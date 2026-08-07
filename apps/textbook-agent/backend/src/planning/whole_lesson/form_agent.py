"""FAST-tier whole-lesson form planner agent."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from planning.catalogue_projections import (
    build_form_candidate_map,
    project_form_guidance,
)
from planning.llm_contract_errors import is_transport_error, structured_output_errors
from planning.planner_diagnostics import log_planner_attempt_failed
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.legality import LessonLegalitySnapshot
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.prompt_render import (
    build_form_planner_payload,
    render_form_prompt,
)
from planning.whole_lesson.teaching_plan import TeachingPlan
from planning.whole_lesson.validation import (
    ValidationReport,
    advisory_form_qc,
    validate_form_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_FORM_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, structured_output_type_for_model


class NoLegalFormCandidatesError(RuntimeError):
    """Deterministic configuration failure — do not call the form LLM."""

    def __init__(self, block_ids: list[str]) -> None:
        self.block_ids = list(block_ids)
        self.code = "NO_LEGAL_FORM_CANDIDATES"
        super().__init__(
            f"no legal form candidates for blocks: {self.block_ids}"
        )


@dataclass
class FormPlanResult:
    plan: FormPlan
    validation: ValidationReport
    qc: list[dict[str, Any]]
    prompt: str
    raw_response: str
    form_guidance: dict[str, Any]
    candidate_map: dict[str, tuple[str, ...]]
    attempts: int


async def _call_form_model(
    *,
    prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
) -> tuple[FormPlan, str]:
    model = get_v3_model(V2_FORM_PLANNER)
    spec = get_v3_spec(V2_FORM_PLANNER)
    slot = get_v3_slot(V2_FORM_PLANNER)
    system_prompt, _, _ = prompt.partition("\n\n## USER INPUT\n\n")
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(FormPlan, spec=spec),
        system_prompt=system_prompt or prompt,
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id,
        caller="v2_form_planner",
        generation_id=generation_id,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=V2_FORM_PLANNER,
        model_settings=get_v3_model_settings(V2_FORM_PLANNER),
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.page_form_plan_timeout_seconds),
        ),
    )
    raw = result.output
    raw_text = (
        raw.model_dump_json()
        if hasattr(raw, "model_dump_json")
        else json.dumps(raw, default=str)
    )
    if isinstance(raw, FormPlan):
        return raw, raw_text
    if hasattr(raw, "model_dump"):
        return FormPlan.model_validate(raw.model_dump()), raw_text
    return FormPlan.model_validate(raw), raw_text


async def run_form_planner(
    packet: ImmutableLessonPacket,
    teaching_plan: TeachingPlan,
    *,
    legality: LessonLegalitySnapshot,
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> FormPlanResult:
    candidate_map = build_form_candidate_map(
        teaching_plan,
        compatible_objects_by_intent=legality.compatible_objects_by_intent,
    )
    teaching_block_ids = [
        block.id for section in teaching_plan.sections for block in section.blocks
    ]
    empty_candidates = [
        block_id
        for block_id in teaching_block_ids
        if not candidate_map.get(block_id)
    ]
    if empty_candidates:
        raise NoLegalFormCandidatesError(sorted(empty_candidates))

    # Descriptive guidance only for already-legal object IDs.
    legal_object_ids = {
        object_id
        for objects in candidate_map.values()
        for object_id in objects
    } | set(legality.permitted_objects)
    form_proj = project_form_guidance(permitted_object_ids=legal_object_ids)
    form_guidance = form_proj.to_dict()

    prompt = render_form_prompt(
        packet,
        teaching_plan,
        form_guidance,
        resource_id=packet.resource_id,
        candidate_map=candidate_map,
    )
    user_payload = build_form_planner_payload(
        packet,
        teaching_plan,
        form_guidance,
        candidate_map=candidate_map,
    )
    tid = trace_id or str(uuid.uuid4())
    plan: FormPlan | None = None
    validation = ValidationReport(ok=False, issues=[])
    raw_response = ""
    previous_output: object | None = None
    repair_errors: list[str] = []
    last_error = None

    for attempt in (1, 2):
        try:
            payload = user_payload
            if attempt == 2 and repair_errors:
                payload = {
                    **user_payload,
                    "repair": {
                        "instruction": (
                            "Return the complete corrected FormPlan. "
                            "You may modify only: block_id only when necessary to match "
                            "an existing teaching block; object; placement; reason; "
                            "escalation. You may not introduce teaching-owned fields. "
                            "Every teaching block must appear exactly once."
                        ),
                        "previous_output": previous_output,
                        "validation_errors": repair_errors,
                    },
                }
            plan, raw_response = await _call_form_model(
                prompt=prompt,
                user_payload=payload,
                trace_id=f"{tid}:form{attempt}",
                generation_id=generation_id,
            )
            previous_output = plan.model_dump(mode="json")

            validation = validate_form_plan(
                plan, teaching_plan, candidate_map=candidate_map
            )
            qc = [finding.to_dict() for finding in advisory_form_qc(plan)]
            if validation.ok:
                return FormPlanResult(
                    plan=plan,
                    validation=validation,
                    qc=qc,
                    prompt=prompt,
                    raw_response=raw_response,
                    form_guidance=form_guidance,
                    candidate_map=candidate_map,
                    attempts=attempt,
                )
            last_error = "validation_failed"
            repair_errors = [
                f"{issue.code}: {issue.message}" for issue in validation.issues
            ]
            log_planner_attempt_failed(
                node=V2_FORM_PLANNER,
                attempt=attempt,
                errors=repair_errors,
                repair_attached=attempt == 2,
                will_retry=attempt == 1,
            )
        except Exception as exc:
            last_error = str(exc)
            if is_transport_error(exc):
                repair_errors = []
            else:
                repair_errors = structured_output_errors(exc)
                if previous_output is None and raw_response:
                    try:
                        previous_output = json.loads(raw_response)
                    except Exception:  # noqa: BLE001
                        previous_output = raw_response
            log_planner_attempt_failed(
                node=V2_FORM_PLANNER,
                attempt=attempt,
                errors=repair_errors,
                exc=exc,
                repair_attached=attempt == 2 and bool(repair_errors),
                will_retry=attempt == 1,
            )
            continue

    raise RuntimeError(f"form planner failed after 2 attempts: {last_error}")

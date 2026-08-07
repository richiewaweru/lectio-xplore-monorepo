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
from planning.planner_diagnostics import log_planner_attempt_failed
from planning.whole_lesson.form_plan import FormPlan
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
from resource_specs.candidates import assemble_lesson_guidance
from resource_specs.loader import get_spec
from v3_blueprint.skeletons import load_skeleton_catalog
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_FORM_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, structured_output_type_for_model
from contracts.lectio_page import get_intent_catalogue, get_object_catalogue


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


def _resource_permitted_objects(resource_id: str) -> set[str] | None:
    try:
        intents = get_intent_catalogue()["intents"]
        objects = get_object_catalogue()["objects"]
        spec = get_spec(resource_id)
        catalog = load_skeleton_catalog()
        slots = {
            slot_id: {**dict(slot or {}), "slot_id": slot_id}
            for slot_id, slot in (catalog.slots or {}).items()
        }
        guidance = assemble_lesson_guidance(
            resource_spec=spec,
            skeleton_slots=slots,
            intent_catalogue=intents,
            object_catalogue=objects,
        )
        return set(guidance.permitted_object_ids)
    except Exception:  # noqa: BLE001
        return None


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
        # Repair is owned by run_form_planner's outer attempt loop below.
        # pydantic-ai's in-library output retry replays the model's own invalid
        # response in the same conversation, which DeepSeek rejects with HTTP 400
        # when that response is reasoning-only with empty content.
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
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> FormPlanResult:
    permitted_objects = _resource_permitted_objects(packet.resource_id)
    form_proj = project_form_guidance(permitted_object_ids=permitted_objects)
    form_guidance = form_proj.to_dict()
    candidate_map = build_form_candidate_map(
        teaching_plan,
        form_guidance=form_proj,
        permitted_object_ids=permitted_objects,
    )
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
    last_error = None

    for attempt in (1, 2):
        try:
            payload = user_payload
            if attempt == 2 and plan is not None:
                payload = {
                    **user_payload,
                    "repair": {
                        "instruction": (
                            "Change only invalid form fields "
                            "(object, placement, reason, escalation). "
                            "Do not invent teaching fields. "
                            "Keep every block_id exactly once."
                        ),
                        "previous_plan": plan.model_dump(mode="json"),
                        "failures": validation.to_dict()["issues"],
                    },
                }
            plan, raw_response = await _call_form_model(
                prompt=prompt,
                user_payload=payload,
                trace_id=f"{tid}:form{attempt}",
                generation_id=generation_id,
            )

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
            log_planner_attempt_failed(
                node=V2_FORM_PLANNER,
                attempt=attempt,
                errors=[str(issue) for issue in validation.to_dict()["issues"]],
                repair_attached=attempt == 2 and plan is not None,
                will_retry=attempt == 1,
            )
        except Exception as exc:
            last_error = str(exc)
            log_planner_attempt_failed(
                node=V2_FORM_PLANNER,
                attempt=attempt,
                errors=[],
                exc=exc,
                repair_attached=attempt == 2 and plan is not None,
                will_retry=attempt == 1,
            )
            continue

    raise RuntimeError(f"form planner failed after 2 attempts: {last_error}")

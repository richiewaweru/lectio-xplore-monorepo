"""STANDARD-tier whole-lesson teaching approach agent."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from planning.catalogue_projections import (
    TeachingGuidanceProjection,
    project_teaching_guidance,
)
from planning.llm_contract_errors import is_transport_error, structured_output_errors
from planning.whole_lesson.legality import (
    LessonLegalitySnapshot,
    build_lesson_legality_snapshot,
    project_slot_intent_policy,
    snapshot_as_teaching_sets,
)
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.prompt_render import render_teaching_prompt
from planning.whole_lesson.teaching_plan import TeachingPlan
from planning.whole_lesson.validation import (
    ValidationReport,
    advisory_teaching_qc,
    validate_teaching_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_LESSON_APPROACH_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, structured_output_type_for_model


@dataclass
class TeachingPlanAttempt:
    prompt: str
    raw_response: str
    plan: TeachingPlan | None
    validation: ValidationReport
    qc: list[dict[str, Any]]
    attempt: int
    error: str | None = None


@dataclass
class TeachingPlanResult:
    plan: TeachingPlan
    validation: ValidationReport
    qc: list[dict[str, Any]]
    prompt: str
    raw_response: str
    teaching_guidance: TeachingGuidanceProjection
    attempts: list[TeachingPlanAttempt]
    typical_by_slot: dict[str, set[str]]
    permitted_intents: set[str]
    excluded_intents: set[str]
    legality: LessonLegalitySnapshot


async def _call_teaching_model(
    *,
    prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
) -> tuple[TeachingPlan, str]:
    model = get_v3_model(V2_LESSON_APPROACH_PLANNER)
    spec = get_v3_spec(V2_LESSON_APPROACH_PLANNER)
    slot = get_v3_slot(V2_LESSON_APPROACH_PLANNER)
    system_prompt, _, _user = prompt.partition("\n\n## USER INPUT\n\n")
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(TeachingPlan, spec=spec),
        system_prompt=system_prompt or prompt,
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id,
        caller="v2_lesson_approach_planner",
        generation_id=generation_id,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=V2_LESSON_APPROACH_PLANNER,
        model_settings=get_v3_model_settings(V2_LESSON_APPROACH_PLANNER),
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.page_lesson_plan_timeout_seconds),
        ),
    )
    raw = result.output
    raw_text = (
        raw.model_dump_json()
        if hasattr(raw, "model_dump_json")
        else json.dumps(raw, default=str)
    )
    if isinstance(raw, TeachingPlan):
        return raw, raw_text
    if hasattr(raw, "model_dump"):
        return TeachingPlan.model_validate(raw.model_dump()), raw_text
    return TeachingPlan.model_validate(raw), raw_text


async def run_lesson_approach_planner(
    packet: ImmutableLessonPacket,
    *,
    legality: LessonLegalitySnapshot | None = None,
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
) -> TeachingPlanResult:
    if require_items and not packet.approved_items:
        from planning.approved_items import ItemPoolEmptyError

        raise ItemPoolEmptyError(card_id="unknown", pack_id=None)

    snapshot = legality or build_lesson_legality_snapshot(packet)
    permitted, excluded, typical_by_slot = snapshot_as_teaching_sets(snapshot)
    teaching_guidance = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents={key: "excluded" for key in excluded},
    )
    slot_intent_policy = project_slot_intent_policy(snapshot)
    prompt = render_teaching_prompt(packet, teaching_guidance, resource_id=packet.resource_id)
    user_payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
    }
    attempts: list[TeachingPlanAttempt] = []
    last_error: str | None = None
    plan: TeachingPlan | None = None
    validation = ValidationReport(ok=False, issues=[])
    raw_response = ""
    previous_output: object | None = None
    repair_errors: list[str] = []
    tid = trace_id or str(uuid.uuid4())

    for attempt in (1, 2):
        try:
            call_payload = user_payload
            if attempt == 2 and repair_errors:
                call_payload = {
                    **user_payload,
                    "repair": {
                        "instruction": (
                            "Return the complete corrected TeachingPlan JSON. "
                            "Change only fields required to satisfy these errors. "
                            "Use only intents listed under slot_intent_policy for each slot."
                        ),
                        "previous_output": previous_output,
                        "validation_errors": repair_errors,
                        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
                        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
                    },
                }
            plan, raw_response = await _call_teaching_model(
                prompt=prompt,
                user_payload=call_payload,
                trace_id=f"{tid}:attempt{attempt}",
                generation_id=generation_id,
            )
            previous_output = plan.model_dump(mode="json")
            validation = validate_teaching_plan(
                plan,
                packet,
                permitted_intents=permitted,
                excluded_intents=excluded,
                typical_by_slot=typical_by_slot,
            )
            qc = [finding.to_dict() for finding in advisory_teaching_qc(plan)]
            attempts.append(
                TeachingPlanAttempt(
                    prompt=prompt,
                    raw_response=raw_response,
                    plan=plan,
                    validation=validation,
                    qc=qc,
                    attempt=attempt,
                )
            )
            if validation.ok:
                return TeachingPlanResult(
                    plan=plan,
                    validation=validation,
                    qc=qc,
                    prompt=prompt,
                    raw_response=raw_response,
                    teaching_guidance=teaching_guidance,
                    attempts=attempts,
                    typical_by_slot=typical_by_slot,
                    permitted_intents=permitted,
                    excluded_intents=excluded,
                    legality=snapshot,
                )
            last_error = "validation_failed"
            repair_errors = [
                f"{issue.code}: {issue.message}" for issue in validation.issues
            ]
        except Exception as exc:
            last_error = str(exc)
            attempts.append(
                TeachingPlanAttempt(
                    prompt=prompt,
                    raw_response=raw_response,
                    plan=plan,
                    validation=validation,
                    qc=[],
                    attempt=attempt,
                    error=last_error,
                )
            )
            if is_transport_error(exc):
                # Provider/backoff retry — do not invent contract repair context.
                repair_errors = []
                previous_output = previous_output
            else:
                repair_errors = structured_output_errors(exc)
                if previous_output is None and raw_response:
                    try:
                        previous_output = json.loads(raw_response)
                    except Exception:  # noqa: BLE001
                        previous_output = raw_response
            continue

    raise RuntimeError(
        f"lesson approach planner failed after {len(attempts)} attempts: {last_error}"
        + (
            f" issues={validation.to_dict()['issues']}"
            if last_error == "validation_failed" and validation.issues
            else ""
        )
    )

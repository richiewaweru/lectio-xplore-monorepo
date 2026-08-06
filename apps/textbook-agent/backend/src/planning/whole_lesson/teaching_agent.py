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
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.prompt_render import render_teaching_prompt
from planning.whole_lesson.teaching_plan import TeachingPlan
from planning.whole_lesson.validation import (
    ValidationReport,
    advisory_teaching_qc,
    validate_teaching_plan,
)
from resource_specs.candidates import assemble_lesson_guidance
from resource_specs.loader import get_spec
from v3_blueprint.skeletons import load_skeleton_catalog
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_LESSON_APPROACH_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, structured_output_type_for_model
from contracts.lectio_page import get_intent_catalogue, get_object_catalogue


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


def _legality_context(packet: ImmutableLessonPacket) -> tuple[set[str], set[str], dict[str, set[str]]]:
    intents = get_intent_catalogue()["intents"]
    objects = get_object_catalogue()["objects"]
    spec = get_spec(packet.resource_id)
    catalog = load_skeleton_catalog()
    slots = {
        slot.slot_id: {
            **dict(catalog.slots.get(slot.slot_id) or {}),
            "slot_id": slot.slot_id,
            "typical_intents": slot.typical_intents,
        }
        for slot in packet.slots
    }
    guidance = assemble_lesson_guidance(
        resource_spec=spec,
        skeleton_slots=slots,
        intent_catalogue=intents,
        object_catalogue=objects,
    )
    typical_by_slot = {
        slot.slot_id: set(slot.typical_intents) for slot in guidance.slots
    }
    return (
        set(guidance.permitted_intent_ids),
        set(guidance.excluded_intents.keys()),
        typical_by_slot,
    )


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
    # System prompt is the full rendered prompt minus user JSON — keep identity clauses.
    # Use the resource prompt body before USER INPUT as system; user_payload as user.
    system_prompt, _, _user = prompt.partition("\n\n## USER INPUT\n\n")
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(TeachingPlan, spec=spec),
        system_prompt=system_prompt or prompt,
        # Repair is owned by run_teaching_planner's outer attempt loop below.
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
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
) -> TeachingPlanResult:
    if require_items and not packet.approved_items:
        from planning.approved_items import ItemPoolEmptyError

        raise ItemPoolEmptyError(card_id="unknown", pack_id=None)

    permitted, excluded, typical_by_slot = _legality_context(packet)
    teaching_guidance = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents={key: "excluded" for key in excluded},
    )
    prompt = render_teaching_prompt(packet, teaching_guidance, resource_id=packet.resource_id)
    user_payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
    }
    attempts: list[TeachingPlanAttempt] = []
    last_error: str | None = None
    plan: TeachingPlan | None = None
    validation = ValidationReport(ok=False, issues=[])
    raw_response = ""
    tid = trace_id or str(uuid.uuid4())

    for attempt in (1, 2):
        try:
            call_payload = user_payload
            if attempt == 2 and plan is not None:
                call_payload = {
                    **user_payload,
                    "repair": {
                        "instruction": "Change only invalid fields. Keep immutable paths.",
                        "previous_plan": plan.model_dump(mode="json"),
                        "failures": validation.to_dict()["issues"],
                    },
                }
            plan, raw_response = await _call_teaching_model(
                prompt=prompt,
                user_payload=call_payload,
                trace_id=f"{tid}:attempt{attempt}",
                generation_id=generation_id,
            )
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
                )
            last_error = "validation_failed"
        except Exception as exc:  # transport / schema
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
            # Attempt 2 is the final try (repair OR transport retry).
            continue

    raise RuntimeError(
        f"lesson approach planner failed after {len(attempts)} attempts: {last_error}"
        + (
            f" issues={validation.to_dict()['issues']}"
            if last_error == "validation_failed" and validation.issues
            else ""
        )
    )

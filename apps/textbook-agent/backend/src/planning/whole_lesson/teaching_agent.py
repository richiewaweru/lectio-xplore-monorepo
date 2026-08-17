"""STANDARD-tier whole-lesson teaching approach agent."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from planning.approved_items import approved_item_kind
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
from planning.whole_lesson.teaching_errors import (
    TeachingPlanOutputInvalidError,
    is_recognized_teaching_output_error,
)
from planning.whole_lesson.teaching_plan import TeachingPlan
from planning.whole_lesson.validation import (
    ValidationReport,
    advisory_teaching_qc,
    allowed_teaching_evidence_refs,
    validate_teaching_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_LESSON_APPROACH_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent


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


def _repair_missing_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    assessment_intents: set[str],
) -> None:
    """Assign unused approved cards when a model omits assessment ownership."""
    used = {
        source_id
        for section in plan.sections
        for block in section.blocks
        for source_id in block.source_question_ids
    }
    available = [
        item.id for item in packet.approved_items if item.id not in used
    ]
    for section in plan.sections:
        for block in section.blocks:
            if (
                block.intent == "check-understanding"
                and not block.source_question_ids
                and available
            ):
                block.source_question_ids = [available.pop(0)]


def _repair_invalid_evidence_refs(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Drop only evidence references that cannot resolve in this packet."""
    allowed = allowed_teaching_evidence_refs(packet)
    for section in plan.sections:
        for block in section.blocks:
            block.evidence_refs = [
                ref for ref in block.evidence_refs if ref in allowed
            ]


def _assessment_source_policy(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
) -> dict[str, Any]:
    """Project validator-owned assessment facts into both planner attempts."""
    assessment_intents = sorted(
        intent_id
        for intent_id, objects in snapshot.compatible_objects_by_intent.items()
        if {"questions", "choices"} & set(objects)
    )
    approved_sources = [
        {
            "approved_item_id": item.id,
            "kind": approved_item_kind(item),
        }
        for item in packet.approved_items
    ]
    return {
        "eligible_intents": assessment_intents,
        "approved_sources": approved_sources,
        "rules": {
            "selection_is_optional": True,
            "multiple_choice_ids_per_block": "0_or_1",
            "source_only_on_eligible_intent": True,
            "reuse_across_blocks": "forbidden",
            "item_kind_is_fixed_upstream": True,
        },
        "forbidden_terminology": [
            entry.statement for entry in packet.scope.must_not_introduce
        ],
        "allowed_evidence_refs": sorted(allowed_teaching_evidence_refs(packet)),
    }


async def _call_teaching_model(
    *,
    prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
    attempt_start: int = 1,
) -> tuple[TeachingPlan, str]:
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=V2_LESSON_APPROACH_PLANNER,
        output_type=TeachingPlan,
    )
    slot = get_v3_slot(V2_LESSON_APPROACH_PLANNER)
    system_prompt, _, _user = prompt.partition("\n\n## USER INPUT\n\n")
    agent = Agent(
        model=model,
        output_type=provider_output,
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
        attempt_start=attempt_start,
        structured_context=structured_context,
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
    assessment_source_policy = _assessment_source_policy(packet, snapshot)
    prompt = render_teaching_prompt(packet, teaching_guidance, resource_id=packet.resource_id)
    user_payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
        "assessment_source_policy": assessment_source_policy,
        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
    }
    attempts: list[TeachingPlanAttempt] = []
    last_error: str | None = None
    plan: TeachingPlan | None = None
    validation = ValidationReport(ok=False, issues=[])
    raw_response = ""
    previous_output: object | None = None
    repair_errors: list[str] = []
    last_exception: Exception | None = None
    output_invalid_details: list[str] = []
    tid = trace_id or str(uuid.uuid4())

    for attempt in (1, 2):
        last_exception = None
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
                            " For the check-understanding block, when approved "
                            "items exist, include at least one approved "
                            "source_question_id. For a "
                            "multiple-choice assessment block, select exactly one "
                            "approved item ID; never group IDs or reuse an ID. Attach it "
                            "only to an assessment_source_policy eligible intent. Remove "
                            "forbidden terminology and use only allowed_evidence_refs."
                        ),
                        "previous_output": previous_output,
                        "validation_errors": repair_errors,
                        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
                        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
                        "assessment_source_policy": assessment_source_policy,
                    },
                }
            plan, raw_response = await _call_teaching_model(
                prompt=prompt,
                user_payload=call_payload,
                trace_id=f"{tid}:attempt{attempt}",
                generation_id=generation_id,
                attempt_start=attempt,
            )
            previous_output = plan.model_dump(mode="json")
            _repair_missing_assessment_sources(
                plan,
                packet,
                set(assessment_source_policy["eligible_intents"]),
            )
            _repair_invalid_evidence_refs(plan, packet)
            validation = validate_teaching_plan(
                plan,
                packet,
                permitted_intents=permitted,
                excluded_intents=excluded,
                typical_by_slot=typical_by_slot,
                assessment_intents=set(
                    assessment_source_policy["eligible_intents"]
                ),
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
            output_invalid_details = repair_errors
        except Exception as exc:
            last_exception = exc
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
            elif is_recognized_teaching_output_error(exc):
                repair_errors = structured_output_errors(exc)
                output_invalid_details = repair_errors
            else:
                # Only teaching-output noncompliance owns the recoverable contract.
                # Generic provider behavior and programming/input failures remain terminal.
                from pydantic_ai.exceptions import UnexpectedModelBehavior

                if isinstance(exc, UnexpectedModelBehavior):
                    raise
                repair_errors = structured_output_errors(exc)
                if previous_output is None and raw_response:
                    try:
                        previous_output = json.loads(raw_response)
                    except Exception:  # noqa: BLE001
                        previous_output = raw_response
            continue

    if last_exception is not None and is_transport_error(last_exception):
        last_exception.add_note(
            "lesson approach planner exhausted "
            f"{len(attempts)} provider attempts"
        )
        raise last_exception

    if last_error == "validation_failed" or (
        last_exception is not None
        and is_recognized_teaching_output_error(last_exception)
    ):
        raise TeachingPlanOutputInvalidError(
            attempt_count=len(attempts),
            details=output_invalid_details,
        ) from last_exception

    raise RuntimeError(
        f"lesson approach planner failed after {len(attempts)} attempts: {last_error}"
        + (
            f" issues={validation.to_dict()['issues']}"
            if last_error == "validation_failed" and validation.issues
            else ""
        )
    )

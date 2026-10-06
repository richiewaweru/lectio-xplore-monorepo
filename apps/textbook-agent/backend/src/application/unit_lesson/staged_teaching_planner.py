"""Staged teaching planner: prompt rendering and the spine call (phase 3).

The spine fixes lesson-wide structure (titles, state chain, item and
misconception placement, figure plan, block budget). Code checks it, repairs
what is deterministic, and retries the spine alone with the errors attached.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_ai import Agent

from application.unit_lesson.teaching_planner import _assessment_source_policy
from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from curriculum.llm_contract_errors import is_transport_error, structured_output_errors
from curriculum.planning.skeletons import load_skeleton_catalog
from curriculum.prompts import teaching_section_prompt, teaching_spine_prompt
from curriculum.teaching_plan.staged import (
    SpineFigurePlan,
    TeachingSpine,
    TeachingSpineDraft,
    materialize_teaching_spine,
)
from document.shared_lesson.continuity import statement_covered
from infra.authoring.model_policy import (
    TEACHING_SPINE_PLANNER,
    get_v3_model_settings,
    get_v3_slot,
)
from infra.authoring.structured_provider import NO_OUTPUT_RETRY, prepare_structured_agent
from print.generation.catalogue_projections import (
    TeachingGuidanceProjection,
    project_teaching_guidance,
)
from print.generation.whole_lesson.legality import (
    LessonLegalitySnapshot,
    project_slot_intent_policy,
    snapshot_as_teaching_sets,
)
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from print.generation.whole_lesson.prompt_render import (
    BACKBONE_TEACHING_GUIDANCE,
    assert_no_page_object_ids,
)
from print.generation.whole_lesson.teaching_errors import (
    TeachingPlanOutputInvalidError,
    is_recognized_teaching_output_error,
)
from resource_specs.loader import get_spec
from resource_specs.renderer import render_lesson_design_guidance, render_resource_identity

SPINE_REPAIR_INSTRUCTION = (
    "Return the complete corrected TeachingSpine JSON. Change only the fields "
    "required to satisfy these errors and keep everything else as it was. Every "
    "entry_state statement of a section must be covered by the previous section's "
    "exit_state (the first section's by starting_state or prior_established). Place "
    "every approved item id exactly once, copying ids verbatim, and only in "
    "required_assessment_slots sections when that list is non-empty. Use only "
    "misconception ids and backbone figure ids that exist in the fixed input. Keep "
    "planned_block_count within each slot's min_blocks..max_blocks and the "
    "lesson's block limits."
)


# --------------------------------------------------------------------------- prompt


def render_staged_prompt(
    packet: ImmutableLessonPacket,
    teaching_guidance: TeachingGuidanceProjection | None = None,
    *,
    kind: Literal["spine", "section"],
    resource_id: str | None = None,
) -> str:
    """Render the system prompt for a spine or section call (user payload is separate)."""
    spec = get_spec(resource_id or packet.resource_id)
    identity = render_resource_identity(spec)
    recipe_guidance = load_skeleton_catalog().knowledge_type_guidance(
        str(packet.lesson.knowledge_type)
    )
    if recipe_guidance is not None:
        identity = f"{identity.rstrip()}\n\n{render_lesson_design_guidance(recipe_guidance)}"
    if packet.backbone:
        identity = f"{identity.rstrip()}\n\n{BACKBONE_TEACHING_GUIDANCE}"
    body = teaching_spine_prompt() if kind == "spine" else teaching_section_prompt()
    system = body.replace("{resource_identity}", identity)
    if kind == "section":
        from core.prompts.loader import effective_prompt_text

        learner_action_policy = effective_prompt_text("learner-action-policy")
        system = (
            f"{system}\n\n## LEARNER ACTION POLICY\n\n{learner_action_policy}"
            "\n\nThis policy supersedes any narrower reading that learner actions "
            "are only formal assessment. Path-agnostic actions may appear before, "
            "during, or after explanation when they improve the sequence."
        )
    assert_no_page_object_ids(system, where=f"teaching-{kind} prompt")
    return system


def build_planner_projections(
    packet: ImmutableLessonPacket, snapshot: LessonLegalitySnapshot
) -> dict[str, Any]:
    """Projections shared by spine and section calls (same as the single planner)."""
    permitted, excluded, _typical = snapshot_as_teaching_sets(snapshot)
    teaching_guidance = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents={key: "excluded" for key in excluded},
    )
    return {
        "teaching_guidance": teaching_guidance,
        # {"slot_intent_policy": ..., "catalogue_hash": ...}
        "slot_intent_policy": project_slot_intent_policy(snapshot),
        "assessment_source_policy": _assessment_source_policy(packet, snapshot),
    }


# --------------------------------------------------------------------------- model call


async def _call_spine_model(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
    attempt_start: int = 1,
) -> tuple[TeachingSpineDraft, str]:
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=TEACHING_SPINE_PLANNER,
        output_type=TeachingSpineDraft,
    )
    slot = get_v3_slot(TEACHING_SPINE_PLANNER)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=system_prompt,
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id,
        caller="teaching_spine_planner",
        generation_id=generation_id,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=TEACHING_SPINE_PLANNER,
        model_settings=get_v3_model_settings(TEACHING_SPINE_PLANNER),
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
    if isinstance(raw, TeachingSpineDraft):
        return raw, raw_text
    if hasattr(raw, "model_dump"):
        return TeachingSpineDraft.model_validate(raw.model_dump()), raw_text
    return TeachingSpineDraft.model_validate(raw), raw_text


# --------------------------------------------------------------------------- checks


def _backbone_figures(packet: ImmutableLessonPacket) -> dict[str, dict[str, Any]]:
    figures = (packet.backbone or {}).get("figures") or []
    return {str(f["id"]): f for f in figures if isinstance(f, dict) and f.get("id")}


def spine_check_errors(spine: TeachingSpine, packet: ImmutableLessonPacket) -> list[str]:
    """Pure code checks on a materialized spine; each error is 'CODE: message'."""
    errors: list[str] = []
    slots = list(packet.slots)
    sections = list(spine.sections)

    if len(sections) != len(slots):
        errors.append(
            f"SPINE_SECTION_COUNT: spine has {len(sections)} sections but the packet has "
            f"{len(slots)} slots ({', '.join(s.slot_id for s in slots)}); write exactly one "
            "section per slot, in slot order."
        )

    # State chain.
    for index, section in enumerate(sections):
        if index == 0:
            available = " ".join(
                [*spine.starting_state, *(p.statement for p in packet.prior_established)]
            )
            source = "starting_state or prior_established"
        else:
            available = " ".join(sections[index - 1].exit_state)
            source = f"exit_state of section {index} ({sections[index - 1].slot_id})"
        for statement in section.entry_state:
            if not statement_covered(statement, available):
                errors.append(
                    f"SPINE_STATE_CHAIN: section {index + 1} ({section.slot_id}) entry_state "
                    f"'{statement}' is not covered by the {source}; either add it to that "
                    "state or remove it from entry_state."
                )

    # Items.
    known_items = {item.id for item in packet.approved_items}
    required_slots = list(packet.required_assessment_slots)
    placements: dict[str, list[str]] = {}
    for section in sections:
        for item_id in section.approved_item_ids:
            placements.setdefault(item_id, []).append(section.slot_id)
            if item_id not in known_items:
                errors.append(
                    f"SPINE_ITEM_UNKNOWN: section {section.slot_id} places approved item "
                    f"'{item_id}', which is not an approved item id "
                    f"(valid ids: {sorted(known_items)})."
                )
            elif required_slots and section.slot_id not in required_slots:
                errors.append(
                    f"SPINE_ITEM_OUTSIDE_ASSESSMENT_SLOT: approved item '{item_id}' is placed "
                    f"in {section.slot_id}, but items may only go in {required_slots}."
                )
    for item_id, where in placements.items():
        if len(where) > 1 and item_id in known_items:
            errors.append(
                f"SPINE_ITEM_DUPLICATE: approved item '{item_id}' is placed in "
                f"{len(where)} sections ({', '.join(where)}); place it in exactly one."
            )
    for item in packet.approved_items:
        if item.id not in placements:
            errors.append(
                f"SPINE_ITEM_UNPLACED: approved item '{item.id}' is not placed in any "
                "section; add it to one section's approved_item_ids"
                + (f" (one of {required_slots})." if required_slots else ".")
            )
    if required_slots:
        by_slot = {s.slot_id: s for s in sections}
        for slot_id in required_slots:
            section = by_slot.get(slot_id)
            if section is not None and not section.approved_item_ids:
                errors.append(
                    f"SPINE_ASSESSMENT_SLOT_EMPTY: required assessment slot {slot_id} has no "
                    "approved_item_ids; place at least one approved item there."
                )

    # Misconceptions.
    known_misconceptions = {m.id for m in packet.misconceptions}
    assigned: set[str] = set()
    for section in sections:
        for mid in section.misconception_ids:
            assigned.add(mid)
            if mid not in known_misconceptions:
                errors.append(
                    f"SPINE_MISCONCEPTION_UNKNOWN: section {section.slot_id} lists "
                    f"misconception '{mid}', which is not in the packet "
                    f"(valid ids: {sorted(known_misconceptions)})."
                )
    for mid in spine.misconception_focus_ids:
        if mid not in known_misconceptions:
            errors.append(
                f"SPINE_MISCONCEPTION_UNKNOWN: misconception_focus_ids lists '{mid}', "
                f"which is not in the packet (valid ids: {sorted(known_misconceptions)})."
            )
        elif mid not in assigned:
            errors.append(
                f"SPINE_MISCONCEPTION_UNASSIGNED: focus misconception '{mid}' is not "
                "assigned to any section; add it to one section's misconception_ids."
            )

    # Figures.
    figures = _backbone_figures(packet)
    for section in sections:
        for plan in section.figure_plan:
            fid = plan.backbone_figure_id
            if fid is None:
                continue
            if not packet.backbone:
                errors.append(
                    f"SPINE_FIGURE_UNKNOWN: section {section.slot_id} sets backbone_figure_id "
                    f"'{fid}' but this lesson has no backbone; set it to null."
                )
            elif fid not in figures:
                errors.append(
                    f"SPINE_FIGURE_UNKNOWN: section {section.slot_id} uses backbone_figure_id "
                    f"'{fid}', which is not a backbone figure (valid ids: {sorted(figures)}); "
                    "use a valid id or null."
                )

    # Block budget.
    limits = packet.limits
    slot_by_id = {s.slot_id: s for s in slots}
    total = 0
    for section in sections:
        count = section.planned_block_count
        total += count
        slot = slot_by_id.get(section.slot_id)
        low = slot.min_blocks if slot else 1
        high = min(slot.max_blocks, limits.max_blocks_per_section) if slot else limits.max_blocks_per_section
        if not low <= count <= high:
            errors.append(
                f"SPINE_BLOCK_BUDGET: section {section.slot_id} planned_block_count {count} "
                f"is outside the allowed {low}..{high} blocks."
            )
    if total > limits.max_total_blocks:
        errors.append(
            f"SPINE_BLOCK_BUDGET: planned blocks total {total} exceeds the lesson limit "
            f"of {limits.max_total_blocks}; reduce planned_block_count in some sections."
        )
    return errors


def repair_spine_figure_plan(
    spine: TeachingSpine, packet: ImmutableLessonPacket
) -> list[dict[str, Any]]:
    """Add backbone figures owned items rely on to the section's figure_plan."""
    figures = _backbone_figures(packet)
    changes: list[dict[str, Any]] = []
    for section in spine.sections:
        present = {p.backbone_figure_id for p in section.figure_plan if p.backbone_figure_id}
        for item_id in section.approved_item_ids:
            fid = (packet.item_backbone_refs.get(item_id) or {}).get("figure_id")
            if not fid or fid not in figures or fid in present:
                continue
            section.figure_plan.append(
                SpineFigurePlan(
                    purpose=str(figures[fid].get("purpose") or fid),
                    backbone_figure_id=fid,
                )
            )
            present.add(fid)
            changes.append(
                {
                    "repair": "spine_figure_plan",
                    "slot_id": section.slot_id,
                    "item_id": item_id,
                    "backbone_figure_id": fid,
                }
            )
    return changes


# --------------------------------------------------------------------------- orchestration


@dataclass
class SpineAttempt:
    attempt: int
    raw_response: str = ""
    errors: list[str] = field(default_factory=list)
    latency_s: float = 0.0
    error: str | None = None


@dataclass
class SpineResult:
    spine: TeachingSpine
    draft: TeachingSpineDraft
    attempts: list[SpineAttempt]
    repairs: list[dict[str, Any]]


async def plan_teaching_spine(
    packet: ImmutableLessonPacket,
    *,
    snapshot: LessonLegalitySnapshot,
    teaching_guidance: TeachingGuidanceProjection,
    slot_intent_policy: dict[str, Any],
    assessment_source_policy: dict[str, Any],
    trace_id: str | None = None,
    generation_id: str | None = None,
    max_attempts: int = 3,
) -> SpineResult:
    """Run the spine call with code checks and up to ``max_attempts`` repairs.

    ``slot_intent_policy`` is the dict returned by ``project_slot_intent_policy``
    (keys ``slot_intent_policy`` and ``catalogue_hash``).
    """
    del snapshot  # projections arrive already built; kept for a stable signature
    system_prompt = render_staged_prompt(packet, teaching_guidance, kind="spine")
    user_payload: dict[str, Any] = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
        "assessment_source_policy": assessment_source_policy,
        "reserved_assessment_scenarios": [
            item.stem for item in packet.approved_items if item.stem.strip()
        ],
        "approved_item_stems": [
            {"id": item.id, "stem": item.stem} for item in packet.approved_items
        ],
        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
    }
    tid = trace_id or str(uuid.uuid4())
    slot_ids = [slot.slot_id for slot in packet.slots]
    attempts: list[SpineAttempt] = []
    repair_errors: list[str] = []
    previous_output: object | None = None
    last_exception: Exception | None = None
    last_invalid = False
    details: list[str] = []

    for attempt in range(1, max_attempts + 1):
        last_exception = None
        last_invalid = False
        payload = user_payload
        if repair_errors:
            payload = {
                **user_payload,
                "repair": {
                    "instruction": SPINE_REPAIR_INSTRUCTION,
                    "previous_output": previous_output,
                    "validation_errors": repair_errors,
                },
            }
        record = SpineAttempt(attempt=attempt)
        attempts.append(record)
        started = time.perf_counter()
        raw_response = ""
        try:
            draft, raw_response = await _call_spine_model(
                system_prompt=system_prompt,
                user_payload=payload,
                trace_id=f"{tid}:spine{attempt}",
                generation_id=generation_id,
                attempt_start=attempt,
            )
            record.raw_response = raw_response
            draft = TeachingSpineDraft.model_validate(
                draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft
            )
            previous_output = draft.model_dump(mode="json")
            try:
                spine = materialize_teaching_spine(
                    draft,
                    slot_ids=slot_ids,
                    item_backbone_refs=packet.item_backbone_refs,
                )
            except ValueError as exc:
                errors = [f"SPINE_SECTION_COUNT: {exc}"]
            else:
                repairs = repair_spine_figure_plan(spine, packet)
                errors = spine_check_errors(spine, packet)
                if not errors:
                    record.latency_s = time.perf_counter() - started
                    return SpineResult(
                        spine=spine, draft=draft, attempts=attempts, repairs=repairs
                    )
            record.errors = errors
            record.error = "validation_failed"
            repair_errors = errors
            details = errors
            last_invalid = True
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            record.error = str(exc)
            record.raw_response = record.raw_response or raw_response
            if is_transport_error(exc):
                repair_errors = []
            elif isinstance(exc, ValidationError) or is_recognized_teaching_output_error(exc):
                repair_errors = structured_output_errors(exc)
                details = repair_errors
                record.errors = repair_errors
                last_invalid = True
            else:
                from pydantic_ai.exceptions import UnexpectedModelBehavior

                if isinstance(exc, UnexpectedModelBehavior):
                    raise
                repair_errors = structured_output_errors(exc)
                record.errors = repair_errors
        finally:
            if not record.latency_s:
                record.latency_s = time.perf_counter() - started

    if last_exception is not None and is_transport_error(last_exception):
        last_exception.add_note(f"teaching spine exhausted {len(attempts)} provider attempts")
        raise last_exception
    if last_invalid:
        raise TeachingPlanOutputInvalidError(
            attempt_count=len(attempts), details=details
        ) from last_exception
    raise RuntimeError(
        f"teaching spine failed after {len(attempts)} attempts: "
        f"{attempts[-1].error if attempts else 'no attempts'}"
    )


__all__ = [
    "SpineAttempt",
    "SpineResult",
    "build_planner_projections",
    "plan_teaching_spine",
    "render_staged_prompt",
    "repair_spine_figure_plan",
    "spine_check_errors",
]

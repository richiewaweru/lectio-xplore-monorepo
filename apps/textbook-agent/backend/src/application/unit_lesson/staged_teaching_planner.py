"""Staged teaching planner: prompt rendering and the spine call (phase 3).

The spine fixes lesson-wide structure (titles, state chain, item and
misconception placement, figure plan, block budget). Code checks it, repairs
what is deterministic, and retries the spine alone with the errors attached.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import types
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_ai import Agent

from application.unit_lesson.teaching_planner import (
    TeachingPlanAttempt,
    TeachingPlanResult,
    _action_source_compatibility_errors,
    _frozen_assessment_reuse_errors,
    _frozen_assessment_reuse_flags,
    _repair_missing_assessment_sources,
    _task_source_contract_errors,
    _unknown_learner_action_errors,
    _action_source_compatibility_errors_for_section,
    _assessment_source_policy,
    _frozen_assessment_reuse_errors_for_section,
    _frozen_assessment_reuse_flags_for_section,
    _repair_briefs_missing_anchor_grounding_for_section,
    _repair_incompatible_assessment_sources_for_section,
    _repair_invalid_evidence_refs_for_section,
    _repair_missing_figure_visuals_for_section,
    _repair_sources_outside_structural_slots_for_section,
    _task_source_contract_errors_for_section,
    _unknown_learner_action_errors_for_section,
)
from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from curriculum.backbone.models import BackboneFigure
from curriculum.llm_contract_errors import is_transport_error, structured_output_errors
from curriculum.planning.skeletons import load_skeleton_catalog
from curriculum.prompts import teaching_section_prompt, teaching_spine_prompt
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanDraftBlock,
    TeachingPlanDraftV2,
    TeachingPlanSection,
    VisualSpec,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.semantic_review import (
    ADVISORY_ONLY_SEMANTIC_CODES,
    TeachingPlanSemanticFinding,
    TeachingPlanSemanticReviewError,
    TeachingPlanSemanticReviewResult,
)
from curriculum.teaching_plan.staged_review import (
    review_teaching_lesson,
    review_teaching_section,
)
from curriculum.teaching_plan.staged import (
    SpineFigurePlan,
    TeachingSectionDraft,
    TeachingSpine,
    TeachingSpineDraft,
    assemble_teaching_plan_draft,
    materialize_teaching_spine,
)
from document.shared_lesson.continuity import statement_covered
from infra.authoring.model_policy import (
    TEACHING_SECTION_PLANNER,
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
    build_lesson_legality_snapshot,
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
from print.generation.whole_lesson.validation import (
    TeachingValidationContext,
    ValidationIssue,
    ValidationReport,
    _flag_locations,
    advisory_issue_flags,
    advisory_teaching_qc,
    apply_advisory_gate,
    plan_quality_flag,
    validate_teaching_plan,
    validate_teaching_section,
)
from resource_specs.loader import get_spec
from resource_specs.renderer import render_lesson_design_guidance, render_resource_identity

_LEGACY_REQUIRED_SOURCE_INTENTS = frozenset({"check-understanding", "diagnose-misconception"})

SECTION_REPAIR_INSTRUCTION = (
    "Return the complete corrected section JSON (blocks only). Change only what is "
    "required to satisfy these errors and keep everything else as it was. Write "
    "between max(1, number of assigned items) and planned_block_count blocks "
    "(planned_block_count is a maximum). Bind each assigned approved item to exactly "
    "one block (at most one item per block), copying ids verbatim, and bind nothing "
    "else. Copy every backbone "
    "figure in figure_plan into a block's visual with figure_ref set to its id."
)

SPINE_REPAIR_INSTRUCTION = (
    "Return the complete corrected TeachingSpine JSON. Change only the fields "
    "required to satisfy these errors and keep everything else as it was. Every "
    "entry_state statement of a section must be covered by the previous section's "
    "exit_state (the first section's by starting_state or prior_established). Placing "
    "approved items is optional, but never place an item twice, copy ids verbatim, "
    "and when required_assessment_slots is non-empty every one of those slots must own "
    "at least one item and items go only there. A section may own no more items than "
    "its planned_block_count (one item per block). Use only "
    "misconception ids and backbone figure ids that exist in the fixed input. "
    "planned_block_count is a maximum; keep it within each slot's min_blocks..max_blocks "
    "and keep the sum within the lesson's block limit."
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
    permitted, excluded, typical = snapshot_as_teaching_sets(snapshot)
    teaching_guidance = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents={key: "excluded" for key in excluded},
    )
    return {
        "teaching_guidance": teaching_guidance,
        "permitted_intents": permitted,
        "excluded_intents": excluded,
        "typical_by_slot": typical,
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
    # Selection is optional (same rule as the single planner): unplaced items are fine.
    # What is required is that each required assessment slot owns one, and that a
    # section never owns more items than it has blocks (one item per block).
    for section in sections:
        if len(section.approved_item_ids) > section.planned_block_count:
            errors.append(
                f"SPINE_ITEM_BLOCK_BUDGET: section {section.slot_id} is assigned "
                f"{len(section.approved_item_ids)} approved items but plans only "
                f"{section.planned_block_count} blocks; each item needs its own block "
                "(at most one item per block), so assign fewer items to this section "
                "(items are optional) or raise planned_block_count within its limit."
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
            f"SPINE_BLOCK_BUDGET: planned block maxima total {total} exceeds the lesson "
            f"limit of {limits.max_total_blocks}; reduce planned_block_count in some sections."
        )
    return errors


def repair_spine_state_chain(
    spine: TeachingSpine, packet: ImmutableLessonPacket
) -> list[dict[str, Any]]:
    """Make the state chain hold by construction; it is never a spine error.

    Section n's ``entry_state`` must be covered by section n-1's ``exit_state`` (the
    first section by ``starting_state`` plus ``prior_established``). Word-coverage is a
    heuristic, so a miss is repaired deterministically instead of failing the spine: each
    uncovered entry statement is appended to the previous section's ``exit_state`` (to the
    spine's ``starting_state`` for the first section). The repair is recorded.
    """
    changes: list[dict[str, Any]] = []
    sections = list(spine.sections)
    for index, section in enumerate(sections):
        if index == 0:
            target = spine.starting_state
            target_name = "starting_state"
            prior = [p.statement for p in packet.prior_established]
        else:
            target = sections[index - 1].exit_state
            target_name = "exit_state"
            prior = []
        for statement in section.entry_state:
            if statement_covered(statement, " ".join([*target, *prior])):
                continue
            target.append(statement)
            changes.append(
                {
                    "repair": "spine_state_chain",
                    "slot_id": section.slot_id,
                    "from_slot_id": sections[index - 1].slot_id if index else None,
                    "appended_to": target_name,
                    "statement": statement,
                }
            )
    return changes


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
                repairs = [
                    *repair_spine_state_chain(spine, packet),
                    *repair_spine_figure_plan(spine, packet),
                ]
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


# --------------------------------------------------------------------------- sections (phase 4)


async def _call_section_model(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
    attempt_start: int = 1,
) -> tuple[TeachingSectionDraft, str]:
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=TEACHING_SECTION_PLANNER,
        output_type=TeachingSectionDraft,
    )
    slot = get_v3_slot(TEACHING_SECTION_PLANNER)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=system_prompt,
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id,
        caller="teaching_section_planner",
        generation_id=generation_id,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=TEACHING_SECTION_PLANNER,
        model_settings=get_v3_model_settings(TEACHING_SECTION_PLANNER),
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
    if isinstance(raw, TeachingSectionDraft):
        return raw, raw_text
    if hasattr(raw, "model_dump"):
        return TeachingSectionDraft.model_validate(raw.model_dump()), raw_text
    return TeachingSectionDraft.model_validate(raw), raw_text


def _spine_section(spine: TeachingSpine, slot_id: str):
    for section in spine.sections:
        if section.slot_id == slot_id:
            return section
    raise KeyError(f"spine has no section for slot {slot_id!r}")


def _backbone_target_records(
    packet: ImmutableLessonPacket, targets: list[str]
) -> list[dict[str, Any]]:
    backbone = packet.backbone or {}
    records: dict[str, dict[str, Any]] = {}
    anchor = backbone.get("anchor")
    if isinstance(anchor, dict) and anchor.get("id"):
        records[str(anchor["id"])] = anchor
    for variant in backbone.get("variants") or []:
        if isinstance(variant, dict) and variant.get("id"):
            records[str(variant["id"])] = variant
    return [dict(records.get(target) or {"id": target}) for target in targets]


def section_payload(
    spine: TeachingSpine,
    slot_id: str,
    packet: ImmutableLessonPacket,
    projections: dict[str, Any],
) -> dict[str, Any]:
    """User payload for one section call (everything it may rely on)."""
    section = _spine_section(spine, slot_id)
    slot = next((s for s in packet.slots if s.slot_id == slot_id), None)
    policy = projections["assessment_source_policy"]
    assigned_ids = set(section.approved_item_ids)
    assigned_items = [
        dict(source)
        for source in policy.get("approved_sources", [])
        if source.get("approved_item_id") in assigned_ids
    ]
    misconception_ids = set(section.misconception_ids)
    figures = _backbone_figures(packet)
    figure_dumps: list[dict[str, Any]] = []
    for plan in section.figure_plan:
        fid = plan.backbone_figure_id
        if not fid or fid not in figures:
            continue
        try:
            figure_dumps.append(BackboneFigure.model_validate(figures[fid]).model_dump(mode="json"))
        except ValueError:
            figure_dumps.append(dict(figures[fid]))
    return {
        "spine": spine.model_dump(mode="json"),
        "section": section.model_dump(mode="json"),
        "slot": slot.model_dump(mode="json") if slot else {"slot_id": slot_id},
        "slot_intent_policy": (
            projections["slot_intent_policy"]["slot_intent_policy"].get(slot_id, {})
        ),
        "lesson": packet.lesson.model_dump(mode="json"),
        "scope": packet.scope.model_dump(mode="json"),
        "anchor": packet.anchor.model_dump(mode="json"),
        "terminology": list(packet.scope.terminology),
        "assigned_items": assigned_items,
        "assigned_misconceptions": [
            m.model_dump(mode="json") for m in packet.misconceptions if m.id in misconception_ids
        ],
        "backbone_targets": _backbone_target_records(packet, list(section.backbone_targets)),
        "backbone_figures": figure_dumps,
        "figure_plan": [p.model_dump(mode="json") for p in section.figure_plan],
        "reserved_assessment_scenarios": [
            item.stem for item in packet.approved_items if item.stem.strip()
        ],
        "assessment_source_policy": {
            "rules": policy.get("rules", {}),
            "eligible_intents": policy.get("eligible_intents", []),
            "allowed_evidence_refs": policy.get("allowed_evidence_refs", []),
            "forbidden_terminology": policy.get("forbidden_terminology", []),
        },
        # planned_block_count is a MAXIMUM; one block per assigned item at least.
        "planned_block_count": section.planned_block_count,
        "min_blocks": max(1, len(section.approved_item_ids)),
    }


# ---- figure copy


def _expected_figure_visual(figure: dict[str, Any]) -> dict[str, Any] | None:
    try:
        backbone_figure = BackboneFigure.model_validate(figure)
    except ValueError:
        return None
    mode = backbone_figure.effective_mode
    must_show = list(backbone_figure.must_show)
    if not must_show and mode == "diagram":
        must_show = [backbone_figure.purpose]
    return {
        "mode": mode,
        "purpose": backbone_figure.purpose,
        "must_show": must_show,
        "labels_required": list(backbone_figure.labels_required),
    }


def copy_backbone_figures(
    section: TeachingPlanSection, packet: ImmutableLessonPacket
) -> list[dict[str, Any]]:
    """Overwrite visuals that name a backbone figure with that figure's contract."""
    figures = _backbone_figures(packet)
    changes: list[dict[str, Any]] = []
    for block in section.blocks:
        visual = block.visual
        if visual is None or not visual.figure_ref or visual.figure_ref not in figures:
            continue
        expected = _expected_figure_visual(figures[visual.figure_ref])
        if expected is None:
            continue
        fields = [k for k, v in expected.items() if getattr(visual, k) != v]
        if not fields:
            continue
        for key, value in expected.items():
            setattr(visual, key, value)
        changes.append(
            {
                "repair": "backbone_figure_copy",
                "block_id": block.id,
                "figure_id": visual.figure_ref,
                "fields": fields,
            }
        )
    return changes


def figure_copy_errors(section: TeachingPlanSection, packet: ImmutableLessonPacket) -> list[str]:
    """Guard: every visual naming a backbone figure must equal the figure's contract."""
    figures = _backbone_figures(packet)
    errors: list[str] = []
    for block in section.blocks:
        visual: VisualSpec | None = block.visual
        if visual is None or not visual.figure_ref or visual.figure_ref not in figures:
            continue
        expected = _expected_figure_visual(figures[visual.figure_ref])
        if expected is None:
            continue
        fields = [k for k, v in expected.items() if getattr(visual, k) != v]
        if fields:
            errors.append(
                f"FIGURE_COPY_MISMATCH: block {block.id!r} visual for backbone figure "
                f"'{visual.figure_ref}' differs from the figure in {fields}; copy mode, "
                "purpose, must_show and labels_required exactly from the figure."
            )
    return errors


# ---- section checks


def _draft_blocks_from_section(section: TeachingPlanSection) -> list[TeachingPlanDraftBlock]:
    return [
        TeachingPlanDraftBlock.model_validate(block.model_dump(exclude={"id", "position"}))
        for block in section.blocks
    ]


def materialize_one_section(
    spine: TeachingSpine, slot_id: str, blocks: list[TeachingPlanDraftBlock]
) -> TeachingPlanSection:
    """Materialize a single section with the exact ids the assembled plan will use."""
    section = _spine_section(spine, slot_id)
    solo = section.model_copy(update={"bridge_from_previous": None})
    solo_spine = spine.model_copy(update={"sections": [solo]})
    draft = assemble_teaching_plan_draft(solo_spine, {slot_id: list(blocks)})
    return materialize_teaching_plan(draft, slot_ids=[slot_id]).sections[0]


def section_check_errors(
    spine: TeachingSpine,
    slot_id: str,
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
    projections: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """Repair the materialized section in place, then check it.

    Returns ``(errors, flags, repairs)``. In the advisory gate only blocking issues
    are errors; the rest become flags.
    """
    spine_section = _spine_section(spine, slot_id)
    policy = projections["assessment_source_policy"]
    advisory_gate = settings.teaching_plan_quality_gate == "advisory"

    _repair_sources_outside_structural_slots_for_section(section, packet)
    _repair_incompatible_assessment_sources_for_section(section, packet)
    _repair_invalid_evidence_refs_for_section(section, packet)
    _repair_briefs_missing_anchor_grounding_for_section(section, packet)
    repairs: list[dict[str, Any]] = [
        {"repair": "missing_figure_visual", **change}
        for change in _repair_missing_figure_visuals_for_section(section, packet)
    ]
    repairs.extend(copy_backbone_figures(section, packet))

    errors: list[str] = []
    flags: list[dict[str, Any]] = []

    report = validate_teaching_section(
        section,
        packet,
        permitted_intents=set(projections["permitted_intents"]),
        excluded_intents=set(projections["excluded_intents"]),
        typical_by_slot={k: set(v) for k, v in projections["typical_by_slot"].items()},
        assessment_intents=set(policy["eligible_intents"]),
        context=TeachingValidationContext(packet),
    )
    validation = ValidationReport(ok=not any(i.blocking for i in report), issues=list(report))
    if advisory_gate:
        solo_plan = types.SimpleNamespace(sections=[section])
        flags.extend(
            advisory_issue_flags(solo_plan, validation, advisory_teaching_qc(solo_plan))
        )
        validation = apply_advisory_gate(validation)
    errors.extend(f"{i.code}: {i.message}" for i in validation.issues if i.blocking)

    errors.extend(_unknown_learner_action_errors_for_section(section))
    errors.extend(_task_source_contract_errors_for_section(section))
    errors.extend(_action_source_compatibility_errors_for_section(section, packet))
    if advisory_gate:
        flags.extend(_frozen_assessment_reuse_flags_for_section(section, packet))
    else:
        errors.extend(_frozen_assessment_reuse_errors_for_section(section, packet))

    planned = spine_section.planned_block_count
    minimum = max(1, len(spine_section.approved_item_ids))
    if not minimum <= len(section.blocks) <= planned:
        errors.append(
            f"SECTION_BLOCK_COUNT: section {slot_id} has {len(section.blocks)} blocks but "
            f"the spine allows {minimum}..{planned} (planned_block_count {planned} is a "
            f"maximum; one block per assigned approved item at least); write between "
            f"{minimum} and {planned} blocks."
        )
    for block in section.blocks:
        if len(block.source_question_ids) > 1:
            errors.append(
                f"SECTION_BLOCK_MULTIPLE_SOURCES: block {block.id!r} binds "
                f"{len(block.source_question_ids)} approved items; bind at most one item "
                "per block."
            )

    bound = [sid for block in section.blocks for sid in block.source_question_ids]
    expected_items = list(spine_section.approved_item_ids)
    missing = [i for i in expected_items if i not in bound]
    extra = sorted({i for i in bound if i not in expected_items})
    duplicated = sorted({i for i in bound if bound.count(i) > 1})
    if missing or extra or duplicated:
        parts = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"not assigned to this section {extra}")
        if duplicated:
            parts.append(f"bound more than once {duplicated}")
        errors.append(
            f"SECTION_SOURCES_MISMATCH: section {slot_id} must bind exactly its assigned "
            f"approved items {expected_items}, each in exactly one block's "
            f"source_question_ids ({'; '.join(parts)})."
        )
    if not packet.required_assessment_slots:
        # Legacy packets: check/diagnose blocks need a bound source (same rule the
        # single planner enforces after assembly).
        for block in section.blocks:
            if (
                block.intent in _LEGACY_REQUIRED_SOURCE_INTENTS
                and not block.source_question_ids
            ):
                errors.append(
                    f"SECTION_REQUIRED_SOURCE_MISSING: block {block.id!r} intent="
                    f"{block.intent!r} needs one of this section's assigned approved "
                    "items; bind it, or use a different intent when the section has "
                    "no assigned item."
                )

    present_refs = {
        block.visual.figure_ref
        for block in section.blocks
        if block.visual is not None and block.visual.figure_ref
    }
    for plan in spine_section.figure_plan:
        fid = plan.backbone_figure_id
        if fid and fid not in present_refs:
            errors.append(
                f"FIGURE_PLAN_MISSING: figure_plan includes backbone figure '{fid}' but no "
                f"block in section {slot_id} has visual.figure_ref '{fid}'; add a block "
                "whose visual draws that figure."
            )
    errors.extend(figure_copy_errors(section, packet))
    return errors, flags, repairs


# ---- orchestration


@dataclass
class SectionAttempt:
    attempt: int
    raw_response: str = ""
    errors: list[str] = field(default_factory=list)
    latency_s: float = 0.0
    error: str | None = None
    review_findings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SectionResult:
    slot_id: str
    draft: TeachingSectionDraft | None
    blocks: list[TeachingPlanDraftBlock]
    attempts: list[SectionAttempt]
    flags: list[dict[str, Any]] = field(default_factory=list)
    unresolved: bool = False
    latency_s: float = 0.0


async def plan_teaching_section(
    spine: TeachingSpine,
    slot_id: str,
    packet: ImmutableLessonPacket,
    *,
    projections: dict[str, Any],
    system_prompt: str,
    trace_id: str,
    generation_id: str | None,
    max_attempts: int = 3,
    section_reviewer: Any | None = None,
    repair_findings: list[str] | None = None,
) -> SectionResult:
    """Plan one section with checks, optional review, and up to ``max_attempts`` tries.

    ``repair_findings`` (e.g. from whole-lesson review) are attached as
    validation errors on the first attempt. On exhaustion the last parsed blocks
    ship with ``unresolved=True`` and a TEACHING_SECTION_UNRESOLVED flag.
    """
    started_all = time.perf_counter()
    base_payload = section_payload(spine, slot_id, packet, projections)
    advisory_gate = settings.teaching_plan_quality_gate == "advisory"
    attempts: list[SectionAttempt] = []
    repair_errors: list[str] = list(repair_findings or [])
    previous_output: object | None = None
    last_exception: Exception | None = None
    details: list[str] = []
    # (draft, blocks, flags, errors) of the latest attempt that parsed.
    last_parsed: tuple[TeachingSectionDraft, list[TeachingPlanDraftBlock], list[dict], list[str]] | None = None
    all_transport = True

    for attempt in range(1, max_attempts + 1):
        payload = base_payload
        if repair_errors:
            payload = {
                **base_payload,
                "repair": {
                    "instruction": SECTION_REPAIR_INSTRUCTION,
                    "previous_output": previous_output,
                    "validation_errors": repair_errors,
                },
            }
        record = SectionAttempt(attempt=attempt)
        attempts.append(record)
        started = time.perf_counter()
        raw_response = ""
        review_after: tuple[TeachingSectionDraft, TeachingPlanSection, list[dict]] | None = None
        try:
            draft, raw_response = await _call_section_model(
                system_prompt=system_prompt,
                user_payload=payload,
                trace_id=f"{trace_id}:{slot_id}:{attempt}",
                generation_id=generation_id,
                attempt_start=attempt,
            )
            record.raw_response = raw_response
            draft = TeachingSectionDraft.model_validate(
                draft.model_dump(mode="json") if hasattr(draft, "model_dump") else draft
            )
            previous_output = draft.model_dump(mode="json")
            all_transport = False
            last_exception = None
            section = materialize_one_section(spine, slot_id, list(draft.blocks))
            errors, flags, _repairs = section_check_errors(
                spine, slot_id, section, packet, projections
            )
            blocks = _draft_blocks_from_section(section)
            last_parsed = (draft, blocks, flags, errors)
            record.errors = list(errors)
            if errors:
                record.error = "validation_failed"
                repair_errors = errors
                details = errors
            else:
                review_after = (draft, section, flags)
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            record.error = str(exc)
            if is_transport_error(exc):
                repair_errors = []
            else:
                all_transport = False
                if isinstance(exc, ValidationError) or is_recognized_teaching_output_error(exc):
                    repair_errors = structured_output_errors(exc)
                    details = repair_errors
                    record.errors = repair_errors
                else:
                    # Includes UnexpectedModelBehavior (malformed output): retry, and
                    # if every attempt fails the section ships flagged, not raised.
                    repair_errors = structured_output_errors(exc)
                    record.errors = repair_errors
                    details = repair_errors
        finally:
            record.latency_s = time.perf_counter() - started

        if review_after is None:
            continue

        draft, section, flags = review_after
        blocks = _draft_blocks_from_section(section)
        if section_reviewer is not None:
            try:
                findings = list(
                    await section_reviewer(
                        spine=spine,
                        slot_id=slot_id,
                        section=section,
                        draft_blocks=blocks,
                        packet=packet,
                    )
                    or []
                )
            except Exception as exc:  # noqa: BLE001 - reviewer outage is advisory
                findings = []
                flags = [
                    *flags,
                    plan_quality_flag(
                        code="SECTION_REVIEW_UNAVAILABLE",
                        source="reviewer",
                        message=(
                            f"Section {slot_id} could not be semantically reviewed "
                            f"({type(exc).__name__}: {exc}); it passed its code checks."
                        ),
                        section_ids=[slot_id],
                        block_ids=[],
                        repair_instruction="Review this section manually before approval.",
                    ),
                ]
            record.review_findings = [
                f.model_dump(mode="json") if hasattr(f, "model_dump") else dict(f)
                for f in findings
            ]
            flagged = [
                f for f in findings if advisory_gate or f.code in ADVISORY_ONLY_SEMANTIC_CODES
            ]
            flags = [
                *flags,
                *(
                    plan_quality_flag(
                        code=f.code,
                        source="reviewer",
                        message=f.message,
                        section_ids=list(f.section_ids),
                        block_ids=list(f.block_ids),
                        repair_instruction=f.repair_instruction,
                    )
                    for f in flagged
                ),
            ]
            blocking = [f for f in findings if f not in flagged]
            if blocking:
                review_errors = [
                    f"SEMANTIC_{f.code.upper()} sections={list(f.section_ids)} "
                    f"blocks={list(f.block_ids)}: {f.repair_instruction}"
                    for f in blocking
                ]
                last_parsed = (draft, blocks, flags, review_errors)
                record.errors = review_errors
                record.error = "validation_failed"
                repair_errors = review_errors
                details = review_errors
                continue
        return SectionResult(
            slot_id=slot_id,
            draft=draft,
            blocks=blocks,
            attempts=attempts,
            flags=flags,
            unresolved=False,
            latency_s=time.perf_counter() - started_all,
        )

    if last_parsed is not None:
        draft, blocks, flags, errors = last_parsed
        flags = [
            *flags,
            plan_quality_flag(
                code="TEACHING_SECTION_UNRESOLVED",
                source="validator",
                message=(
                    f"Section {slot_id} still failed checks after {len(attempts)} attempts: "
                    + "; ".join(errors)
                ),
                section_ids=[slot_id],
                block_ids=[],
                repair_instruction="Edit this section before approval.",
            ),
        ]
        return SectionResult(
            slot_id=slot_id,
            draft=draft,
            blocks=blocks,
            attempts=attempts,
            flags=flags,
            unresolved=True,
            latency_s=time.perf_counter() - started_all,
        )
    if all_transport and last_exception is not None:
        last_exception.add_note(
            f"teaching section {slot_id} exhausted {len(attempts)} provider attempts"
        )
        raise last_exception
    # No attempt produced parseable output: ship an empty unresolved section. The
    # final gate turns issues located inside unresolved sections into flags.
    return _empty_unresolved_section(
        slot_id,
        attempts,
        reason=f"no attempt produced usable output ({'; '.join(details) or 'unknown error'})",
        latency_s=time.perf_counter() - started_all,
    )


def _empty_unresolved_section(
    slot_id: str,
    attempts: list[SectionAttempt],
    *,
    reason: str,
    latency_s: float,
) -> SectionResult:
    """Zero-block unresolved section carrying a TEACHING_SECTION_UNRESOLVED flag."""
    return SectionResult(
        slot_id=slot_id,
        draft=None,
        blocks=[],
        attempts=attempts,
        flags=[
            plan_quality_flag(
                code="TEACHING_SECTION_UNRESOLVED",
                source="validator",
                message=f"Section {slot_id} has no blocks: {reason}",
                section_ids=[slot_id],
                block_ids=[],
                repair_instruction="Write this section's blocks before approval.",
            )
        ],
        unresolved=True,
        latency_s=latency_s,
    )


async def plan_teaching_sections(
    spine: TeachingSpine,
    packet: ImmutableLessonPacket,
    *,
    projections: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
    section_reviewer: Any | None = None,
    max_attempts: int = 3,
) -> dict[str, SectionResult]:
    """Run every section call in parallel and flag, don't fail.

    A section that exhausts its retries, or whose call raises unexpectedly, becomes an
    unresolved flagged section (zero blocks when nothing usable came back). The one
    exception: when EVERY section failed with a transport/provider error the provider
    is down, so the first such error is re-raised for the work-item retry to handle.
    """
    system_prompt = render_staged_prompt(
        packet, projections.get("teaching_guidance"), kind="section"
    )
    slot_ids = [section.slot_id for section in spine.sections]
    results = await asyncio.gather(
        *(
            plan_teaching_section(
                spine,
                slot_id,
                packet,
                projections=projections,
                system_prompt=system_prompt,
                trace_id=trace_id,
                generation_id=generation_id,
                max_attempts=max_attempts,
                section_reviewer=section_reviewer,
            )
            for slot_id in slot_ids
        ),
        return_exceptions=True,
    )
    for outcome in results:
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome  # cancellation etc.
    failures = [o for o in results if isinstance(o, Exception)]
    if failures and len(failures) == len(results) and all(
        is_transport_error(f) for f in failures
    ):
        raise failures[0]
    out: dict[str, SectionResult] = {}
    for slot_id, outcome in zip(slot_ids, results, strict=True):
        if isinstance(outcome, Exception):
            out[slot_id] = _empty_unresolved_section(
                slot_id,
                [SectionAttempt(attempt=1, error=f"{type(outcome).__name__}: {outcome}")],
                reason=f"{type(outcome).__name__}: {outcome}",
                latency_s=0.0,
            )
        else:
            out[slot_id] = outcome
    return out


# --------------------------------------------------------------------------- assembly (phases 5-6)


def _solo_plan_and_draft(
    spine: TeachingSpine, slot_id: str, blocks: list[TeachingPlanDraftBlock]
) -> tuple[TeachingPlan, TeachingPlanDraftV2]:
    """One-section TeachingPlan (v2) plus its draft, with the final plan's block ids."""
    section = _spine_section(spine, slot_id)
    solo = section.model_copy(update={"bridge_from_previous": None})
    solo_spine = spine.model_copy(update={"sections": [solo]})
    draft = assemble_teaching_plan_draft(solo_spine, {slot_id: list(blocks)})
    return materialize_teaching_plan(draft, slot_ids=[slot_id]), draft


def _lesson_context(packet: ImmutableLessonPacket) -> dict[str, Any]:
    """Reviewer context, same as the single planner (frozen stems alongside ids)."""
    return {
        **packet.planner_payload(),
        "approved_items": [{"id": item.id, "stem": item.stem} for item in packet.approved_items],
    }


def configured_section_reviewer(*, trace_id: str, generation_id: str | None):
    """Per-section reviewer when ``staged_section_review`` is on, else ``None``."""
    if not settings.staged_section_review:
        return None
    return make_section_reviewer(trace_id=trace_id, generation_id=generation_id)


def make_section_reviewer(*, trace_id: str, generation_id: str | None):
    """Adapter matching ``plan_teaching_section``'s ``section_reviewer`` call."""

    async def section_reviewer(
        *,
        spine: TeachingSpine,
        slot_id: str,
        section: TeachingPlanSection,
        draft_blocks: list[TeachingPlanDraftBlock],
        packet: ImmutableLessonPacket,
    ) -> list[TeachingPlanSemanticFinding]:
        del section  # the draft blocks are derived from it; ids come from materialization
        plan, draft = _solo_plan_and_draft(spine, slot_id, draft_blocks)
        return await review_teaching_section(
            spine=spine,
            slot_id=slot_id,
            section_plan=plan,
            section_draft=draft,
            lesson_context=_lesson_context(packet),
            trace_id=f"{trace_id}:section-review:{slot_id}",
            generation_id=generation_id,
        )

    return section_reviewer


def _flag_key(flag: dict[str, Any]) -> tuple[Any, ...]:
    return (
        flag.get("code"),
        flag.get("source"),
        tuple(flag.get("section_ids") or ()),
        tuple(flag.get("block_ids") or ()),
        flag.get("message"),
    )


def _dedupe_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for flag in flags:
        key = _flag_key(flag)
        if key not in seen:
            seen.add(key)
            out.append(flag)
    return out


def _finding_flag(finding: TeachingPlanSemanticFinding, *, prefix: str = "") -> dict[str, Any]:
    return plan_quality_flag(
        code=finding.code,
        source="reviewer",
        message=f"{prefix}{finding.message}",
        section_ids=list(finding.section_ids),
        block_ids=list(finding.block_ids),
        repair_instruction=finding.repair_instruction,
    )


def _split_findings(
    findings: list[TeachingPlanSemanticFinding], *, advisory_gate: bool
) -> tuple[list[TeachingPlanSemanticFinding], list[TeachingPlanSemanticFinding]]:
    """(flagged, blocking): advisory gate or advisory-only codes never block."""
    flagged = [f for f in findings if advisory_gate or f.code in ADVISORY_ONLY_SEMANTIC_CODES]
    blocking = [f for f in findings if f not in flagged]
    return flagged, blocking


_ERROR_BLOCK_RE = re.compile(r"block '([^']+)'")
_ERROR_SLOT_RE = re.compile(r"slot '([^']+)'")


def _error_sections(error: str, plan: TeachingPlan) -> list[str]:
    """Section ids an ownership error text points at (by block id or slot id)."""
    block_to_slot = {b.id: s.slot_id for s in plan.sections for b in s.blocks}
    slots = {s.slot_id for s in plan.sections}
    found: list[str] = []
    for match in _ERROR_BLOCK_RE.finditer(error):
        slot = block_to_slot.get(match.group(1))
        if slot and slot not in found:
            found.append(slot)
    for match in _ERROR_SLOT_RE.finditer(error):
        if match.group(1) in slots and match.group(1) not in found:
            found.append(match.group(1))
    return found


def _error_blocks(error: str, plan: TeachingPlan) -> list[str]:
    ids = {b.id for s in plan.sections for b in s.blocks}
    return [m.group(1) for m in _ERROR_BLOCK_RE.finditer(error) if m.group(1) in ids]


def _assemble_and_materialize(
    spine: TeachingSpine,
    sections: dict[str, SectionResult],
    packet: ImmutableLessonPacket,
    assessment_intents: set[str],
) -> tuple[TeachingPlanDraftV2, TeachingPlan, list[str]]:
    """Assemble, materialize, and run the assessment-source safety net.

    The repair runs before any review so the reviewed plan hash is the final one.
    """
    slot_ids = [slot.slot_id for slot in packet.slots]
    try:
        draft = assemble_teaching_plan_draft(
            spine, {slot_id: result.blocks for slot_id, result in sections.items()}
        )
        plan = materialize_teaching_plan(draft, slot_ids=slot_ids)
    except ValueError as exc:
        raise TeachingPlanOutputInvalidError(
            attempt_count=sum(len(r.attempts) for r in sections.values()),
            details=[str(exc)],
        ) from exc
    ownership_errors = _repair_missing_assessment_sources(plan, packet, assessment_intents)
    return draft, plan, ownership_errors


async def _review_lesson_safe(
    *,
    spine: TeachingSpine,
    plan: TeachingPlan,
    draft: TeachingPlanDraftV2,
    packet: ImmutableLessonPacket,
    trace_id: str,
    generation_id: str | None,
) -> tuple[TeachingPlanSemanticReviewResult | None, dict[str, Any] | None]:
    """Whole-lesson review that never fails the plan.

    Returns ``(result, None)`` or ``(None, advisory LESSON_REVIEW_UNAVAILABLE flag)``
    when the reviewer errors or times out.
    """
    try:
        return (
            await _review_lesson_bound(
                spine=spine,
                plan=plan,
                draft=draft,
                packet=packet,
                trace_id=trace_id,
                generation_id=generation_id,
            ),
            None,
        )
    except Exception as exc:  # noqa: BLE001 - reviewer outage is advisory
        return None, plan_quality_flag(
            code="LESSON_REVIEW_UNAVAILABLE",
            source="reviewer",
            message=(
                "The whole-lesson semantic review could not run "
                f"({type(exc).__name__}: {exc}); the plan passed its code checks."
            ),
            section_ids=[],
            block_ids=[],
            repair_instruction="Read the plan end to end before approving it.",
        )


async def _review_lesson_bound(
    *,
    spine: TeachingSpine,
    plan: TeachingPlan,
    draft: TeachingPlanDraftV2,
    packet: ImmutableLessonPacket,
    trace_id: str,
    generation_id: str | None,
) -> TeachingPlanSemanticReviewResult:
    result = await review_teaching_lesson(
        spine=spine,
        plan=plan,
        draft=draft,
        lesson_context=_lesson_context(packet),
        trace_id=trace_id,
        generation_id=generation_id,
        include_section_codes=not settings.staged_section_review,
    )
    if result.content_hash != teaching_plan_content_hash(plan):
        raise TeachingPlanSemanticReviewError(
            "TEACHING_SEMANTIC_REVIEW_INVALID",
            "Teaching Plan semantic review is not bound to this candidate",
        )
    return result


def _serialize_attempts(attempts: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "attempt": a.attempt,
            "raw_response": a.raw_response,
            "errors": list(a.errors),
            "latency_s": a.latency_s,
            "error": a.error,
            **({"review_findings": list(a.review_findings)} if hasattr(a, "review_findings") else {}),
        }
        for a in attempts
    ]


def spine_result_to_json(result: SpineResult) -> dict[str, Any]:
    """JSON form of a spine stage result (stored as work-item ``output_json``)."""
    return {
        "spine": result.spine.model_dump(mode="json"),
        "draft": result.draft.model_dump(mode="json"),
        "attempts": _serialize_attempts(result.attempts),
        "repairs": list(result.repairs),
    }


def spine_result_from_json(data: dict[str, Any]) -> SpineResult:
    return SpineResult(
        spine=TeachingSpine.model_validate(data["spine"]),
        draft=TeachingSpineDraft.model_validate(data["draft"]),
        attempts=[SpineAttempt(**a) for a in data.get("attempts", [])],
        repairs=list(data.get("repairs", [])),
    )


def section_result_to_json(result: SectionResult) -> dict[str, Any]:
    """JSON form of a section stage result (stored as work-item ``output_json``)."""
    return {
        "slot_id": result.slot_id,
        "draft": result.draft.model_dump(mode="json") if result.draft is not None else None,
        "blocks": [b.model_dump(mode="json") for b in result.blocks],
        "attempts": _serialize_attempts(result.attempts),
        "flags": list(result.flags),
        "unresolved": result.unresolved,
        "latency_s": result.latency_s,
    }


def section_result_from_json(data: dict[str, Any]) -> SectionResult:
    draft = data.get("draft")
    return SectionResult(
        slot_id=data["slot_id"],
        draft=TeachingSectionDraft.model_validate(draft) if draft is not None else None,
        blocks=[TeachingPlanDraftBlock.model_validate(b) for b in data.get("blocks", [])],
        attempts=[SectionAttempt(**a) for a in data.get("attempts", [])],
        flags=list(data.get("flags", [])),
        unresolved=bool(data.get("unresolved", False)),
        latency_s=float(data.get("latency_s", 0.0)),
    )


async def run_spine_stage(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
    *,
    trace_id: str,
    generation_id: str | None = None,
) -> SpineResult:
    """Spine stage on its own (one work item in the staged preparation run)."""
    projections = build_planner_projections(packet, snapshot)
    return await plan_teaching_spine(
        packet,
        snapshot=snapshot,
        teaching_guidance=projections["teaching_guidance"],
        slot_intent_policy=projections["slot_intent_policy"],
        assessment_source_policy=projections["assessment_source_policy"],
        trace_id=trace_id,
        generation_id=generation_id,
    )


async def run_section_stage(
    spine: TeachingSpine,
    slot_id: str,
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
    *,
    trace_id: str,
    generation_id: str | None = None,
) -> SectionResult:
    """One section (with its own review and retries) as a standalone stage."""
    projections = build_planner_projections(packet, snapshot)
    return await plan_teaching_section(
        spine,
        slot_id,
        packet,
        projections=projections,
        system_prompt=render_staged_prompt(
            packet, projections.get("teaching_guidance"), kind="section"
        ),
        trace_id=trace_id,
        generation_id=generation_id,
        section_reviewer=configured_section_reviewer(
            trace_id=trace_id, generation_id=generation_id
        ),
    )


async def run_staged_teaching_planner(
    packet: ImmutableLessonPacket,
    *,
    legality: LessonLegalitySnapshot | None = None,
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
) -> TeachingPlanResult:
    """Spine -> parallel sections -> assembly -> whole-lesson review -> final gate.

    Same signature and result type as ``run_lesson_approach_planner``. Sections that
    exhaust their retries ship flagged (flag, don't fail); blocking whole-lesson
    findings get one bounded fix round on the named sections only.
    """
    if require_items and not packet.approved_items:
        from curriculum.approved_items import ItemPoolEmptyError

        raise ItemPoolEmptyError(card_id="unknown", pack_id=None)

    started_all = time.perf_counter()
    snapshot = legality or build_lesson_legality_snapshot(packet)
    projections = build_planner_projections(packet, snapshot)
    tid = trace_id or str(uuid.uuid4())

    # Spine.
    spine_started = time.perf_counter()
    spine_result = await plan_teaching_spine(
        packet,
        snapshot=snapshot,
        teaching_guidance=projections["teaching_guidance"],
        slot_intent_policy=projections["slot_intent_policy"],
        assessment_source_policy=projections["assessment_source_policy"],
        trace_id=tid,
        generation_id=generation_id,
    )
    spine_s = time.perf_counter() - spine_started

    # Sections (parallel; each reviewed on its own, retried alone).
    reviewer = configured_section_reviewer(trace_id=tid, generation_id=generation_id)
    sections_started = time.perf_counter()
    sections = await plan_teaching_sections(
        spine_result.spine,
        packet,
        projections=projections,
        trace_id=tid,
        generation_id=generation_id,
        section_reviewer=reviewer,
    )
    sections_s = time.perf_counter() - sections_started
    return await finish_staged_plan(
        packet,
        snapshot,
        spine_result,
        sections,
        trace_id=tid,
        generation_id=generation_id,
        started_all=started_all,
        spine_s=spine_s,
        sections_s=sections_s,
    )


async def finish_staged_plan(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
    spine_result: SpineResult,
    sections: dict[str, SectionResult],
    *,
    trace_id: str,
    generation_id: str | None = None,
    started_all: float | None = None,
    spine_s: float | None = None,
    sections_s: float | None = None,
) -> TeachingPlanResult:
    """Assemble, whole-lesson review (+ one fix round) and final gate.

    Works from stage results, so it also runs from work-item outputs.
    """
    started_all = time.perf_counter() if started_all is None else started_all
    spine_s = (
        sum(a.latency_s for a in spine_result.attempts) if spine_s is None else spine_s
    )
    sections_s = (
        max((r.latency_s for r in sections.values()), default=0.0)
        if sections_s is None
        else sections_s
    )
    sections = dict(sections)
    spine = spine_result.spine
    tid = trace_id
    projections = build_planner_projections(packet, snapshot)
    teaching_guidance: TeachingGuidanceProjection = projections["teaching_guidance"]
    permitted = projections["permitted_intents"]
    excluded = projections["excluded_intents"]
    typical_by_slot = projections["typical_by_slot"]
    assessment_intents = set(projections["assessment_source_policy"]["eligible_intents"])
    advisory_gate = settings.teaching_plan_quality_gate == "advisory"
    spine_prompt = render_staged_prompt(packet, teaching_guidance, kind="spine")
    reviewer = configured_section_reviewer(trace_id=tid, generation_id=generation_id)
    extra_attempts: list[tuple[str, SectionAttempt]] = []

    # Assembly + whole-lesson review.
    draft, plan, ownership_errors = _assemble_and_materialize(
        spine, sections, packet, assessment_intents
    )
    review_started = time.perf_counter()
    lesson_review: TeachingPlanSemanticReviewResult | None = None
    review_state = "skipped"
    review_flags: list[dict[str, Any]] = []
    if settings.staged_lesson_review:
        lesson_review, unavailable = await _review_lesson_safe(
            spine=spine,
            plan=plan,
            draft=draft,
            packet=packet,
            trace_id=f"{tid}:lesson-review",
            generation_id=generation_id,
        )
        review_state = "ran"
        if unavailable is not None:
            review_state = "unavailable"
            review_flags.append(unavailable)
    review_s = time.perf_counter() - review_started
    first_findings = lesson_review.findings if lesson_review is not None else []
    flagged, blocking = _split_findings(first_findings, advisory_gate=advisory_gate)
    first_blocking_count = len(blocking)
    review_flags.extend(_finding_flag(f) for f in flagged)
    review_unresolved: set[str] = set()
    timings_fix: dict[str, Any] = {}
    final_review = lesson_review

    if blocking:
        fix_started = time.perf_counter()
        targets: dict[str, list[str]] = {}
        for finding in blocking:
            for slot_id in finding.section_ids:
                if slot_id in sections:
                    targets.setdefault(slot_id, []).append(
                        f"SEMANTIC_{finding.code.upper()} sections={list(finding.section_ids)} "
                        f"blocks={list(finding.block_ids)}: {finding.repair_instruction}"
                    )
        fix_note = "Still unresolved after one fix round: "
        replaced: list[str] = []
        if targets:
            section_prompt = render_staged_prompt(packet, teaching_guidance, kind="section")
            fixed = await asyncio.gather(
                *(
                    plan_teaching_section(
                        spine,
                        slot_id,
                        packet,
                        projections=projections,
                        system_prompt=section_prompt,
                        trace_id=f"{tid}:fix",
                        generation_id=generation_id,
                        section_reviewer=reviewer,
                        repair_findings=repair_findings,
                    )
                    for slot_id, repair_findings in targets.items()
                ),
                return_exceptions=True,
            )
            for slot_id, outcome in zip(targets, fixed, strict=True):
                if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
                    raise outcome
                if isinstance(outcome, Exception):
                    # Keep the section that already passed its own checks.
                    extra_attempts.append(
                        (slot_id, SectionAttempt(attempt=0, error=f"fix round failed: {outcome}"))
                    )
                    continue
                extra_attempts.extend((slot_id, a) for a in outcome.attempts)
                if outcome.unresolved:
                    continue  # the earlier version passed section checks; keep it
                sections[slot_id] = outcome
                replaced.append(slot_id)
        if replaced:
            draft, plan, ownership_errors = _assemble_and_materialize(
                spine, sections, packet, assessment_intents
            )
            final_review, unavailable = await _review_lesson_safe(
                spine=spine,
                plan=plan,
                draft=draft,
                packet=packet,
                trace_id=f"{tid}:lesson-review2",
                generation_id=generation_id,
            )
            second_findings = final_review.findings if final_review is not None else []
            flagged, blocking = _split_findings(second_findings, advisory_gate=advisory_gate)
            review_flags = [_finding_flag(f) for f in flagged]
            if unavailable is not None:
                review_flags.append(unavailable)
        for finding in blocking:
            review_flags.append(_finding_flag(finding, prefix=fix_note))
            review_unresolved.update(s for s in finding.section_ids if s in sections)
        timings_fix = {
            "latency_s": round(time.perf_counter() - fix_started, 4),
            "sections": list(targets),
            "replaced": replaced,
            "unresolved_after": sorted(review_unresolved),
        }

    # Final safety net on the final plan (no mutation after this point).
    ownership_errors = list(ownership_errors)
    ownership_errors.extend(_unknown_learner_action_errors(plan))
    ownership_errors.extend(_task_source_contract_errors(plan))
    ownership_errors.extend(_action_source_compatibility_errors(plan, packet))
    flags: list[dict[str, Any]] = []
    for result in sections.values():
        flags.extend(result.flags)
    flags.extend(review_flags)
    if advisory_gate:
        flags.extend(_frozen_assessment_reuse_flags(plan, packet))
    else:
        ownership_errors.extend(_frozen_assessment_reuse_errors(plan, packet))
    validation = validate_teaching_plan(
        plan,
        packet,
        permitted_intents=permitted,
        excluded_intents=excluded,
        typical_by_slot=typical_by_slot,
        assessment_intents=assessment_intents,
    )
    qc_findings = advisory_teaching_qc(plan)
    if advisory_gate:
        flags.extend(advisory_issue_flags(plan, validation, qc_findings))
        validation = apply_advisory_gate(validation)

    unresolved_sections = {s for s, r in sections.items() if r.unresolved} | review_unresolved
    failing: list[str] = []
    gate_issues: list[ValidationIssue] = []
    for issue in validation.issues:
        if issue.blocking:
            located, blocks = _flag_locations(plan, issue.path)
            if located and set(located) <= unresolved_sections:
                flags.append(
                    plan_quality_flag(
                        code=issue.code,
                        source="validator",
                        message=issue.message,
                        section_ids=located,
                        block_ids=blocks,
                    )
                )
                issue = ValidationIssue(
                    code=issue.code, message=issue.message, path=issue.path, blocking=False
                )
            else:
                failing.append(f"{issue.code}: {issue.message}")
        gate_issues.append(issue)
    for error in ownership_errors:
        located = _error_sections(error, plan)
        if located and set(located) <= unresolved_sections:
            flags.append(
                plan_quality_flag(
                    code=error.split(":", 1)[0].strip() or "TEACHING_OWNERSHIP",
                    source="validator",
                    message=error,
                    section_ids=located,
                    block_ids=_error_blocks(error, plan),
                )
            )
        else:
            failing.append(error)
    if failing:
        raise TeachingPlanOutputInvalidError(
            attempt_count=len(spine_result.attempts)
            + sum(len(r.attempts) for r in sections.values())
            + len(extra_attempts),
            details=failing,
        )
    validation = ValidationReport(ok=True, issues=gate_issues)

    if final_review is not None and final_review.content_hash != teaching_plan_content_hash(
        plan
    ):
        raise TeachingPlanSemanticReviewError(
            "TEACHING_SEMANTIC_REVIEW_INVALID",
            "Teaching Plan semantic review is not bound to the final plan",
        )
    qc = [finding.to_dict() for finding in qc_findings]
    if final_review is not None:
        qc.append(
            {
                "code": "TEACHING_PLAN_SEMANTIC_REVIEW_PASS",
                "content_hash": final_review.content_hash,
            }
        )
    else:
        qc.append({"code": "TEACHING_PLAN_SEMANTIC_REVIEW_SKIPPED", "state": review_state})

    # Attempts: spine tries, then section tries, then the final assembled plan.
    section_prompt_text = render_staged_prompt(packet, teaching_guidance, kind="section")
    attempts: list[TeachingPlanAttempt] = []

    def _add(prompt: str, raw: str, error: str | None, *, assembled: bool = False) -> None:
        attempts.append(
            TeachingPlanAttempt(
                prompt=prompt,
                raw_response=raw,
                plan=plan if assembled else None,
                validation=validation if assembled else ValidationReport(ok=False, issues=[]),
                qc=qc if assembled else [],
                attempt=len(attempts) + 1,
                error=error,
                semantic_review=final_review if assembled else None,
            )
        )

    for rec in spine_result.attempts:
        _add(spine_prompt, rec.raw_response, rec.error)
    for slot_id, result in sections.items():
        for rec in result.attempts:
            _add(section_prompt_text, rec.raw_response, rec.error)
    for _slot_id, rec in extra_attempts:
        _add(section_prompt_text, rec.raw_response, rec.error)
    _add(spine_prompt, "", None, assembled=True)

    raw_response = json.dumps(
        {
            "spine": [a.raw_response for a in spine_result.attempts],
            "sections": {
                slot_id: [a.raw_response for a in result.attempts]
                for slot_id, result in sections.items()
            },
        }
    )
    stage_timings: dict[str, Any] = {
        "total_s": round(time.perf_counter() - started_all, 4),
        "spine": {
            "wall_s": round(spine_s, 4),
            "latency_s": round(sum(a.latency_s for a in spine_result.attempts), 4),
            "attempts": len(spine_result.attempts),
        },
        "sections_wall_s": round(sections_s, 4),
        "sections": {
            slot_id: {
                "latency_s": round(result.latency_s, 4),
                "attempts": len(result.attempts),
                "unresolved": result.unresolved,
            }
            for slot_id, result in sections.items()
        },
        "lesson_review": {
            "latency_s": round(review_s, 4),
            "state": review_state,
            "findings": len(first_findings),
            "blocking": first_blocking_count,
        },
        "fix_round": timings_fix,
        "fix_round_attempts": len(extra_attempts),
        "flags": len(_dedupe_flags(flags)),
    }
    return TeachingPlanResult(
        plan=plan,
        validation=validation,
        qc=qc,
        prompt=spine_prompt,
        raw_response=raw_response,
        teaching_guidance=teaching_guidance,
        attempts=attempts,
        typical_by_slot=typical_by_slot,
        permitted_intents=permitted,
        excluded_intents=excluded,
        legality=snapshot,
        semantic_review=final_review,
        flags=_dedupe_flags(flags),
        stage_timings=stage_timings,
    )


__all__ = [
    "SectionAttempt",
    "SectionResult",
    "SpineAttempt",
    "SpineResult",
    "build_planner_projections",
    "copy_backbone_figures",
    "figure_copy_errors",
    "materialize_one_section",
    "plan_teaching_section",
    "plan_teaching_sections",
    "plan_teaching_spine",
    "make_section_reviewer",
    "render_staged_prompt",
    "finish_staged_plan",
    "run_section_stage",
    "run_spine_stage",
    "run_staged_teaching_planner",
    "section_result_from_json",
    "section_result_to_json",
    "spine_result_from_json",
    "spine_result_to_json",
    "repair_spine_figure_plan",
    "section_check_errors",
    "section_payload",
    "spine_check_errors",
    "repair_spine_state_chain",
]

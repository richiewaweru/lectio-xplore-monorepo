"""Staged teaching planner: prompt rendering and the spine call (phase 3).

The spine fixes lesson-wide structure (titles, state chain, item and
misconception placement, figure plan, block budget). Code checks it, repairs
what is deterministic, and retries the spine alone with the errors attached.
"""

from __future__ import annotations

import asyncio
import json
import time
import types
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError
from pydantic_ai import Agent

from application.unit_lesson.teaching_planner import (
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
from curriculum.teaching_plan.models import (
    TeachingPlanDraftBlock,
    TeachingPlanSection,
    VisualSpec,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.semantic_review import ADVISORY_ONLY_SEMANTIC_CODES
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
    ValidationReport,
    advisory_issue_flags,
    advisory_teaching_qc,
    apply_advisory_gate,
    plan_quality_flag,
    validate_teaching_section,
)
from resource_specs.loader import get_spec
from resource_specs.renderer import render_lesson_design_guidance, render_resource_identity

SECTION_REPAIR_INSTRUCTION = (
    "Return the complete corrected section JSON (blocks only). Change only what is "
    "required to satisfy these errors and keep everything else as it was. Write "
    "exactly planned_block_count blocks. Bind each assigned approved item to exactly "
    "one block, copying ids verbatim, and bind nothing else. Copy every backbone "
    "figure in figure_plan into a block's visual with figure_ref set to its id."
)

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
        "planned_block_count": section.planned_block_count,
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
    if len(section.blocks) != planned:
        errors.append(
            f"SECTION_BLOCK_COUNT: section {slot_id} has {len(section.blocks)} blocks but "
            f"the spine plans exactly {planned}; write exactly {planned} blocks."
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
                    from pydantic_ai.exceptions import UnexpectedModelBehavior

                    if isinstance(exc, UnexpectedModelBehavior):
                        raise
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
    raise TeachingPlanOutputInvalidError(
        attempt_count=len(attempts), details=details
    ) from last_exception


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
    """Run every section call in parallel; exhaustion flags a section, never raises."""
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
        )
    )
    return dict(zip(slot_ids, results, strict=True))


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
    "render_staged_prompt",
    "repair_spine_figure_plan",
    "section_check_errors",
    "section_payload",
    "spine_check_errors",
]

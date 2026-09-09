"""Native Print production adapter: approved teaching → closed forms → work orders.

Bridges P04 closed selection into the whole-lesson executor path without
substituting prepared teaching/form plans. Provider fakes remain allowed only
at LLM call sites; this module is code-owned selection and persistence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from curriculum.teaching_plan.models import TeachingPlan
from print.generation.catalogue_projections import build_form_candidate_map
from print.generation.selection_snapshot import (
    PrintSelectionSnapshot,
    build_print_selection_snapshot,
    form_plan_from_decisions,
    select_print_deterministically,
    snapshot_from_form_plan,
)
from print.generation.work_orders import PrintWorkOrder, compile_print_work_orders
from print.generation.whole_lesson.form_plan import FormPlan
from print.generation.whole_lesson.legality import LessonLegalitySnapshot
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from print.resources.native_policy import (
    default_print_policy,
    policy_version_and_hash,
)
from print.resources.selection import load_form_selection_view


def teaching_plan_content_hash(plan: TeachingPlan | Mapping[str, Any]) -> str:
    """Stable hash of teaching meaning (identity fields excluded from body hash)."""
    if isinstance(plan, TeachingPlan):
        payload = plan.model_dump(mode="json")
    else:
        payload = dict(plan)
    body = {
        "arc": payload.get("arc"),
        "sections": payload.get("sections"),
        "anchor_usage": payload.get("anchor_usage"),
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def package_contract_hash() -> str:
    view = load_form_selection_view()
    raw = json.dumps(view, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prefer_figure_for_visual_slots(
    teaching_plan: TeachingPlan,
    decisions: list[Any],
    *,
    required_visual_slots: set[str],
    candidate_map: Mapping[str, Sequence[str]],
) -> list[Any]:
    """Keep stable order; prefer figure for visual slots / visual intents."""
    block_meta = {
        block.id: (section.slot_id, block.intent)
        for section in teaching_plan.sections
        for block in section.blocks
    }
    visual_intents = {"illustrate", "show-structure", "show-process"}
    # Prefer readable defaults when the closed set allows multiple forms.
    preference = (
        "figure",
        "choices",
        "questions",
        "prose",
        "worked-example",
        "table",
        "list",
        "aside",
    )
    out = []
    for decision in decisions:
        slot, intent = block_meta.get(decision.block_id, (None, None))
        allowed = [str(item) for item in (candidate_map.get(decision.block_id) or ())]
        chosen = decision.form_id
        if slot in required_visual_slots and "figure" in allowed:
            chosen = "figure"
            reason = "required visual slot prefers figure"
        elif intent in visual_intents and "figure" in allowed:
            chosen = "figure"
            reason = "visual intent prefers figure"
        else:
            for form_id in preference:
                if form_id in allowed:
                    chosen = form_id
                    break
            reason = f"closed preference selected {chosen}"
        if chosen != decision.form_id:
            out.append(
                decision.model_copy(
                    update={"form_id": chosen, "reason": reason}
                )
            )
        else:
            out.append(decision)
    return out


def build_closed_print_production_plan(
    *,
    teaching_plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    legality: LessonLegalitySnapshot,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> tuple[FormPlan, PrintSelectionSnapshot, list[PrintWorkOrder]]:
    """Closed selection + work orders from an approved shared teaching plan."""
    body = dict(policy) if policy is not None else default_print_policy()
    _, policy_hash = policy_version_and_hash(body)
    assets = [str(item) for item in (available_asset_ids or ()) if item]
    # Required visuals may be selected before raster assets exist. The writer
    # then records visual_pending / FIGURES_NOT_READY rather than a blank success.
    if packet.required_visual_slots() and not assets:
        assets = [f"deferred-visual:{packet.lesson.path_lesson_id}"]
    # Visual intents (illustrate / show-structure) also need figure eligibility.
    has_visual_intent = any(
        block.intent in {"illustrate", "show-structure", "show-process"}
        for section in teaching_plan.sections
        for block in section.blocks
    )
    if has_visual_intent and not assets:
        assets = [f"deferred-visual:{packet.lesson.path_lesson_id}"]
    candidate_map = build_form_candidate_map(
        teaching_plan,
        compatible_objects_by_intent=legality.compatible_objects_by_intent,
        approved_items=packet.approved_items,
        available_asset_ids=assets,
        policy=body,
    )
    decisions = select_print_deterministically(
        teaching_plan, candidate_map=candidate_map
    )
    decisions = prefer_figure_for_visual_slots(
        teaching_plan,
        decisions,
        required_visual_slots=set(packet.required_visual_slots()),
        candidate_map=candidate_map,
    )
    plan_hash = teaching_plan_content_hash(teaching_plan)
    snapshot = build_print_selection_snapshot(
        teaching_plan,
        candidate_map=candidate_map,
        teaching_plan_hash=plan_hash,
        native_policy_hash=policy_hash,
        package_contract_hash=package_contract_hash(),
        decisions=decisions,
    )
    form_plan = form_plan_from_decisions(teaching_plan, snapshot.decisions)
    orders = compile_print_work_orders(
        teaching_plan=teaching_plan, snapshot=snapshot
    )
    return form_plan, snapshot, orders


def compile_print_work_orders_for_form_plan(
    *,
    teaching_plan: TeachingPlan,
    form_plan: FormPlan,
    policy: Mapping[str, Any] | None = None,
) -> list[PrintWorkOrder]:
    """Reconstruct selected work orders for a validated/reused Print form plan."""
    body = dict(policy) if policy is not None else default_print_policy()
    _, policy_hash = policy_version_and_hash(body)
    candidate_map = {
        decision.block_id: [decision.object]
        for section in form_plan.sections
        for decision in section.forms
    }
    snapshot = snapshot_from_form_plan(
        teaching_plan=teaching_plan,
        form_plan=form_plan,
        candidate_map=candidate_map,
        teaching_plan_hash=teaching_plan_content_hash(teaching_plan),
        native_policy_hash=policy_hash,
        package_contract_hash=package_contract_hash(),
    )
    return compile_print_work_orders(teaching_plan=teaching_plan, snapshot=snapshot)


def selection_trace_payload(
    snapshot: PrintSelectionSnapshot,
    orders: Sequence[PrintWorkOrder],
) -> dict[str, Any]:
    return {
        "selection_snapshot": snapshot.model_dump(mode="json"),
        "work_orders": [order.model_dump(mode="json") for order in orders],
        "work_order_ids": [order.work_order_id for order in orders],
    }


__all__ = [
    "build_closed_print_production_plan",
    "compile_print_work_orders_for_form_plan",
    "package_contract_hash",
    "prefer_figure_for_visual_slots",
    "selection_trace_payload",
    "teaching_plan_content_hash",
]

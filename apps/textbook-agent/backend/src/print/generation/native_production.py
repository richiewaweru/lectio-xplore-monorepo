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
from infra.authoring.capability_selector import ChooseFn
from print.generation.catalogue_projections import build_form_candidate_map
from print.generation.document_realizer import produce_print_document_plan_from_teaching
from print.generation.selection_snapshot import (
    PrintSelectionSnapshot,
    build_print_selection_snapshot_async,
    form_plan_from_decisions,
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


async def build_closed_print_production_plan_async(
    *,
    teaching_plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    legality: LessonLegalitySnapshot,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    choose: ChooseFn | None = None,
    sealed_form_plan: FormPlan | None = None,
    provider: Any | None = None,
    engine: Any | None = None,
    use_document_composition: bool = True,
) -> tuple[FormPlan, PrintSelectionSnapshot, list[PrintWorkOrder]]:
    """Build Print FormPlan from shared document composition (canonical).

    When ``use_document_composition`` is True (default), ordinary content
    selection uses ``document.composer`` + Print task treatments — not the
    closed catalogue LLM form selector. FormPlan remains the Print layout
    carrier for writers/assembly.
    """
    body = dict(policy) if policy is not None else default_print_policy()
    _, policy_hash = policy_version_and_hash(body)
    assets = [str(item) for item in (available_asset_ids or ()) if item]
    if packet.required_visual_slots() and not assets:
        assets = [f"deferred-visual:{packet.lesson.path_lesson_id}"]
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
    plan_hash = teaching_plan_content_hash(teaching_plan)
    if sealed_form_plan is not None:
        snapshot = snapshot_from_form_plan(
            teaching_plan=teaching_plan,
            form_plan=sealed_form_plan,
            candidate_map=candidate_map,
            teaching_plan_hash=plan_hash,
            native_policy_hash=policy_hash,
            package_contract_hash=package_contract_hash(),
        )
        form_plan = sealed_form_plan
    elif use_document_composition:
        from print.generation.composition_bridge import (
            build_print_production_from_composition,
        )

        form_plan, snapshot, _composition = await build_print_production_from_composition(
            teaching_plan=teaching_plan,
            provider=provider,
            engine=engine,
            policy=body,
            allow_heuristic_fallback=True,
            candidate_map=candidate_map,
        )
        _ = choose  # catalogue choose unused when composition owns ordinary selection
    else:
        # Legacy closed catalogue selection — kept for salvage/tests only.
        lesson = packet.lesson
        lesson_title = getattr(lesson, "objective", None) or getattr(lesson, "title", None) or ""
        teaching_context = {
            "arc": teaching_plan.arc,
            "lesson_title": lesson_title,
            "subject": getattr(lesson, "subject", None) or "",
        }
        snapshot = await build_print_selection_snapshot_async(
            teaching_plan,
            candidate_map=candidate_map,
            teaching_plan_hash=plan_hash,
            native_policy_hash=policy_hash,
            package_contract_hash=package_contract_hash(),
            choose=choose,
            teaching_context=teaching_context,
            required_visual_slots=set(packet.required_visual_slots()),
        )
        form_plan = form_plan_from_decisions(teaching_plan, snapshot.decisions)
    orders = compile_print_work_orders(
        teaching_plan=teaching_plan, snapshot=snapshot
    )
    return form_plan, snapshot, orders


def build_closed_print_production_plan(
    *,
    teaching_plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    legality: LessonLegalitySnapshot,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    sealed_form_plan: FormPlan | None = None,
) -> tuple[FormPlan, PrintSelectionSnapshot, list[PrintWorkOrder]]:
    """Sync wrapper; executor should call the async variant."""
    import asyncio

    return asyncio.run(
        build_closed_print_production_plan_async(
            teaching_plan=teaching_plan,
            packet=packet,
            legality=legality,
            available_asset_ids=available_asset_ids,
            policy=policy,
            sealed_form_plan=sealed_form_plan,
        )
    )


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
    "build_closed_print_production_plan_async",
    "compile_print_work_orders_for_form_plan",
    "package_contract_hash",
    "produce_print_document_plan_from_teaching",
    "selection_trace_payload",
    "teaching_plan_content_hash",
]

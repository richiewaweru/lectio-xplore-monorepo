"""Native Learn production adapter: approved teaching → closed selection → document.

Mirrors Print's closed production path. Provider fakes remain allowed only at
LLM call sites; this module is code-owned selection, work orders and assembly.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import AuthoringEngine, AuthoringProvider
from infra.authoring.capability_selector import ChooseFn
from learn.generation.authoring_adapter import author_learn_work_orders
from learn.generation.preparation_context import (
    LearnPreparationContext,
    lesson_context_from_preparation,
)
from learn.generation.native_selection import (
    LearnSelectionSnapshot,
    build_learn_selection_snapshot_async,
)
from learn.generation.assemble import assemble_learn_document
from learn.generation.document_realizer import realize_learn_document
from learn.generation.document_writer import write_document_node, write_interaction_node
from learn.generation.ordered_assemble import assemble_ordered_learn_document
from learn.generation.work_orders import LearnWorkOrder, compile_learn_work_orders
from learn.resources.native_policy import (
    default_learn_policy,
    policy_version_and_hash,
)
from learn.resources.selection import load_learn_selection_view


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
    view = load_learn_selection_view()
    raw = json.dumps(view, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def host_interaction_blocks_for_builder(document: dict[str, Any]) -> dict[str, Any]:
    """Remap learn-interaction:* hosts onto a registered content component (D-029).

    Keeps the interaction contract intact so runtime evaluation still works while
    Builder/publish registries catch up.
    """
    blocks = document.get("blocks")
    if not isinstance(blocks, dict):
        return document
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("learn_interaction"), dict):
            block["component_id"] = "explanation-block"
        elif str(block.get("component_id") or "").startswith("learn-interaction:"):
            block["component_id"] = "explanation-block"
    return document


def build_closed_learn_production(
    *,
    teaching_plan: TeachingPlan,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    title: str | None = None,
    subject: str = "science",
    source_generation_id: str | None = None,
    approved_items: Sequence[Any] | None = None,
    write_interactions: bool = True,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    preparation_context: LearnPreparationContext | None = None,
    choose: ChooseFn | None = None,
) -> dict[str, Any]:
    return _run_sync(
        build_closed_learn_production_async(
            teaching_plan=teaching_plan,
            available_asset_ids=available_asset_ids,
            policy=policy,
            title=title,
            subject=subject,
            source_generation_id=source_generation_id,
            approved_items=approved_items,
            write_interactions=write_interactions,
            provider=provider,
            engine=engine,
            preparation_context=preparation_context,
            choose=choose,
        )
    )


async def build_closed_learn_production_async(
    *,
    teaching_plan: TeachingPlan,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    title: str | None = None,
    subject: str = "science",
    source_generation_id: str | None = None,
    approved_items: Sequence[Any] | None = None,
    write_interactions: bool = True,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    preparation_context: LearnPreparationContext | None = None,
    choose: ChooseFn | None = None,
) -> dict[str, Any]:
    """Closed selection + work orders + assembled LessonDocument from shared teaching."""
    body = dict(policy) if policy is not None else default_learn_policy()
    _, policy_hash = policy_version_and_hash(body)
    plan_hash = teaching_plan_content_hash(teaching_plan)
    prep = preparation_context or LearnPreparationContext(
        objective=str(teaching_plan.arc or title or "").strip(),
    )
    lesson_ctx = lesson_context_from_preparation(
        prep,
        title=title or teaching_plan.arc or "Learn lesson",
        subject=subject,
    )
    snapshot = await build_learn_selection_snapshot_async(
        teaching_plan,
        teaching_plan_hash=plan_hash,
        native_policy_hash=policy_hash,
        package_contract_hash=package_contract_hash(),
        available_asset_ids=available_asset_ids,
        policy=body,
        teaching_context=lesson_ctx,
        choose=choose,
    )
    orders = compile_learn_work_orders(
        teaching_plan=teaching_plan,
        snapshot=snapshot,
        approved_items=approved_items,
    )
    approved_maps = [
        dict(item) if isinstance(item, Mapping) else vars(item)
        for item in (approved_items or [])
    ]
    authored_results = await author_learn_work_orders(
        orders,
        provider=provider,
        engine=engine,
        lesson_context=lesson_ctx,
        allowed_facts=prep.allowed_facts,
        terminology=prep.terminology,
        approved_items=approved_maps,
    )
    document = assemble_ordered_learn_document(
        teaching_plan=teaching_plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=authored_results,
        title=title or teaching_plan.arc or "Learn lesson",
        subject=subject,
        source="generated",
        source_generation_id=source_generation_id,
        write_interactions=False,
        approved_items=approved_items,
    )
    document = host_interaction_blocks_for_builder(document)
    return {
        "teaching_plan_hash": plan_hash,
        "native_policy_hash": policy_hash,
        "package_contract_hash": package_contract_hash(),
        "selection_snapshot": snapshot,
        "work_orders": orders,
        "document": document,
        "selection_trace": selection_trace_payload(snapshot, orders),
        "authoring_results": authored_results,
    }


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def selection_trace_payload(
    snapshot: LearnSelectionSnapshot,
    orders: Sequence[LearnWorkOrder],
) -> dict[str, Any]:
    return {
        "selection_snapshot": snapshot.model_dump(mode="json"),
        "work_orders": [order.model_dump(mode="json") for order in orders],
        "work_order_ids": [order.work_order_id for order in orders],
        "form_prompt": "closed_learn_selection",
    }


def produce_learn_document_from_teaching(
    *,
    teaching_plan: TeachingPlan,
    title: str | None = None,
    subject: str = "science",
    source_generation_id: str | None = None,
    lesson_id: str | None = None,
) -> dict[str, Any]:
    """Cutover target: Teaching Plan → document realizer → LearnDocument v2.

    Does not call the legacy component assembly path.
    Ordinary content is written as document primitives; interactions use stub
    config shells for retained types.
    """
    composition = realize_learn_document(teaching_plan)
    brief_by_block: dict[str, str] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            brief_by_block[block.id] = block.brief

    nodes: list[dict[str, Any]] = []
    for decision in composition.decisions:
        brief = brief_by_block.get(decision.teaching_block_id, "")
        decision_payload = decision.model_dump(mode="json")
        if decision.lane == "document":
            nodes.append(
                write_document_node(
                    form=decision.kind,
                    brief=brief,
                    teaching_block_id=decision.teaching_block_id,
                    decision=decision_payload,
                )
            )
        elif decision.lane == "learn_interaction":
            nodes.append(
                write_interaction_node(
                    interaction_type=decision.kind,
                    brief=brief,
                    teaching_block_id=decision.teaching_block_id,
                    decision=decision_payload,
                )
            )
        else:
            raise ValueError(
                f"unsupported Learn composition lane {decision.lane!r} "
                f"for block {decision.teaching_block_id!r}"
            )

    document = assemble_learn_document(
        nodes,
        {
            "id": lesson_id,
            "title": title or teaching_plan.arc or "Learn lesson",
            "subject": subject,
            "source": "generated",
            "source_generation_id": source_generation_id,
            "teaching_plan_id": teaching_plan.teaching_plan_id or composition.teaching_plan_id,
            "teaching_plan_revision": (
                teaching_plan.revision
                if teaching_plan.revision is not None
                else composition.teaching_plan_revision
            ),
        },
    )
    return {
        "composition_plan": composition,
        "document": document,
        "teaching_plan_hash": teaching_plan_content_hash(teaching_plan),
    }


__all__ = [
    "build_closed_learn_production",
    "build_closed_learn_production_async",
    "host_interaction_blocks_for_builder",
    "package_contract_hash",
    "produce_learn_document_from_teaching",
    "selection_trace_payload",
    "teaching_plan_content_hash",
]

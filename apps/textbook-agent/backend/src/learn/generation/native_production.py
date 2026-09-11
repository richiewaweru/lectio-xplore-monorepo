"""Native Learn production: Teaching Plan → compose → write → LearnDocument v2.

Production path uses the shared LLM document composer and writer. Brief-copy
stubs are not used. Interactions go through ``interaction_writer``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composer import compose_document_plan
from document.composition import CompositionDecision, CompositionPlan
from document.writer import write_document_primitive
from infra.authoring import AuthoringEngine, AuthoringProvider
from infra.authoring.capability_selector import ChooseFn
from learn.generation.assemble import assemble_learn_document
from learn.generation.authoring_adapter import author_learn_work_orders
from learn.generation.document_realizer import realize_learn_document
from learn.generation.figure_pipeline import attach_figure_asset
from learn.generation.interaction_writer import write_interaction_from_request
from learn.generation.native_selection import (
    LearnSelectionSnapshot,
    build_learn_selection_snapshot_async,
)
from learn.generation.ordered_assemble import assemble_ordered_learn_document
from learn.generation.preparation_context import (
    LearnPreparationContext,
    lesson_context_from_preparation,
)
from learn.generation.work_orders import LearnWorkOrder, compile_learn_work_orders
from learn.interactions.action_map import (
    ACTION_TO_LEARN_INTERACTION,
    PASSIVE_LEARNER_ACTIONS,
)
from learn.interactions.registry import RETAINED_INTERACTIONS
from learn.resources.native_policy import (
    default_learn_policy,
    policy_version_and_hash,
)
from learn.resources.selection import (
    build_learn_candidate_map,
    load_learn_selection_view,
)


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
    """Legacy v1 host remap — kept for closed-path tests only."""
    from document.models import DOCUMENT_PRIMITIVE_KINDS

    blocks = document.get("blocks")
    if not isinstance(blocks, dict):
        return document
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        component_id = str(block.get("component_id") or "")
        if isinstance(block.get("learn_interaction"), dict):
            block["component_id"] = "explanation-block"
        elif component_id.startswith("learn-interaction:"):
            block["component_id"] = "explanation-block"
        elif component_id in DOCUMENT_PRIMITIVE_KINDS:
            # v1 LessonDocument host still expects registry component ids.
            # Preserve authored payload under content; remap the host id only.
            content = block.get("content")
            if isinstance(content, dict) and "body" not in content:
                text = (
                    content.get("text")
                    or content.get("body")
                    or content.get("caption")
                    or ""
                )
                if component_id == "list" and isinstance(content.get("items"), list):
                    text = "; ".join(str(item) for item in content["items"])
                elif component_id == "callout":
                    text = str(content.get("body") or content.get("title") or text)
                elif component_id == "table":
                    text = str(content.get("caption") or "Comparison table.")
                block["content"] = {
                    "body": str(text) or "Generated ordinary content.",
                    "emphasis": [],
                    "primitive": dict(content),
                }
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
    """Legacy closed LessonDocument v1 path (tests / salvage only — not Unit production)."""
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


def _block_lookup(plan: TeachingPlan) -> dict[str, TeachingPlanBlock]:
    return {block.id: block for section in plan.sections for block in section.blocks}


def _section_lookup(plan: TeachingPlan) -> dict[str, str]:
    out: dict[str, str] = {}
    for section in plan.sections:
        for block in section.blocks:
            out[block.id] = str(section.slot_id or "")
    return out


def _action_for(block: TeachingPlanBlock) -> str | None:
    if block.learner_action is None:
        return None
    return str(block.learner_action.action or "").strip() or None


def _select_interaction_for_block(
    block: TeachingPlanBlock,
    *,
    candidates_by_block: Mapping[str, Sequence[str]] | None = None,
) -> str | None:
    """Derive retained interaction for a learner_action.

    One obvious candidate → deterministic. Multiple → prefer action map, else first legal.
    """
    action = _action_for(block)
    if not action or action in PASSIVE_LEARNER_ACTIONS:
        return None
    mapped = ACTION_TO_LEARN_INTERACTION.get(action)
    legal = list(candidates_by_block.get(block.id, ()) if candidates_by_block else ())
    legal = [c for c in legal if c in RETAINED_INTERACTIONS]
    if mapped and (not legal or mapped in legal):
        return mapped
    if len(legal) == 1:
        return legal[0]
    if mapped:
        return mapped
    if legal:
        return legal[0]
    return mapped


def _layer_learn_interactions(
    plan: TeachingPlan,
    document_plan: CompositionPlan,
    *,
    candidates_by_block: Mapping[str, Sequence[str]] | None = None,
) -> CompositionPlan:
    """Append learn_interaction decisions after ordinary document composition."""
    section_map = _section_lookup(plan)
    decisions = list(document_plan.decisions)
    seen_blocks: set[str] = set()
    for block in (b for s in plan.sections for b in s.blocks):
        if block.id in seen_blocks:
            continue
        seen_blocks.add(block.id)
        interaction = _select_interaction_for_block(
            block, candidates_by_block=candidates_by_block
        )
        if interaction is None:
            continue
        decisions.append(
            CompositionDecision(
                teaching_block_id=block.id,
                kind=interaction,
                lane="learn_interaction",
                reason=f"learner_action → retained interaction {interaction!r}",
                section_id=section_map.get(block.id) or None,
                role="check",
            )
        )
    return CompositionPlan(
        path="learn",
        teaching_plan_id=document_plan.teaching_plan_id or plan.teaching_plan_id,
        teaching_plan_revision=(
            document_plan.teaching_plan_revision
            if document_plan.teaching_plan_revision is not None
            else plan.revision
        ),
        decisions=decisions,
    )


def _interaction_node_from_contract(
    contract: Mapping[str, Any],
    *,
    teaching_block_id: str,
    node_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id or f"ix-{uuid.uuid4().hex[:12]}",
        "kind": "interaction",
        "interaction_type": str(contract.get("kind") or ""),
        "teaching_block_id": teaching_block_id,
        "prompt": str(contract.get("prompt") or ""),
        "config": dict(contract.get("config") or {}),
        "feedback": contract.get("feedback"),
        "assessment_mode": contract.get("assessment_mode") or "practice",
        "attempt_policy": contract.get("attempt_policy"),
        "completion": contract.get("completion"),
        "contract": dict(contract),
    }


async def produce_learn_document_from_teaching_async(
    *,
    teaching_plan: TeachingPlan,
    title: str | None = None,
    subject: str = "science",
    source_generation_id: str | None = None,
    lesson_id: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    preparation_context: LearnPreparationContext | None = None,
    available_asset_ids: Sequence[str] | None = None,
    approved_items: Sequence[Any] | None = None,
    allow_heuristic_composition_fallback: bool = True,
) -> dict[str, Any]:
    """Production LearnDocument v2: compose → write → assemble.

    Requires a provider for real learner-facing writing. Composition may fall
    back to heuristics only when explicitly allowed and the composer fails.
    """
    prep = preparation_context or LearnPreparationContext(
        objective=str(teaching_plan.arc or title or "").strip(),
    )
    lesson_ctx = lesson_context_from_preparation(
        prep,
        title=title or teaching_plan.arc or "Learn lesson",
        subject=subject,
    )
    lesson_ctx = {
        **lesson_ctx,
        "teaching_plan_revision": teaching_plan.revision,
        "objective": lesson_ctx.get("objective") or teaching_plan.arc,
    }

    # Candidate map for interaction selection (closed legal set per block).
    candidates_by_block: dict[str, list[str]] = {}
    try:
        candidate_map = build_learn_candidate_map(
            teaching_plan,
            available_asset_ids=available_asset_ids,
            policy=default_learn_policy(),
            fail_on_empty_required=False,
        )
        for block_id, entry in (candidate_map or {}).items():
            if hasattr(entry, "interaction_candidates"):
                candidates_by_block[str(block_id)] = [
                    str(c) for c in entry.interaction_candidates
                ]
            elif isinstance(entry, Mapping):
                candidates_by_block[str(block_id)] = [
                    str(c) for c in (entry.get("interaction_candidates") or [])
                ]
    except Exception:
        candidates_by_block = {}

    document_plan = await compose_document_plan(
        teaching_plan,
        path="learn",
        provider=provider,
        engine=engine,
        allow_heuristic_fallback=allow_heuristic_composition_fallback,
    )
    composition = _layer_learn_interactions(
        teaching_plan,
        document_plan,
        candidates_by_block=candidates_by_block,
    )

    blocks = _block_lookup(teaching_plan)
    nodes: list[dict[str, Any]] = []
    doc_decisions = [d for d in composition.decisions if d.lane == "document"]
    for index, decision in enumerate(composition.decisions):
        block = blocks.get(decision.teaching_block_id)
        if block is None:
            raise ValueError(
                f"composition references unknown teaching block {decision.teaching_block_id!r}"
            )
        brief = block.brief or ""
        if decision.lane == "document":
            neighbours: list[dict[str, Any]] = []
            if decision in doc_decisions:
                di = doc_decisions.index(decision)
                neighbours = [
                    {
                        "kind": d.kind,
                        "role": d.role,
                        "teaching_block_id": d.teaching_block_id,
                        "reason": d.reason,
                    }
                    for i, d in enumerate(doc_decisions)
                    if i != di and abs(i - di) <= 2
                ]
            teaching_block_payload = {
                "id": block.id,
                "intent": block.intent,
                "brief": block.brief,
                "evidence": block.evidence,
            }
            node = await write_document_primitive(
                kind=decision.kind,
                brief=brief,
                teaching_block=teaching_block_payload,
                lesson_context=lesson_ctx,
                evidence=block.evidence,
                allowed_facts=prep.allowed_facts,
                terminology=prep.terminology,
                neighbour_summaries=neighbours,
                teaching_block_id=block.id,
                role=decision.role,
                reason=decision.reason,
                provider=provider,
                engine=engine,
            )
            if decision.kind == "figure" and not node.get("asset_id"):
                # Caption/alt from writer; image via the shared visual pipeline.
                node = await attach_figure_asset(
                    node,
                    generation_id=str(
                        source_generation_id or lesson_id or "learn-figure"
                    ),
                    teaching_block=teaching_block_payload,
                    lesson_context=lesson_ctx,
                )
            nodes.append(node)
        elif decision.lane == "learn_interaction":
            action = _action_for(block)
            contract = write_interaction_from_request(
                {
                    "capability_id": decision.kind,
                    "lane": "interaction",
                    "block_id": block.id,
                    "section_id": decision.section_id or "section",
                    "brief": brief,
                    "intent": block.intent,
                    "action": action,
                    "evidence": block.evidence or "",
                    "teaching_plan_id": teaching_plan.teaching_plan_id or "teaching-plan",
                    "teaching_plan_revision": int(teaching_plan.revision or 1),
                    "lesson_context": lesson_ctx,
                    "allowed_facts": list(prep.allowed_facts or []),
                    "terminology": list(prep.terminology or []),
                    "approved_items": list(approved_items or []),
                },
                provider=provider,
                engine=engine,
            )
            nodes.append(
                _interaction_node_from_contract(
                    contract,
                    teaching_block_id=block.id,
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


def produce_learn_document_from_teaching(
    *,
    teaching_plan: TeachingPlan,
    title: str | None = None,
    subject: str = "science",
    source_generation_id: str | None = None,
    lesson_id: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    preparation_context: LearnPreparationContext | None = None,
    available_asset_ids: Sequence[str] | None = None,
    approved_items: Sequence[Any] | None = None,
    allow_heuristic_composition_fallback: bool = True,
) -> dict[str, Any]:
    """Sync wrapper around the async LearnDocument v2 production path."""
    return _run_sync(
        produce_learn_document_from_teaching_async(
            teaching_plan=teaching_plan,
            title=title,
            subject=subject,
            source_generation_id=source_generation_id,
            lesson_id=lesson_id,
            provider=provider,
            engine=engine,
            preparation_context=preparation_context,
            available_asset_ids=available_asset_ids,
            approved_items=approved_items,
            allow_heuristic_composition_fallback=allow_heuristic_composition_fallback,
        )
    )


# Keep heuristic realizer import reachable for tests / fallback diagnostics.
_ = realize_learn_document


__all__ = [
    "build_closed_learn_production",
    "build_closed_learn_production_async",
    "host_interaction_blocks_for_builder",
    "package_contract_hash",
    "produce_learn_document_from_teaching",
    "produce_learn_document_from_teaching_async",
    "selection_trace_payload",
    "teaching_plan_content_hash",
]

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
from learn.generation.document_realizer import realize_learn_document
from learn.generation.figure_pipeline import attach_figure_asset
from learn.generation.interaction_writer import write_interaction_from_request
from learn.generation.preparation_context import (
    LearnPreparationContext,
    lesson_context_from_preparation,
)
from learn.interactions.action_map import (
    ACTION_TO_LEARN_INTERACTION,
    PASSIVE_LEARNER_ACTIONS,
    interaction_for_learner_action,
)
from learn.interactions.registry import RETAINED_INTERACTIONS
from learn.resources.native_policy import (
    default_learn_policy,
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


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _block_lookup(plan: TeachingPlan) -> dict[str, TeachingPlanBlock]:
    return {block.id: block for section in plan.sections for block in section.blocks}


def _realized_sections(plan: TeachingPlan, nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    block_to_section: dict[str, str] = {}
    sections: list[dict[str, Any]] = []
    for index, section in enumerate(plan.sections):
        slot_id = str(section.slot_id or f"section-{index}")
        sections.append(
            {
                "id": slot_id,
                "title": str(section.specific_purpose or slot_id),
                "position": index,
                "transition": section.transition,
                "node_ids": [],
            }
        )
        for block in section.blocks:
            block_to_section[block.id] = slot_id
    by_id = {item["id"]: item for item in sections}
    for node in nodes:
        block_id = str(node.get("teaching_block_id") or "")
        section_id = block_to_section.get(block_id)
        node_id = str(node.get("id") or "")
        if section_id and node_id and section_id in by_id:
            by_id[section_id]["node_ids"].append(node_id)
    return sections


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


def _legal_interaction_candidates(
    block: TeachingPlanBlock,
    *,
    candidates_by_block: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Closed legal interaction kinds for a block (runtime shortlist ∩ retained).

    Falls back to YAML learn-action-map candidates when no runtime shortlist.
    """
    from core.policies.loader import learn_candidates_for_action

    action = _action_for(block)
    runtime = list(candidates_by_block.get(block.id, ()) if candidates_by_block else ())
    runtime = [c for c in runtime if c in RETAINED_INTERACTIONS]
    if runtime:
        return runtime
    yaml_candidates = [
        c for c in learn_candidates_for_action(action) if c in RETAINED_INTERACTIONS
    ]
    return yaml_candidates


async def _llm_select_interaction(
    *,
    legal: Sequence[str],
    block: TeachingPlanBlock,
    choose: ChooseFn | None = None,
) -> str:
    """Bounded LLM pick among legal candidates using interaction-selection.md."""
    from core.prompts.loader import effective_prompt_text
    from infra.authoring.capability_selector import (
        CapabilitySelection,
        select_capability_from_shortlist,
    )

    action = _action_for(block)
    la = block.learner_action
    evidence = str(la.expected_evidence if la is not None else block.evidence or "")
    difficulty = str(la.difficulty if la is not None else "")
    policy_text = effective_prompt_text("interaction-selection")

    async def _default_choose(context: dict[str, Any]) -> CapabilitySelection:
        from curriculum.agents import run_interaction_selection

        slim = {
            "learner_action": action,
            "expected_evidence": evidence,
            "difficulty": difficulty,
            "intent": block.intent,
            "brief": block.brief,
            "legal_candidates": list(legal),
            "policy": policy_text,
        }
        if context.get("repair"):
            slim["repair"] = context["repair"]
            slim["validation_errors"] = context.get("validation_errors")
            slim["instruction"] = context.get("instruction")
        return await run_interaction_selection(slim)

    selection = await select_capability_from_shortlist(
        candidate_ids=list(legal),
        brief=str(block.brief or ""),
        intent=str(block.intent or ""),
        action=action,
        lane="interaction",
        required=True,
        choose=choose or _default_choose,
    )
    chosen = str(selection.capability_id or "").strip()
    if chosen not in set(legal):
        raise ValueError(
            f"interaction selection {chosen!r} not in legal candidates {list(legal)}"
        )
    return chosen


async def _select_interaction_for_block(
    block: TeachingPlanBlock,
    *,
    candidates_by_block: Mapping[str, Sequence[str]] | None = None,
    choose: ChooseFn | None = None,
) -> tuple[str | None, str | None]:
    """Derive retained interaction and truthful selection_mode.

    Returns (kind, selection_mode). Modes:
    - deterministic_single: exactly one legal candidate, no LLM
    - policy_default: YAML default with no multi-candidate shortlist, no LLM
    - llm_multi_candidate: 2+ legal candidates, bounded LLM via interaction-selection.md
    """
    action = _action_for(block)
    if not action or action in PASSIVE_LEARNER_ACTIONS:
        return None, None
    mapped = interaction_for_learner_action(action) or ACTION_TO_LEARN_INTERACTION.get(
        action
    )
    legal = _legal_interaction_candidates(
        block, candidates_by_block=candidates_by_block
    )
    if len(legal) == 1:
        return legal[0], "deterministic_single"
    if len(legal) >= 2:
        chosen = await _llm_select_interaction(
            legal=legal, block=block, choose=choose
        )
        return chosen, "llm_multi_candidate"
    if mapped:
        return mapped, "policy_default"
    return None, None


async def _layer_learn_interactions(
    plan: TeachingPlan,
    document_plan: CompositionPlan,
    *,
    candidates_by_block: Mapping[str, Sequence[str]] | None = None,
    choose: ChooseFn | None = None,
) -> CompositionPlan:
    """Append learn_interaction decisions after ordinary document composition."""
    section_map = _section_lookup(plan)
    decisions = list(document_plan.decisions)
    seen_blocks: set[str] = set()
    for block in (b for s in plan.sections for b in s.blocks):
        if block.id in seen_blocks:
            continue
        seen_blocks.add(block.id)
        interaction, mode = await _select_interaction_for_block(
            block, candidates_by_block=candidates_by_block, choose=choose
        )
        if interaction is None:
            continue
        decisions.append(
            CompositionDecision(
                teaching_block_id=block.id,
                kind=interaction,
                lane="learn_interaction",
                reason=(
                    f"learner_action → retained interaction {interaction!r} "
                    f"(selection_mode={mode})"
                ),
                section_id=section_map.get(block.id) or None,
                role="check",
                selection_mode=mode,  # type: ignore[arg-type]
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
        composition_mode=document_plan.composition_mode,
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
    composition = await _layer_learn_interactions(
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
            "sections": _realized_sections(teaching_plan, nodes),
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
    "package_contract_hash",
    "produce_learn_document_from_teaching",
    "produce_learn_document_from_teaching_async",
    "teaching_plan_content_hash",
]

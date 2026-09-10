"""Learn native selection decisions, snapshots and validation (P04)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring.capability_selector import ChooseFn, select_capability_from_shortlist
from learn.resources.selection import (
    LearnBlockCandidates,
    NoCompatibleLearnCapabilityError,
    build_learn_candidate_map,
    load_learn_selection_view,
)

SelectionErrorCode = Literal[
    "OUT_OF_SET",
    "MISSING_BLOCK",
    "DUPLICATE_BLOCK",
    "ALTERED_TEACHING_IDENTITY",
    "BLOCK_SET",
    "NO_COMPATIBLE_CAPABILITY",
    "UNSUPPORTED_ASSET",
]


class SelectionError(ValueError):
    def __init__(self, code: SelectionErrorCode, message: str, *, path: str = "") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


class LearnSelectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    content_id: str | None = None
    interaction_id: str | None = None
    reason: str = ""
    source_item_ids: list[str] = Field(default_factory=list)
    dependency_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _at_least_one_surface(self) -> LearnSelectionDecision:
        if not self.content_id and not self.interaction_id:
            raise ValueError("decision must select content and/or interaction")
        return self


class LearnSelectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["learn"] = "learn"
    teaching_plan_id: str
    teaching_plan_revision: int
    teaching_plan_hash: str
    native_policy_hash: str
    package_contract_hash: str
    candidate_map: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    decisions: list[LearnSelectionDecision] = Field(default_factory=list)
    snapshot_hash: str = ""

    def recompute_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"snapshot_hash"})
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def seal(self) -> LearnSelectionSnapshot:
        return self.model_copy(update={"snapshot_hash": self.recompute_hash()})


def candidate_map_payload(
    candidates: Mapping[str, LearnBlockCandidates],
) -> dict[str, dict[str, list[str]]]:
    return {
        block_id: {
            "content": list(row.content_candidates),
            "interaction": list(row.interaction_candidates),
        }
        for block_id, row in candidates.items()
    }


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _guidance_tokens(text: str) -> frozenset[str]:
    return frozenset(tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) > 2)


def rank_learn_interaction_candidates(
    interaction_ids: Sequence[str],
    *,
    brief: str,
    intent: str,
    action: str | None,
    selection_view: Mapping[str, Any] | None = None,
) -> list[str]:
    """Rank a closed interaction shortlist by package choose_when / reject_when.

    Higher overlap between the block brief (plus intent/action) and choose_when
    wins; reject_when overlap penalizes. Ties keep the input shortlist order —
    never Sequence-because-writer and never first-id as product policy.
    """
    if not interaction_ids:
        return []
    view = selection_view if selection_view is not None else load_learn_selection_view()
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in view.get("capabilities") or []:
        if isinstance(row, Mapping) and row.get("id"):
            by_id[str(row["id"])] = row
    query = _guidance_tokens(f"{brief} {intent} {action or ''}")
    scored: list[tuple[int, int, int, str]] = []
    for index, capability_id in enumerate(interaction_ids):
        record = by_id.get(capability_id) or {}
        choose = _guidance_tokens(str(record.get("choose_when") or ""))
        reject = _guidance_tokens(str(record.get("reject_when") or ""))
        choose_hits = len(query & choose)
        reject_hits = len(query & reject)
        # Sort key: maximize choose overlap, minimize reject overlap, stable index.
        scored.append((-choose_hits, reject_hits, index, capability_id))
    scored.sort()
    return [capability_id for _, _, _, capability_id in scored]


def rank_learn_content_candidates(
    content_ids: Sequence[str],
    *,
    brief: str,
    intent: str,
    action: str | None,
    selection_view: Mapping[str, Any] | None = None,
) -> list[str]:
    """Rank closed content shortlist by package guidance and clear intent hints."""
    if not content_ids:
        return []
    view = selection_view if selection_view is not None else load_learn_selection_view()
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in view.get("capabilities") or []:
        if isinstance(row, Mapping) and row.get("id"):
            by_id[str(row["id"])] = row
    query_text = f"{brief} {intent} {action or ''}"
    query = _guidance_tokens(query_text)
    lowered = query_text.lower()
    scored: list[tuple[int, int, int, int, str]] = []
    for index, capability_id in enumerate(content_ids):
        record = by_id.get(capability_id) or {}
        choose = _guidance_tokens(str(record.get("choose_when") or ""))
        reject = _guidance_tokens(str(record.get("reject_when") or ""))
        choose_hits = len(query & choose)
        reject_hits = len(query & reject)
        intent_bonus = 0
        if capability_id == "explanation-block" and any(
            token in lowered for token in ("explain", "causal", "prose", "why")
        ):
            intent_bonus = 3
        elif capability_id == "definition-card" and any(
            token in lowered for token in ("define", "definition", "term")
        ):
            intent_bonus = 3
        elif capability_id == "summary-block" and any(
            token in lowered for token in ("summar", "takeaway", "recap")
        ):
            intent_bonus = 3
        scored.append((-(choose_hits + intent_bonus), reject_hits, -intent_bonus, index, capability_id))
    scored.sort()
    return [capability_id for _, _, _, _, capability_id in scored]


def _source_and_deps_for_block(block: Any) -> tuple[list[str], list[str]]:
    """Provenance lives on the block: source_question_ids + stimulus_dependencies."""
    source_ids = list(block.source_question_ids or [])
    deps = list(block.stimulus_dependencies or [])
    return source_ids, deps


def _decide_from_candidates(
    teaching_plan: TeachingPlan,
    candidates: Mapping[str, LearnBlockCandidates],
    *,
    pick_content: Any,
    pick_interaction: Any,
    reason_with_interaction: str,
) -> list[LearnSelectionDecision]:
    decisions: list[LearnSelectionDecision] = []
    for section in teaching_plan.sections:
        for block in section.blocks:
            row = candidates[block.id]
            content_id = pick_content(block, row) if row.content_candidates else None
            interaction_id: str | None
            if row.requires_response:
                if not row.interaction_candidates:
                    raise NoCompatibleLearnCapabilityError(
                        block_id=block.id,
                        intent=block.intent,
                        action=row.action,
                        constraints={"interaction_candidates": []},
                        reason="required interaction set empty",
                    )
                interaction_id = pick_interaction(block, row)
            else:
                # Optional interaction → explicit none (P04-N03).
                interaction_id = None
            source_ids, deps = _source_and_deps_for_block(block)
            if not content_id and not interaction_id:
                raise NoCompatibleLearnCapabilityError(
                    block_id=block.id,
                    intent=block.intent,
                    action=row.action,
                    constraints={},
                    reason="no content or interaction selected",
                )
            decisions.append(
                LearnSelectionDecision(
                    block_id=block.id,
                    content_id=content_id,
                    interaction_id=interaction_id,
                    reason=(
                        reason_with_interaction
                        if interaction_id
                        else "passive content; interaction=none"
                    ),
                    source_item_ids=source_ids,
                    dependency_ids=deps,
                )
            )
    return decisions


def select_learn_first_legal(
    teaching_plan: TeachingPlan,
    *,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> tuple[dict[str, LearnBlockCandidates], list[LearnSelectionDecision]]:
    """Test helper: first legal content + first legal interaction from the shortlist.

    Production selection ranks with package choose_when / reject_when; gates that
    need a stable first-legal pick should call this helper explicitly.
    """
    candidates = build_learn_candidate_map(
        teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
        fail_on_empty_required=True,
    )

    def _first(_block: Any, row: LearnBlockCandidates) -> str:
        return row.interaction_candidates[0]

    def _first_content(_block: Any, row: LearnBlockCandidates) -> str:
        return row.content_candidates[0]

    decisions = _decide_from_candidates(
        teaching_plan,
        candidates,
        pick_content=_first_content,
        pick_interaction=_first,
        reason_with_interaction="deterministic first-legal closed candidate",
    )
    return candidates, decisions


def select_learn_deterministically(
    teaching_plan: TeachingPlan,
    *,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> tuple[dict[str, LearnBlockCandidates], list[LearnSelectionDecision]]:
    """Test utility: keyword-ranked closed selection (not production policy)."""
    candidates = build_learn_candidate_map(
        teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
        fail_on_empty_required=True,
    )

    def _ranked(block: Any, row: LearnBlockCandidates) -> str:
        ranked = rank_learn_interaction_candidates(
            row.interaction_candidates,
            brief=str(getattr(block, "brief", "") or ""),
            intent=block.intent,
            action=row.action,
        )
        return ranked[0]

    def _ranked_content(block: Any, row: LearnBlockCandidates) -> str:
        ranked = rank_learn_content_candidates(
            row.content_candidates,
            brief=str(getattr(block, "brief", "") or ""),
            intent=block.intent,
            action=row.action,
        )
        return ranked[0]

    decisions = _decide_from_candidates(
        teaching_plan,
        candidates,
        pick_content=_ranked_content,
        pick_interaction=_ranked,
        reason_with_interaction="keyword-ranked test utility",
    )
    return candidates, decisions


async def select_learn_with_model_async(
    teaching_plan: TeachingPlan,
    *,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    choose: ChooseFn | None = None,
    teaching_context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, LearnBlockCandidates], list[LearnSelectionDecision]]:
    """Production closed selection via configured model selector."""
    candidates = build_learn_candidate_map(
        teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
        fail_on_empty_required=True,
    )
    selection_view = load_learn_selection_view()
    content_reason = "model-selected closed content candidate"
    interaction_reason = "model-selected closed interaction candidate"
    pick_cache: dict[tuple[str, str, tuple[str, ...]], str] = {}

    async def _pick(
        *,
        lane: str,
        candidate_ids: Sequence[str],
        block: Any,
        row: LearnBlockCandidates,
        required: bool,
    ) -> str | None:
        if not candidate_ids:
            return None
        key = (block.id, lane, tuple(candidate_ids))
        if key in pick_cache:
            return pick_cache[key]
        selection = await select_capability_from_shortlist(
            candidate_ids=candidate_ids,
            brief=str(getattr(block, "brief", "") or ""),
            intent=block.intent,
            action=row.action,
            lane=lane,
            required=required,
            selection_view=selection_view,
            collection_key="capabilities",
            teaching_context=teaching_context,
            choose=choose,
        )
        pick_cache[key] = selection.capability_id
        return selection.capability_id

    async def _pick_content(block: Any, row: LearnBlockCandidates) -> str | None:
        if not row.content_candidates:
            return None
        return await _pick(
            lane="content",
            candidate_ids=row.content_candidates,
            block=block,
            row=row,
            required=False,
        )

    async def _pick_interaction(block: Any, row: LearnBlockCandidates) -> str | None:
        if not row.requires_response:
            return None
        return await _pick(
            lane="interaction",
            candidate_ids=row.interaction_candidates,
            block=block,
            row=row,
            required=True,
        )

    decisions: list[LearnSelectionDecision] = []
    for section in teaching_plan.sections:
        for block in section.blocks:
            row = candidates[block.id]
            content_id = await _pick_content(block, row) if row.content_candidates else None
            interaction_id: str | None
            if row.requires_response:
                if not row.interaction_candidates:
                    raise NoCompatibleLearnCapabilityError(
                        block_id=block.id,
                        intent=block.intent,
                        action=row.action,
                        constraints={"interaction_candidates": []},
                        reason="required interaction set empty",
                    )
                interaction_id = await _pick_interaction(block, row)
            else:
                interaction_id = None
            source_ids, deps = _source_and_deps_for_block(block)
            if not content_id and not interaction_id:
                raise NoCompatibleLearnCapabilityError(
                    block_id=block.id,
                    intent=block.intent,
                    action=row.action,
                    constraints={},
                    reason="no content or interaction selected",
                )
            decisions.append(
                LearnSelectionDecision(
                    block_id=block.id,
                    content_id=content_id,
                    interaction_id=interaction_id,
                    reason=(
                        interaction_reason
                        if interaction_id
                        else (
                            content_reason
                            if content_id
                            else "passive content; interaction=none"
                        )
                    ),
                    source_item_ids=source_ids,
                    dependency_ids=deps,
                )
            )
    return candidates, decisions


async def build_learn_selection_snapshot_async(
    teaching_plan: TeachingPlan,
    *,
    teaching_plan_hash: str,
    native_policy_hash: str,
    package_contract_hash: str,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    decisions: Sequence[LearnSelectionDecision] | None = None,
    choose: ChooseFn | None = None,
    teaching_context: Mapping[str, Any] | None = None,
) -> LearnSelectionSnapshot:
    if decisions is not None:
        candidates = build_learn_candidate_map(
            teaching_plan,
            available_asset_ids=available_asset_ids,
            policy=policy,
            fail_on_empty_required=True,
        )
        chosen = list(decisions)
    else:
        candidates, chosen = await select_learn_with_model_async(
            teaching_plan,
            available_asset_ids=available_asset_ids,
            policy=policy,
            choose=choose,
            teaching_context=teaching_context,
        )
    validate_learn_selection(
        teaching_plan=teaching_plan,
        decisions=chosen,
        candidate_map=candidates,
        expected_teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        expected_teaching_plan_revision=int(teaching_plan.revision or 1),
        expected_teaching_plan_hash=teaching_plan_hash,
        actual_teaching_plan_hash=teaching_plan_hash,
    )
    snap = LearnSelectionSnapshot(
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=teaching_plan_hash,
        native_policy_hash=native_policy_hash,
        package_contract_hash=package_contract_hash,
        candidate_map=candidate_map_payload(candidates),
        decisions=list(chosen),
    )
    return snap.seal()


def build_learn_selection_snapshot(
    teaching_plan: TeachingPlan,
    *,
    teaching_plan_hash: str,
    native_policy_hash: str,
    package_contract_hash: str,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    decisions: Sequence[LearnSelectionDecision] | None = None,
    choose: ChooseFn | None = None,
    teaching_context: Mapping[str, Any] | None = None,
) -> LearnSelectionSnapshot:
    """Sync helper for tests; production callers should use the async builder."""
    if decisions is not None:
        return asyncio.run(
            build_learn_selection_snapshot_async(
                teaching_plan,
                teaching_plan_hash=teaching_plan_hash,
                native_policy_hash=native_policy_hash,
                package_contract_hash=package_contract_hash,
                available_asset_ids=available_asset_ids,
                policy=policy,
                decisions=decisions,
            )
        )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            build_learn_selection_snapshot_async(
                teaching_plan,
                teaching_plan_hash=teaching_plan_hash,
                native_policy_hash=native_policy_hash,
                package_contract_hash=package_contract_hash,
                available_asset_ids=available_asset_ids,
                policy=policy,
                choose=choose,
                teaching_context=teaching_context,
            )
        )
    raise RuntimeError(
        "build_learn_selection_snapshot cannot run model selection inside an event loop; "
        "await build_learn_selection_snapshot_async instead"
    )


def validate_learn_selection(
    *,
    teaching_plan: TeachingPlan,
    decisions: Sequence[LearnSelectionDecision],
    candidate_map: Mapping[str, LearnBlockCandidates] | Mapping[str, Mapping[str, Sequence[str]]],
    expected_teaching_plan_id: str | None = None,
    expected_teaching_plan_revision: int | None = None,
    expected_teaching_plan_hash: str | None = None,
    actual_teaching_plan_hash: str | None = None,
) -> None:
    if expected_teaching_plan_id is not None:
        if str(teaching_plan.teaching_plan_id or "") != expected_teaching_plan_id:
            raise SelectionError(
                "ALTERED_TEACHING_IDENTITY",
                "teaching_plan_id does not match selection snapshot",
                path="teaching_plan_id",
            )
    if expected_teaching_plan_revision is not None:
        if int(teaching_plan.revision or 0) != int(expected_teaching_plan_revision):
            raise SelectionError(
                "ALTERED_TEACHING_IDENTITY",
                "teaching_plan_revision does not match selection snapshot",
                path="teaching_plan_revision",
            )
    if (
        expected_teaching_plan_hash is not None
        and actual_teaching_plan_hash is not None
        and expected_teaching_plan_hash != actual_teaching_plan_hash
    ):
        raise SelectionError(
            "ALTERED_TEACHING_IDENTITY",
            "teaching_plan_hash does not match selection snapshot",
            path="teaching_plan_hash",
        )

    teaching_ids = [
        block.id for section in teaching_plan.sections for block in section.blocks
    ]
    decision_ids = [item.block_id for item in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise SelectionError(
            "DUPLICATE_BLOCK",
            "selection has duplicate block ids",
            path="decisions",
        )
    missing = [block_id for block_id in teaching_ids if block_id not in set(decision_ids)]
    if missing:
        raise SelectionError(
            "MISSING_BLOCK",
            f"selection missing teaching blocks: {missing}",
            path="decisions",
        )
    extra = [block_id for block_id in decision_ids if block_id not in set(teaching_ids)]
    if extra:
        raise SelectionError(
            "BLOCK_SET",
            f"selection references unknown blocks: {extra}",
            path="decisions",
        )

    for item in decisions:
        raw = candidate_map.get(item.block_id)
        if raw is None:
            raise SelectionError(
                "OUT_OF_SET",
                f"no candidate set for block {item.block_id!r}",
                path=f"decisions.{item.block_id}",
            )
        if isinstance(raw, LearnBlockCandidates):
            content_allowed = set(raw.content_candidates)
            interaction_allowed = set(raw.interaction_candidates)
            optional = raw.interaction_optional
            requires_response = raw.requires_response
        else:
            content_allowed = {str(x) for x in (raw.get("content") or [])}
            interaction_allowed = {str(x) for x in (raw.get("interaction") or [])}
            optional = True
            requires_response = False
        if item.content_id is not None and item.content_id not in content_allowed:
            raise SelectionError(
                "OUT_OF_SET",
                f"content {item.content_id!r} not in candidates for {item.block_id!r}",
                path=f"decisions.{item.block_id}.content_id",
            )
        if item.interaction_id is None:
            if requires_response:
                raise SelectionError(
                    "NO_COMPATIBLE_CAPABILITY",
                    f"required interaction missing for {item.block_id!r}",
                    path=f"decisions.{item.block_id}.interaction_id",
                )
            if not optional and interaction_allowed:
                pass
        elif item.interaction_id not in interaction_allowed:
            raise SelectionError(
                "OUT_OF_SET",
                f"interaction {item.interaction_id!r} not in candidates for {item.block_id!r}",
                path=f"decisions.{item.block_id}.interaction_id",
            )


__all__ = [
    "LearnSelectionDecision",
    "LearnSelectionSnapshot",
    "SelectionError",
    "SelectionErrorCode",
    "build_learn_selection_snapshot",
    "build_learn_selection_snapshot_async",
    "candidate_map_payload",
    "rank_learn_content_candidates",
    "rank_learn_interaction_candidates",
    "select_learn_deterministically",
    "select_learn_first_legal",
    "select_learn_with_model_async",
    "validate_learn_selection",
]

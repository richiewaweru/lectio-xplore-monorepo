"""Learn native selection decisions, snapshots and validation (P04)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum.teaching_plan.models import TeachingPlan
from learn.resources.selection import (
    LearnBlockCandidates,
    NoCompatibleLearnCapabilityError,
    build_learn_candidate_map,
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


def select_learn_deterministically(
    teaching_plan: TeachingPlan,
    *,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
) -> tuple[dict[str, LearnBlockCandidates], list[LearnSelectionDecision]]:
    """Code-owned closed selection: first legal content + optional/required interaction.

    Semantic LLM selection may replace the choice among the closed set later; this
    deterministic path is authoritative for eligibility gates and work-order compile.
    """
    candidates = build_learn_candidate_map(
        teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
        fail_on_empty_required=True,
    )
    decisions: list[LearnSelectionDecision] = []
    for section in teaching_plan.sections:
        for block in section.blocks:
            row = candidates[block.id]
            content_id = row.content_candidates[0] if row.content_candidates else None
            # Prefer Sequence among required interactions — sole generation-ready writer.
            interaction_id: str | None
            if row.requires_response:
                ordered = []
                if "sequence" in row.interaction_candidates:
                    ordered.append("sequence")
                ordered.extend(
                    i for i in row.interaction_candidates if i != "sequence"
                )
                if not ordered:
                    raise NoCompatibleLearnCapabilityError(
                        block_id=block.id,
                        intent=block.intent,
                        action=row.action,
                        constraints={"interaction_candidates": []},
                        reason="required interaction set empty",
                    )
                interaction_id = ordered[0]
            else:
                # Optional interaction → explicit none (P04-N03).
                interaction_id = None
            source_ids = list(block.source_question_ids or [])
            deps: list[str] = []
            if block.learner_action is not None:
                deps = list(block.learner_action.dependencies or [])
                if block.learner_action.source_item_ids:
                    source_ids = list(block.learner_action.source_item_ids)
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
                        "deterministic first-legal closed candidate"
                        if interaction_id
                        else "passive content; interaction=none"
                    ),
                    source_item_ids=source_ids,
                    dependency_ids=deps,
                )
            )
    return candidates, decisions


def build_learn_selection_snapshot(
    teaching_plan: TeachingPlan,
    *,
    teaching_plan_hash: str,
    native_policy_hash: str,
    package_contract_hash: str,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    decisions: Sequence[LearnSelectionDecision] | None = None,
) -> LearnSelectionSnapshot:
    candidates, auto = select_learn_deterministically(
        teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
    )
    chosen = list(decisions) if decisions is not None else auto
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
    "candidate_map_payload",
    "select_learn_deterministically",
    "validate_learn_selection",
]

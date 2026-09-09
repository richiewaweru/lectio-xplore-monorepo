"""Closed Learn content/interaction eligibility (P04)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from learn.resources.native_policy import (
    capabilities_requiring_assets,
    default_learn_policy,
    offered_content_ids,
    offered_interaction_ids,
)

PASSIVE_ACTIONS = frozenset({"compare-without-response", "read-explanation"})
# Gate wording uses reconstruct-order; vocabulary id is order-items.
ACTION_ALIASES = {
    "reconstruct-order": "order-items",
}
_REGISTERED_VALIDATOR_REFS: frozenset[str] = frozenset(
    {
        "learn.payload_schema",
        "learn.evaluateChoice",
        "learn.evaluateMultiSelect",
        "learn.evaluateFillBlank",
        "learn.evaluateNumeric",
        "learn.evaluateShortResponse",
        "learn.evaluateMatchPairs",
        "learn.evaluateClassify",
        "learn.evaluateSequence",
        "learn.quizContentToInteractionContract",
        "learn.fillBlankContentToInteractionContract",
    }
)
class NoCompatibleLearnCapabilityError(RuntimeError):
    """Required response/action has no legal capability under the closed set."""

    code = "NO_COMPATIBLE_CAPABILITY"

    def __init__(
        self,
        *,
        block_id: str,
        intent: str,
        action: str | None,
        constraints: Mapping[str, Any],
        reason: str,
    ) -> None:
        self.block_id = block_id
        self.intent = intent
        self.action = action
        self.constraints = dict(constraints)
        self.reason = reason
        super().__init__(
            f"NO_COMPATIBLE_CAPABILITY block={block_id!r} intent={intent!r} "
            f"action={action!r}: {reason}"
        )


@dataclass(frozen=True)
class LearnBlockCandidates:
    block_id: str
    intent: str
    action: str | None
    content_candidates: tuple[str, ...]
    interaction_candidates: tuple[str, ...]
    excluded: dict[str, str]
    requires_response: bool
    interaction_optional: bool


def _contracts_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "contracts"


@lru_cache(maxsize=1)
def load_learn_capabilities() -> list[dict[str, Any]]:
    path = _contracts_dir() / "learn-capabilities.v1.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("capabilities") or []
    return [row for row in rows if isinstance(row, dict) and row.get("id")]


@lru_cache(maxsize=1)
def load_learn_selection_view() -> dict[str, Any]:
    path = _contracts_dir() / "learn-selection-view.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_learn_writer_view() -> dict[str, Any]:
    path = _contracts_dir() / "learn-writer-view.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _capability_index(
    records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    rows = records if records is not None else load_learn_capabilities()
    return {str(row["id"]): dict(row) for row in rows}


def normalize_action(action: str | None) -> str | None:
    if action is None:
        return None
    return ACTION_ALIASES.get(action, action)


def _action_matches(
    *,
    action: str | None,
    supported_actions: Sequence[str],
    kind: str,
) -> bool:
    if not action:
        # No learner action → content presentation only.
        return kind == "content"
    canonical = normalize_action(action) or action
    supported = {str(item) for item in supported_actions}
    if canonical in supported or action in supported:
        return True
    # Passive teaching actions may be served by explanatory content even when
    # the catalogue lists only read-explanation.
    if canonical in PASSIVE_ACTIONS and kind == "content":
        return bool(supported.intersection(PASSIVE_ACTIONS)) or not supported
    return False


def _writer_readiness_error(
    capability_id: str, card: Mapping[str, Any] | None
) -> str | None:
    del capability_id
    if not isinstance(card, Mapping):
        return "writer_view_missing"
    instructions = card.get("instructions")
    text = ""
    if isinstance(instructions, Mapping):
        text = str(instructions.get("text") or "").strip()
    elif isinstance(instructions, str):
        text = instructions.strip()
    if not text:
        return "missing_instructions"
    if not card.get("payload_schema") and not card.get("payload_schema_ref"):
        return "missing_payload_schema"
    if not card.get("required_inputs"):
        return "missing_required_inputs"
    if not set(card.get("modes") or ()).intersection({"generate", "convert-approved"}):
        return "missing_authoring_mode"
    refs = {str(ref) for ref in (card.get("validator_refs") or [])}
    if not refs:
        return "missing_validator_refs"
    if refs - _REGISTERED_VALIDATOR_REFS:
        return "unknown_validator_refs"
    return None


def derive_learn_block_candidates(
    *,
    block_id: str,
    intent: str,
    action: str | None,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    capabilities: Sequence[Mapping[str, Any]] | None = None,
    remaining_budgets: Mapping[str, int] | None = None,
    writer_view: Mapping[str, Any] | None = None,
) -> LearnBlockCandidates:
    body = dict(policy) if policy is not None else default_learn_policy()
    content_offered = offered_content_ids(body)
    interaction_offered = offered_interaction_ids(body)
    asset_required = capabilities_requiring_assets(body)
    assets = {str(item) for item in (available_asset_ids or []) if item}
    budgets = {str(k): int(v) for k, v in (remaining_budgets or {}).items()}
    index = _capability_index(capabilities)
    writers = writer_view if writer_view is not None else (load_learn_writer_view().get("capabilities") or {})
    canonical_action = normalize_action(action)

    excluded: dict[str, str] = {}
    content: list[str] = []
    interactions: list[str] = []
    requires_response = bool(canonical_action) and canonical_action not in PASSIVE_ACTIONS
    interaction_optional = not requires_response

    for capability_id, record in sorted(index.items()):
        kind = str(record.get("kind") or "")
        if kind == "content":
            if capability_id not in content_offered:
                excluded[capability_id] = "not_in_native_policy"
                continue
        elif kind == "interaction":
            if capability_id not in interaction_offered:
                excluded[capability_id] = "not_in_native_policy"
                continue
        else:
            excluded[capability_id] = "unknown_kind"
            continue

        availability = str(record.get("availability") or "")
        if availability == "unavailable":
            excluded[capability_id] = "package_unavailable"
            continue

        # Production selection admits only generation-ready interactions
        # (package isSelectable). Incomplete kinds stay in writer/runtime views.
        if kind == "interaction":
            readiness = str(record.get("readiness") or "")
            if readiness != "generation-ready" or availability != "available":
                excluded[capability_id] = "not_generation_ready"
                continue

        # Writer projection: package must export a writer schema for the kind.
        writer_error = _writer_readiness_error(capability_id, writers.get(capability_id))
        if writer_error is not None:
            excluded[capability_id] = writer_error
            continue

        intents = {str(item) for item in (record.get("supported_intents") or [])}
        if intent not in intents:
            excluded[capability_id] = "intent_unsupported"
            continue

        actions = [str(item) for item in (record.get("supported_actions") or [])]
        if not _action_matches(
            action=canonical_action, supported_actions=actions, kind=kind
        ):
            excluded[capability_id] = "action_unsupported"
            continue

        requires_asset = bool(record.get("requires_asset")) or capability_id in asset_required
        if requires_asset and not assets:
            excluded[capability_id] = "asset_unavailable"
            continue

        if capability_id in budgets and budgets[capability_id] <= 0:
            excluded[capability_id] = "budget_exhausted"
            continue

        if kind == "content":
            content.append(capability_id)
        else:
            interactions.append(capability_id)

    return LearnBlockCandidates(
        block_id=block_id,
        intent=intent,
        action=canonical_action,
        content_candidates=tuple(content),
        interaction_candidates=tuple(interactions),
        excluded=excluded,
        requires_response=requires_response,
        interaction_optional=interaction_optional,
    )


def build_learn_candidate_map(
    teaching_plan: Any,
    *,
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    fail_on_empty_required: bool = True,
) -> dict[str, LearnBlockCandidates]:
    body = dict(policy) if policy is not None else default_learn_policy()
    caps = load_learn_capabilities()
    out: dict[str, LearnBlockCandidates] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            action = None
            if getattr(block, "learner_action", None) is not None:
                action = str(block.learner_action.action)
            derived = derive_learn_block_candidates(
                block_id=block.id,
                intent=block.intent,
                action=action,
                available_asset_ids=available_asset_ids,
                policy=body,
                capabilities=caps,
            )
            if fail_on_empty_required:
                if derived.requires_response and not derived.interaction_candidates:
                    raise NoCompatibleLearnCapabilityError(
                        block_id=block.id,
                        intent=block.intent,
                        action=action,
                        constraints={
                            "content_candidates": list(derived.content_candidates),
                            "interaction_candidates": [],
                            "excluded": derived.excluded,
                            "policy_interactions": sorted(offered_interaction_ids(body)),
                        },
                        reason="required learner action has no compatible interaction",
                    )
                if not derived.content_candidates and not derived.interaction_candidates:
                    raise NoCompatibleLearnCapabilityError(
                        block_id=block.id,
                        intent=block.intent,
                        action=action,
                        constraints={"excluded": derived.excluded},
                        reason="empty content and interaction candidate sets",
                    )
            out[block.id] = derived
    return out


__all__ = [
    "ACTION_ALIASES",
    "PASSIVE_ACTIONS",
    "LearnBlockCandidates",
    "NoCompatibleLearnCapabilityError",
    "build_learn_candidate_map",
    "derive_learn_block_candidates",
    "load_learn_capabilities",
    "load_learn_selection_view",
    "load_learn_writer_view",
    "normalize_action",
]

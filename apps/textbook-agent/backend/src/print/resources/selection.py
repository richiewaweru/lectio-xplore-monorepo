"""Closed Print form eligibility from package ∩ policy ∩ teaching ∩ assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from curriculum.approved_items import approved_item_kind
from print.contracts.lectio_page import get_object_catalogue, lectio_page_contracts_dir
from print.resources.native_policy import (
    default_print_policy,
    forms_requiring_assets,
    offered_form_ids,
)

# Learner actions that do not require a response interface.
PASSIVE_ACTIONS = frozenset({"compare-without-response", "read-explanation"})
_IMPLEMENTED_FORM_OBJECTS: frozenset[str] = frozenset(
    {
        "prose",
        "list",
        "table",
        "figure",
        "aside",
        "worked-example",
        "questions",
        "choices",
    }
)
_NEVER_SELECTABLE_OBJECTS: frozenset[str] = frozenset({"heading", "answer-key"})


class NoCompatiblePrintCapabilityError(RuntimeError):
    """Required teaching block has an empty legal form set."""

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
class PrintBlockCandidates:
    block_id: str
    intent: str
    action: str | None
    candidates: tuple[str, ...]
    excluded: dict[str, str]
    requires_response: bool


@lru_cache(maxsize=1)
def load_form_selection_view() -> dict[str, Any]:
    path = lectio_page_contracts_dir() / "form-selection-view.v1.json"
    if not path.exists():
        alt = (
            Path(__file__).resolve().parents[6]
            / "packages"
            / "lectio-page"
            / "contracts"
            / "generated"
            / "form-selection-view.v1.json"
        )
        path = alt
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_form_writer_view() -> dict[str, Any]:
    path = lectio_page_contracts_dir() / "form-writer-view.v1.json"
    if not path.exists():
        alt = (
            Path(__file__).resolve().parents[6]
            / "packages"
            / "lectio-page"
            / "contracts"
            / "generated"
            / "form-writer-view.v1.json"
        )
        path = alt
    return json.loads(path.read_text(encoding="utf-8"))


def _form_cards(view: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    doc = view or load_form_selection_view()
    rows = doc.get("forms") or []
    return {
        str(row["id"]): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def _object_actions_fallback() -> dict[str, tuple[str, ...]]:
    objects = get_object_catalogue().get("objects") or {}
    out: dict[str, tuple[str, ...]] = {}
    for object_id, record in objects.items():
        if not isinstance(record, dict):
            continue
        actions = record.get("supported_actions") or []
        out[str(object_id)] = tuple(str(a) for a in actions if a)
    return out


def _apply_approved_item_filter(
    legal: Sequence[str],
    *,
    source_question_ids: Sequence[str],
    approved_by_id: Mapping[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """Assessment forms bind to teaching-owned items; never discard item IDs."""
    excluded: dict[str, str] = {}
    if not source_question_ids:
        filtered = [
            object_id
            for object_id in legal
            if object_id not in {"questions", "choices"}
        ]
        for object_id in legal:
            if object_id in {"questions", "choices"} and object_id not in filtered:
                excluded[object_id] = "assessment_form_without_source"
        return filtered, excluded

    selected = [approved_by_id.get(str(item_id)) for item_id in source_question_ids]
    if any(item is None for item in selected):
        for object_id in legal:
            excluded[object_id] = "approved_item_missing"
        return [], excluded

    kinds = [approved_item_kind(item) for item in selected]
    if len(kinds) == 1 and kinds[0] == "multiple_choice":
        filtered = [object_id for object_id in legal if object_id == "choices"]
    elif 1 <= len(kinds) <= 6 and set(kinds) == {"open_response"}:
        filtered = [object_id for object_id in legal if object_id == "questions"]
    else:
        filtered = []
    for object_id in legal:
        if object_id not in filtered:
            excluded[object_id] = "approved_item_kind_mismatch"
    return filtered, excluded


def derive_print_block_candidates(
    *,
    block_id: str,
    intent: str,
    action: str | None,
    package_compatible: Sequence[str],
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    form_cards: Mapping[str, Mapping[str, Any]] | None = None,
    source_question_ids: Sequence[str] | None = None,
    approved_items: Sequence[Any] | None = None,
    remaining_budgets: Mapping[str, int] | None = None,
) -> PrintBlockCandidates:
    """Eligibility = package ∩ policy ∩ intent/action ∩ assets ∩ writer support."""
    body = dict(policy) if policy is not None else default_print_policy()
    offered = offered_form_ids(body)
    asset_required = forms_requiring_assets(body)
    assets = {str(item) for item in (available_asset_ids or []) if item}
    cards = dict(form_cards) if form_cards is not None else _form_cards()
    fallback_actions = _object_actions_fallback()
    budgets = {str(k): int(v) for k, v in (remaining_budgets or {}).items()}
    writer_view = load_form_writer_view().get("forms") or {}

    excluded: dict[str, str] = {}
    legal: list[str] = []
    requires_response = bool(action) and action not in PASSIVE_ACTIONS

    for form_id in sorted({str(item) for item in package_compatible if item}):
        if form_id in _NEVER_SELECTABLE_OBJECTS:
            excluded[form_id] = "never_selectable"
            continue
        if form_id not in _IMPLEMENTED_FORM_OBJECTS:
            excluded[form_id] = "writer_unsupported"
            continue
        if form_id not in offered:
            excluded[form_id] = "not_in_native_policy"
            continue
        if form_id not in writer_view and form_id not in _IMPLEMENTED_FORM_OBJECTS:
            excluded[form_id] = "writer_view_missing"
            continue

        card = cards.get(form_id)
        intents = set((card or {}).get("supported_intents") or ())
        actions = set((card or {}).get("supported_actions") or ())
        if not intents and not actions:
            actions = set(fallback_actions.get(form_id) or ())
        if intents and intent not in intents and card is not None:
            excluded[form_id] = "intent_unsupported"
            continue
        if action:
            if actions and action not in actions:
                if not (
                    action in PASSIVE_ACTIONS and actions.intersection(PASSIVE_ACTIONS)
                ):
                    excluded[form_id] = "action_unsupported"
                    continue
        if form_id in asset_required or bool((card or {}).get("requires_asset")):
            if not assets:
                excluded[form_id] = "asset_unavailable"
                continue
        if form_id in budgets and budgets[form_id] <= 0:
            excluded[form_id] = "budget_exhausted"
            continue
        legal.append(form_id)

    approved_by_id = {
        str(getattr(item, "id", "") or ""): item for item in (approved_items or [])
    }
    filtered, item_excluded = _apply_approved_item_filter(
        legal,
        source_question_ids=tuple(source_question_ids or ()),
        approved_by_id=approved_by_id,
    )
    excluded.update(item_excluded)

    return PrintBlockCandidates(
        block_id=block_id,
        intent=intent,
        action=action,
        candidates=tuple(filtered),
        excluded=excluded,
        requires_response=requires_response,
    )


def build_print_candidate_map(
    teaching_plan: Any,
    *,
    compatible_objects_by_intent: Mapping[str, Sequence[str]],
    available_asset_ids: Sequence[str] | None = None,
    policy: Mapping[str, Any] | None = None,
    approved_items: Sequence[Any] | None = None,
    fail_on_empty_required: bool = True,
) -> dict[str, tuple[str, ...]]:
    """Per-block closed candidate set for the Print selector prompt + validator."""
    cards = _form_cards()
    body = dict(policy) if policy is not None else default_print_policy()
    out: dict[str, tuple[str, ...]] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            action = None
            if getattr(block, "learner_action", None) is not None:
                action = str(block.learner_action.action)
            package = tuple(
                str(item)
                for item in compatible_objects_by_intent.get(block.intent, ())
                if item
            )
            derived = derive_print_block_candidates(
                block_id=block.id,
                intent=block.intent,
                action=action,
                package_compatible=package,
                available_asset_ids=available_asset_ids,
                policy=body,
                form_cards=cards,
                source_question_ids=getattr(block, "source_question_ids", ()) or (),
                approved_items=approved_items,
            )
            if fail_on_empty_required and not derived.candidates:
                raise NoCompatiblePrintCapabilityError(
                    block_id=block.id,
                    intent=block.intent,
                    action=action,
                    constraints={
                        "package_compatible": list(package),
                        "policy_offered": sorted(offered_form_ids(body)),
                        "excluded": derived.excluded,
                    },
                    reason="empty legal form set after package ∩ policy ∩ action ∩ assets",
                )
            out[block.id] = derived.candidates
    return out


__all__ = [
    "PASSIVE_ACTIONS",
    "NoCompatiblePrintCapabilityError",
    "PrintBlockCandidates",
    "build_print_candidate_map",
    "derive_print_block_candidates",
    "load_form_selection_view",
    "load_form_writer_view",
]

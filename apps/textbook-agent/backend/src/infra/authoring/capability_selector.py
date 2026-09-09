"""Shared curriculum-safe capability selector for Learn and Print native paths."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CapabilitySelectionErrorCode = Literal[
    "OUT_OF_SET",
    "REQUIRED_OMITTED",
    "SELECTOR_EXHAUSTED",
]


class CapabilitySelectionError(ValueError):
    def __init__(
        self,
        code: CapabilitySelectionErrorCode,
        message: str,
        *,
        path: str = "",
    ) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


class CapabilitySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    reason: str = ""


ChooseFn = Callable[[dict[str, Any]], Awaitable[CapabilitySelection] | CapabilitySelection]


def capability_records_from_view(
    view: Mapping[str, Any],
    *,
    collection_key: str,
) -> dict[str, Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in view.get(collection_key) or []:
        if isinstance(row, Mapping) and row.get("id"):
            by_id[str(row["id"])] = row
    return by_id


def build_capability_selector_context(
    *,
    candidate_ids: Sequence[str],
    selection_view: Mapping[str, Any],
    collection_key: str,
    brief: str,
    intent: str,
    action: str | None = None,
    lane: str = "capability",
    required: bool = False,
    teaching_context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    by_id = capability_records_from_view(selection_view, collection_key=collection_key)
    eligible = [
        {
            "id": capability_id,
            "choose_when": str((by_id.get(capability_id) or {}).get("choose_when") or ""),
            "reject_when": str((by_id.get(capability_id) or {}).get("reject_when") or ""),
        }
        for capability_id in candidate_ids
    ]
    payload: dict[str, Any] = {
        "lane": lane,
        "required_interaction": required,
        "block": {
            "brief": brief,
            "intent": intent,
            "action": action,
        },
        "eligible_candidates": eligible,
        "candidate_ids": [str(item) for item in candidate_ids],
    }
    if teaching_context:
        payload["teaching_context"] = dict(teaching_context)
    if constraints:
        payload["constraints"] = dict(constraints)
    return payload


def _validate_selection(
    selection: CapabilitySelection,
    *,
    candidate_ids: Sequence[str],
    required: bool,
) -> list[str]:
    errors: list[str] = []
    allowed = {str(item) for item in candidate_ids}
    chosen = str(selection.capability_id or "").strip()
    if not chosen:
        if required:
            errors.append("required capability omitted")
        return errors
    if chosen not in allowed:
        errors.append(f"capability_id {chosen!r} not in eligible shortlist {sorted(allowed)}")
    return errors


async def select_capability_from_shortlist(
    *,
    candidate_ids: Sequence[str],
    brief: str,
    intent: str,
    action: str | None = None,
    lane: str = "capability",
    required: bool = False,
    selection_view: Mapping[str, Any] | None = None,
    collection_key: str = "capabilities",
    teaching_context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    choose: ChooseFn | None = None,
) -> CapabilitySelection:
    """Select from a closed shortlist. Sole candidate is automatic; ambiguous invokes choose."""
    ids = [str(item) for item in candidate_ids if str(item)]
    if not ids:
        if required:
            raise CapabilitySelectionError(
                "REQUIRED_OMITTED",
                f"required {lane} shortlist is empty",
                path=lane,
            )
        raise CapabilitySelectionError(
            "OUT_OF_SET",
            f"empty {lane} shortlist",
            path=lane,
        )
    if len(ids) == 1:
        return CapabilitySelection(
            capability_id=ids[0],
            reason="sole eligible closed candidate",
        )

    choose_fn = choose or default_capability_choose
    context = build_capability_selector_context(
        candidate_ids=ids,
        selection_view=selection_view or {},
        collection_key=collection_key,
        brief=brief,
        intent=intent,
        action=action,
        lane=lane,
        required=required,
        teaching_context=teaching_context,
        constraints=constraints,
    )

    async def _call(payload: dict[str, Any]) -> CapabilitySelection:
        result = choose_fn(payload)
        if inspect.isawaitable(result):
            return await result
        return result

    selection = await _call(context)
    errors = _validate_selection(selection, candidate_ids=ids, required=required)
    if not errors:
        return selection

    repair_payload = {
        **context,
        "repair": True,
        "validation_errors": errors,
        "instruction": (
            "Your previous selection was invalid. Repair using only candidate_ids. "
            "Do not invent IDs outside the shortlist."
        ),
    }
    selection = await _call(repair_payload)
    errors = _validate_selection(selection, candidate_ids=ids, required=required)
    if errors:
        raise CapabilitySelectionError(
            "SELECTOR_EXHAUSTED",
            "; ".join(errors),
            path=lane,
        )
    return selection


async def default_capability_choose(context: dict[str, Any]) -> CapabilitySelection:
    from curriculum.agents import run_capability_selector

    return await run_capability_selector(context)


__all__ = [
    "CapabilitySelection",
    "CapabilitySelectionError",
    "CapabilitySelectionErrorCode",
    "ChooseFn",
    "build_capability_selector_context",
    "capability_records_from_view",
    "default_capability_choose",
    "select_capability_from_shortlist",
]

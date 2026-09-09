"""Exact approved-source resolution for Learn authoring (R02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from curriculum.approved_items import approved_item_kind
from curriculum.teaching_plan.compatibility import (
    ActionSourceIncompatibleError,
    assert_action_compatible_with_sources,
    expected_source_kind_for_action,
)
from infra.authoring import AuthoringEngineError
from learn.generation.work_orders import LearnWorkOrder


AuthoringMode = Literal["generate", "convert-approved"]

_MULTI_SOURCE_CONVERTERS = frozenset(
    {
        "learn.quizContentToInteractionContract",
        "learn.fillBlankContentToInteractionContract",
    }
)


@dataclass(frozen=True)
class ResolvedLearnSources:
    ref_ids: tuple[str, ...]
    items: tuple[dict[str, Any], ...]
    mode: AuthoringMode
    primary_item: dict[str, Any] | None


def _item_id(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("id") or "")
    return str(getattr(item, "id", "") or "")


def _item_mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    return dict(vars(item))


def _index_pool(pool: Sequence[Any] | None) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for raw in pool or []:
        item_id = _item_id(raw)
        if not item_id:
            continue
        if item_id in indexed:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                f"duplicate ambiguous approved item id {item_id!r} in pool",
                stage="inputs",
            )
        indexed[item_id] = _item_mapping(raw)
    return indexed


def _supports_multi_source(order: LearnWorkOrder) -> bool:
    definition = order.authoring_definition or {}
    converter_ref = str(definition.get("converter_ref") or "")
    return converter_ref in _MULTI_SOURCE_CONVERTERS


def resolve_learn_work_order_sources(
    order: LearnWorkOrder,
    pool: Sequence[Any] | None,
    *,
    forced_mode: str | None = None,
) -> ResolvedLearnSources:
    """Resolve explicit approved-item references from the pool only."""
    ref_ids = tuple(str(item_id) for item_id in order.approved_item_ids if str(item_id))
    if not ref_ids:
        mode: AuthoringMode = "generate"
        if forced_mode in {"generate", "convert-approved"}:
            mode = forced_mode  # type: ignore[assignment]
        return ResolvedLearnSources((), (), mode, None)

    indexed = _index_pool(pool)
    missing = [item_id for item_id in ref_ids if item_id not in indexed]
    if missing:
        raise AuthoringEngineError(
            "INCOMPATIBLE_APPROVED_ITEM",
            f"approved item(s) missing from pool: {', '.join(missing)}",
            stage="inputs",
        )

    if len(ref_ids) > 1 and not _supports_multi_source(order):
        raise AuthoringEngineError(
            "INCOMPATIBLE_APPROVED_ITEM",
            f"capability {order.capability_id!r} does not support multi-source conversion",
            stage="inputs",
        )

    items = tuple(indexed[item_id] for item_id in ref_ids)

    if order.action is not None:
        expected = expected_source_kind_for_action(order.action)
        kinds = [approved_item_kind(item) for item in items]
        if expected is not None and any(kind != expected for kind in kinds):
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                f"approved task type {kinds} incompatible with action "
                f"{order.action!r} / capability {order.capability_id!r}; expected {expected!r}",
                stage="inputs",
            )
        try:
            assert_action_compatible_with_sources(action=order.action, source_items=items)
        except ActionSourceIncompatibleError as exc:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                str(exc),
                stage="inputs",
            ) from exc

    if order.source_refs and set(order.source_refs) != set(ref_ids):
        raise AuthoringEngineError(
            "INCOMPATIBLE_APPROVED_ITEM",
            "approved_item_ids must agree with work-order source_refs",
            stage="inputs",
        )

    mode = "convert-approved"
    if forced_mode in {"generate", "convert-approved"}:
        mode = forced_mode  # type: ignore[assignment]
    elif order.authoring_mode != "approved_item":
        mode = "generate"

    primary = items[0] if mode == "convert-approved" and items else None
    return ResolvedLearnSources(ref_ids, items, mode, primary)


__all__ = ["ResolvedLearnSources", "resolve_learn_work_order_sources"]

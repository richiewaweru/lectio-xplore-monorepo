"""Exact approved-source resolution for Print authoring (R03)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from infra.authoring import AuthoringEngineError
from print.generation.work_orders import PrintWorkOrder


AuthoringMode = Literal["generate", "convert-approved"]


@dataclass(frozen=True)
class ResolvedPrintSources:
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


def resolve_print_work_order_sources(
    order: PrintWorkOrder,
    pool: Sequence[Any] | None,
    *,
    forced_mode: str | None = None,
) -> ResolvedPrintSources:
    """Resolve explicit source_refs from the pool only (never pool positional)."""
    ref_ids = tuple(str(item_id) for item_id in order.source_refs if str(item_id))
    if not ref_ids:
        mode: AuthoringMode = "generate"
        if forced_mode in {"generate", "convert-approved"}:
            mode = forced_mode  # type: ignore[assignment]
        return ResolvedPrintSources(ref_ids=(), items=(), mode=mode, primary_item=None)

    indexed = _index_pool(pool)
    items: list[dict[str, Any]] = []
    for ref_id in ref_ids:
        item = indexed.get(ref_id)
        if item is None:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                f"approved source ref {ref_id!r} not found in pool",
                stage="inputs",
            )
        items.append(item)
    mode = "convert-approved"
    if forced_mode in {"generate", "convert-approved"}:
        mode = forced_mode  # type: ignore[assignment]
    primary = items[0] if items else None
    return ResolvedPrintSources(
        ref_ids=ref_ids,
        items=tuple(items),
        mode=mode,
        primary_item=primary,
    )


__all__ = ["ResolvedPrintSources", "resolve_print_work_order_sources"]

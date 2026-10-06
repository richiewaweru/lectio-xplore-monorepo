"""Per-figure progress: planned figures joined to their media work items.

``plan_visual_figures`` reads the approved Teaching Plan ledger read-only and
lists one expected figure per plan block that carries a ``visual`` spec (the
figure node id is the code-owned id from ``composer.figure_item_for_block``).
``project_figures`` joins those to the Run's media work items so a teacher sees
every figure as planned / pending / ready / failed with a safe error code.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from curriculum.models import FigureProgressDTO
from curriculum.teaching_plan.models import TeachingPlanBlock
from document.shared_lesson.auto_retry import is_leaf_auto_retryable
from document.shared_lesson.composer import figure_item_for_block

_MEDIA_STAGE = "media_generation"
_FAILED = frozenset({"failed_recoverable", "failed_terminal", "cancelled"})


@dataclass(frozen=True)
class PlannedFigure:
    figure_id: str
    section_id: str
    section_title: str | None
    block_id: str
    required: bool


def plan_visual_figures(
    page_state: Mapping[str, Any] | None, *, revision: int
) -> list[PlannedFigure]:
    """Expected figures of one approved plan revision (never raises, never mutates)."""
    if not isinstance(page_state, Mapping):
        return []
    plan: Mapping[str, Any] | None = None
    for record in page_state.get("teaching_revisions") or []:
        if isinstance(record, Mapping) and record.get("revision") == revision:
            candidate = record.get("plan")
            plan = candidate if isinstance(candidate, Mapping) else None
            break
    if plan is None:
        return []
    planned: list[PlannedFigure] = []
    for section in plan.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        slot_id = str(section.get("slot_id") or "")
        if not slot_id:
            continue
        title = section.get("display_title")
        for block in section.get("blocks") or []:
            if not isinstance(block, Mapping) or not isinstance(block.get("visual"), Mapping):
                continue
            try:
                parsed = TeachingPlanBlock.model_validate(block)
            except ValueError:
                continue
            visual = block["visual"]
            planned.append(
                PlannedFigure(
                    figure_id=figure_item_for_block(slot_id, parsed).id,
                    section_id=slot_id,
                    section_title=str(title) if title else None,
                    block_id=parsed.id,
                    required=bool(visual.get("required", True)),
                )
            )
    return planned


def _identity(item: Any) -> dict[str, Any]:
    raw = getattr(item, "composition_identity", None)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_media(item: Any) -> bool:
    return item.stage == _MEDIA_STAGE or str(item.item_key).startswith("media:")


def active_leaves(items: Sequence[Any]) -> list[Any]:
    replaced = {
        getattr(item, "replaces_work_item_id", None)
        for item in items
        if getattr(item, "replaces_work_item_id", None)
    }
    return [item for item in items if getattr(item, "id", None) not in replaced]


def project_figures(
    planned: Sequence[PlannedFigure],
    items: Sequence[Any],
    *,
    run_auto_retrying: bool = False,
) -> list[FigureProgressDTO]:
    """One record per expected figure, plus any media item the plan did not predict."""
    media_by_figure: dict[str, Any] = {}
    for item in active_leaves([i for i in items if _is_media(i)]):
        figure_id = _identity(item).get("figure_node_id")
        media_by_figure[str(figure_id) if figure_id else str(item.item_key)] = item

    records: list[FigureProgressDTO] = []
    seen: set[str] = set()

    def record(
        *,
        figure_id: str,
        section_id: str | None,
        section_title: str | None,
        block_id: str | None,
        required: bool,
        item: Any | None,
    ) -> FigureProgressDTO:
        if item is None:
            return FigureProgressDTO(
                figure_id=figure_id,
                section_id=section_id,
                section_title=section_title,
                block_id=block_id,
                status="planned",
                required=required,
            )
        identity = _identity(item)
        warnings = [str(w) for w in identity.get("warnings") or []]
        output = item.output_json if isinstance(getattr(item, "output_json", None), dict) else {}
        if item.status == "ready" and output.get("status") == "unavailable":
            return FigureProgressDTO(
                figure_id=figure_id,
                section_id=section_id or identity.get("section_id"),
                section_title=section_title,
                block_id=block_id,
                status="unavailable",
                required=bool(identity.get("required", required)),
                error_code=str(output.get("error_code") or "") or None,
                error_summary=str(output.get("reason") or "") or None,
                attempt=item.attempt,
                max_attempts=item.max_attempts,
                warnings=warnings,
            )
        if item.status == "ready":
            status = "ready"
        elif item.status in _FAILED:
            status = "failed"
        else:
            status = "pending"
        failed = status == "failed"
        return FigureProgressDTO(
            figure_id=figure_id,
            section_id=section_id or identity.get("section_id"),
            section_title=section_title,
            block_id=block_id,
            status=status,
            required=bool(identity.get("required", required)),
            error_code=item.error_code if failed else None,
            error_summary=item.error_summary if failed else None,
            retryable=failed
            and item.status == "failed_recoverable"
            and item.recovery_action == "retry",
            recovery_action=(item.recovery_action or None) if failed else None,
            attempt=item.attempt,
            max_attempts=item.max_attempts,
            auto_retrying=failed and run_auto_retrying and is_leaf_auto_retryable(item),
            warnings=warnings,
        )

    for figure in planned:
        seen.add(figure.figure_id)
        records.append(
            record(
                figure_id=figure.figure_id,
                section_id=figure.section_id,
                section_title=figure.section_title,
                block_id=figure.block_id,
                required=figure.required,
                item=media_by_figure.get(figure.figure_id),
            )
        )
    for figure_id, item in media_by_figure.items():
        if figure_id in seen:
            continue
        records.append(
            record(
                figure_id=figure_id,
                section_id=None,
                section_title=None,
                block_id=None,
                required=True,
                item=item,
            )
        )
    return records


def figures_label(*, ready: int, failed: int, total: int, unavailable: int = 0) -> str:
    if total and ready + unavailable >= total:
        if unavailable:
            return f"Figures: {ready} ready / {unavailable} unavailable"
        return f"Figures: {total} ready"
    parts = [f"{ready} ready"]
    if unavailable:
        parts.append(f"{unavailable} unavailable")
    if failed:
        parts.append(f"{failed} failed")
    parts.append(f"{total} planned")
    return "Figures: " + " / ".join(parts)


__all__ = [
    "PlannedFigure",
    "figures_label",
    "plan_visual_figures",
    "project_figures",
]

"""Learn figure asset pipeline — caption/alt from the writer, image via execute_visual.

Does not import print/. Builds a VisualGeneratorWorkOrder and calls the shared
visual executor, then attaches a resolvable asset_id onto the figure node.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping
from urllib.parse import urlsplit

from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

logger = logging.getLogger(__name__)


class FigurePipelineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _local_image_key(src: str) -> str | None:
    raw = str(src or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    path = parsed.path if parsed.scheme or parsed.netloc else raw.split("?", 1)[0]
    prefix = "/images/"
    if path.startswith(prefix):
        key = path[len(prefix) :].strip("/")
        parts = [p for p in key.split("/") if p]
        if parts and not any(p in {".", ".."} for p in parts):
            return "/".join(parts)
    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("data:"):
        return raw
    if raw.startswith("/"):
        return raw
    return raw or None


def _work_order_for_figure(
    *,
    generation_id: str,
    node_id: str,
    caption: str,
    alt: str,
    teaching_block: Mapping[str, Any],
    lesson_context: Mapping[str, Any] | None = None,
) -> VisualGeneratorWorkOrder:
    request_id = f"learn-fig-{generation_id}-{node_id}"[:80]
    brief = str(teaching_block.get("brief") or "").strip()
    evidence = str(teaching_block.get("evidence") or "").strip()
    intent = str(teaching_block.get("intent") or "illustrate").strip()
    ctx = dict(lesson_context or {})
    objective = str(ctx.get("objective") or ctx.get("title") or "").strip()
    terminology = [
        str(t).strip() for t in (ctx.get("terminology") or []) if str(t).strip()
    ]
    source_of_truth: list[dict[str, str]] = []
    if objective:
        source_of_truth.append({"key": "lesson.objective", "text": objective})
    if brief:
        source_of_truth.append({"key": f"block.{node_id}.brief", "text": brief})
    if evidence:
        source_of_truth.append({"key": f"block.{node_id}.evidence", "text": evidence})
    if caption:
        source_of_truth.append({"key": f"figure.{node_id}.caption", "text": caption})
    purpose = (caption or alt or intent or "lesson concept diagram").strip()[:120]
    return VisualGeneratorWorkOrder(
        work_order_id=f"learn-visual:{request_id}",
        resource_type="lesson",
        dependency="blueprint_only",
        visual=VisualPlanItem(
            id=request_id,
            attaches_to=node_id,
            component_id=node_id,
            mode="diagram",
            visual_style="diagram_precision",
            purpose=purpose,
            must_show=[
                "Show the requested semantic structure with shapes and arrows; no additional text."
            ],
            must_not_show=[],
            labels_required=terminology,
        ),
        source_of_truth=source_of_truth,
    )


async def _noop_emit(_event: str, _payload: dict[str, Any]) -> None:
    return None


async def attach_figure_asset(
    node: Mapping[str, Any],
    *,
    generation_id: str,
    teaching_block: Mapping[str, Any],
    lesson_context: Mapping[str, Any] | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """Run the visual pipeline for a figure node and set asset_id.

    Stage-local retries: figure failure → figure stage retry (max_attempts).
    """
    if str(node.get("kind") or "") != "figure":
        return dict(node)
    if node.get("asset_id"):
        return dict(node)

    node_id = str(node.get("id") or "figure")
    caption = str(node.get("caption") or "").strip()
    alt = str(node.get("alt") or caption).strip()
    order = _work_order_for_figure(
        generation_id=generation_id,
        node_id=node_id,
        caption=caption,
        alt=alt,
        teaching_block=teaching_block,
        lesson_context=lesson_context,
    )

    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            blocks = await execute_visual(
                order,
                _noop_emit,
                trace_id=f"learn-visual:{generation_id}:{node_id}:a{attempt}",
                generation_id=generation_id,
                bypass_cache_read=attempt > 1,
            )
            block = blocks[0] if blocks else None
            if block is None:
                last_error = "visual executor returned no blocks"
                continue
            src = getattr(block, "fallback_image_url", None) or getattr(
                block, "image_url", None
            )
            status = str(getattr(block, "status", "") or "")
            asset_id = _local_image_key(str(src or ""))
            if asset_id and status in {
                "ready",
                "ready_with_quality_warning",
                "flagged_quality",
            }:
                out = dict(node)
                out["asset_id"] = asset_id
                return out
            last_error = (
                str(getattr(block, "error_message", "") or "").strip()
                or f"visual status={status!r} src={src!r}"
            )
        except Exception as exc:  # noqa: BLE001 — stage-local retry
            last_error = str(exc)[:500]
            logger.warning(
                "learn figure attempt %s failed for %s: %s",
                attempt,
                node_id,
                last_error,
            )

    raise FigurePipelineError(
        "FIGURE_ASSET_FAILED",
        last_error or f"could not produce asset for figure {node_id!r}",
    )


__all__ = ["FigurePipelineError", "attach_figure_asset"]

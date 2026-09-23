"""Learn figure asset pipeline — caption/alt from the writer, image via execute_visual.

Does not import print/. Builds a VisualGeneratorWorkOrder and calls the shared
visual executor, then attaches a resolvable asset_id onto the figure node.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from core.prompts.loader import effective_prompt_text
from media.generation.executor import execute_visual
from media.generation.contracts import VisualGeneratorWorkOrder, VisualPlanItem

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
    if raw.startswith(("http://", "https://", "data:")):
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
    source_of_truth.append(
        {
            "key": "figure.authoring_policy",
            "text": effective_prompt_text("figure-authoring"),
        }
    )
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
    budget_ledger: Any | None = None,
    work_item_id: str | None = None,
    durable_persist_hook: Any | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
) -> dict[str, Any]:
    """Run the visual pipeline for a figure node and set asset_id.

    Stage-local retries: figure failure → figure stage retry (max_attempts).
    When ``budget_ledger`` is provided, each physical visual attempt reserves a
    durable call slot before dispatch (C01/C04).
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
    budget_key = work_item_id or f"learn-media:{node_id}"
    budget = None
    if budget_ledger is not None:
        from infra.execution.call_budget import CallBudgetLedger

        if isinstance(budget_ledger, CallBudgetLedger):
            budget = budget_ledger.get_or_create(budget_key, max_calls=max(3, max_attempts))

    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        reserved = None
        try:
            if budget is not None:
                reserved = budget.reserve()
                budget_ledger.persist(budget)
                if durable_persist_hook is not None:
                    maybe = durable_persist_hook()
                    if inspect.isawaitable(maybe):
                        await maybe
            if progress_store is not None and progress_run_id:
                try:
                    progress_store.append_event(
                        progress_run_id,
                        event_type="media_attempt",
                        path="learn",
                        stage="media",
                        item_id=budget_key,
                        attempt=attempt,
                    )
                except Exception:
                    logger.debug("media progress event skipped", exc_info=True)
            blocks = await execute_visual(
                order,
                _noop_emit,
                trace_id=f"learn-visual:{generation_id}:{node_id}:a{attempt}",
                generation_id=generation_id,
                bypass_cache_read=attempt > 1,
            )
            if budget is not None and reserved is not None:
                budget.mark_dispatched(reserved)
                budget_ledger.persist(budget)
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
            if budget is not None and reserved is not None:
                budget.mark_ambiguous(reserved)
                budget_ledger.persist(budget)
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

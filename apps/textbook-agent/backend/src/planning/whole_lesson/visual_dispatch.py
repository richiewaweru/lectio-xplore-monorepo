"""Native visual dispatch — reuse existing VisualGeneratorWorkOrder / execute_visual."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from planning.whole_lesson.figure_ids import stable_figure_request_id
from planning.whole_lesson.repository import PageDocumentRepository
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

logger = logging.getLogger(__name__)

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def figure_work_order_from_pending(
    *,
    generation_id: str,
    block_id: str,
    content: dict[str, Any],
    request_id: str | None = None,
    intent: str = "",
) -> VisualGeneratorWorkOrder:
    """Map a visual_pending figure block to one stable VisualGeneratorWorkOrder."""
    rid = request_id or stable_figure_request_id(
        generation_id=generation_id, block_id=block_id
    )
    alt = str(content.get("alt_text") or content.get("caption") or "Figure").strip()
    caption = str(content.get("caption") or alt).strip()
    must_show = [
        item
        for item in (content.get("must_show") or [])
        if isinstance(item, str) and item.strip()
    ]
    if not must_show:
        must_show = [alt]
    must_not = [
        item
        for item in (content.get("must_not_show") or [])
        if isinstance(item, str) and item.strip()
    ]
    return VisualGeneratorWorkOrder(
        work_order_id=f"native-visual:{rid}",
        resource_type="lesson",
        dependency="blueprint_only",
        visual=VisualPlanItem(
            id=rid,
            attaches_to=block_id,
            component_id=block_id,
            mode="diagram",
            purpose=caption or intent or alt,
            must_show=must_show,
            must_not_show=must_not,
            labels_required=[],
        ),
        source_of_truth=[],
    )


def collect_pending_figure_dispatches(
    *,
    generation_id: str,
    block_execution: dict[str, dict[str, Any]],
) -> list[tuple[str, str, VisualGeneratorWorkOrder]]:
    """Return (block_id, request_id, work_order) for unresolved pending figures."""
    out: list[tuple[str, str, VisualGeneratorWorkOrder]] = []
    seen: set[str] = set()
    for outcome in block_execution.values():
        if not isinstance(outcome, dict):
            continue
        if str(outcome.get("object") or "") != "figure":
            continue
        if str(outcome.get("status") or "") not in {
            "visual_pending",
            "ready",
            "failed_recoverable",
            "failed",
        }:
            continue
        content = dict(outcome.get("content") or {})
        asset = dict(content.get("asset") or {})
        status = str(asset.get("status") or "pending")
        if status in {"ready", "generating"}:
            continue
        if status not in {"pending", "failed", ""}:
            continue
        block_id = str(outcome.get("block_id") or "")
        if not block_id:
            continue
        request_id = str(
            outcome.get("request_id")
            or asset.get("request_id")
            or stable_figure_request_id(generation_id=generation_id, block_id=block_id)
        )
        if request_id in seen:
            continue
        seen.add(request_id)
        order = figure_work_order_from_pending(
            generation_id=generation_id,
            block_id=block_id,
            content=content,
            request_id=request_id,
            intent=str(outcome.get("intent") or ""),
        )
        out.append((block_id, request_id, order))
    return out


async def _noop_emit(_event: str, _payload: dict[str, Any]) -> None:
    return None


async def dispatch_native_pending_visuals(
    *,
    generation_id: str,
    block_execution: dict[str, dict[str, Any]],
    apply_completion: Callable[..., Any],
    emit_event: EmitFn | None = None,
    execute_visual_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Invoke existing execute_visual once per pending request_id and patch via callback."""
    executor = execute_visual_fn or execute_visual
    emit = emit_event or _noop_emit
    dispatches = collect_pending_figure_dispatches(
        generation_id=generation_id,
        block_execution=block_execution,
    )
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for block_id, request_id, order in dispatches:
        asset_error: str | None = None
        try:
            blocks = await executor(
                order,
                emit,
                trace_id=f"native-visual:{generation_id}:{request_id}",
                generation_id=generation_id,
            )
            block = blocks[0] if blocks else None
            src = None
            status = "failed"
            if block is not None:
                src = getattr(block, "fallback_image_url", None) or getattr(
                    block, "image_url", None
                )
                block_status = str(getattr(block, "status", "") or "")
                status = "ready" if block_status == "ready" and src else (
                    "ready" if block_status == "ready" else "failed"
                )
                if status == "ready" and not src:
                    # Simulation / placeholder-ready without URL still resolves text path.
                    src = getattr(block, "html_content", None)
            asset = {
                "status": status if src or status == "failed" else "failed",
                "request_id": request_id,
                "kind": "image",
                "src": src if isinstance(src, str) and src.startswith(("http", "data:", "/")) else (
                    None if status != "ready" else src
                ),
            }
            if status == "ready" and asset["src"] is None and isinstance(src, str):
                # Non-URL ready content still marks asset ready for document patching.
                asset["src"] = src
                asset["kind"] = "image"
        except Exception as exc:  # noqa: BLE001
            asset_error = str(exc)[:500]
            asset = {
                "status": "failed",
                "request_id": request_id,
                "kind": "image",
                "src": None,
            }
            logger.exception(
                "native visual dispatch failed generation_id=%s request_id=%s",
                generation_id,
                request_id,
            )
        completion = await apply_completion(
            request_id=request_id,
            asset=asset,
            supplied_block_id=block_id,
        )
        revision = None
        if completion is not None:
            revision = getattr(completion, "document_revision", None)
            if revision is None and isinstance(completion, dict):
                revision = completion.get("document_revision")
        row = {
            "block_id": block_id,
            "request_id": request_id,
            "work_order_id": order.work_order_id,
            "asset_status": asset["status"],
            "document_revision": revision,
        }
        if asset_error:
            row["error"] = asset_error
        if asset["status"] == "failed":
            failures.append(row)
        results.append(row)
    return {
        "dispatched": len(results),
        "results": results,
        "failed": len(failures),
        "failures": failures,
    }


async def dispatch_and_patch_from_repo(
    *,
    session: Any,
    generation_id: str,
    execute_visual_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    repo = PageDocumentRepository(session, generation_id)
    block_execution = await repo.load_block_results()

    async def _apply(**kwargs: Any) -> Any:
        return await repo.apply_visual_completion(**kwargs)

    result = await dispatch_native_pending_visuals(
        generation_id=generation_id,
        block_execution=block_execution,
        apply_completion=_apply,
        execute_visual_fn=execute_visual_fn,
    )
    failures = list(result.get("failures") or [])
    if failures:
        failed_ids = [
            str(row.get("request_id") or "")
            for row in failures
            if row.get("request_id")
        ]
        message = "; ".join(
            str(row.get("error") or row.get("asset_status") or "failed")
            for row in failures[:3]
        )
        await repo.persist_visual_dispatch_failure(
            message=message or "visual dispatch failed",
            failed_request_ids=failed_ids,
        )
        result["error"] = "visual_dispatch_failed"
        result["retryable"] = True
    else:
        # Successful redispath of pending figures — drop prior visual last_error.
        try:
            await repo.clear_visual_last_error()
        except Exception:  # noqa: BLE001
            pass
    return result

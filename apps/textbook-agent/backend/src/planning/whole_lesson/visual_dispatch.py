"""Native visual dispatch — reuse existing VisualGeneratorWorkOrder / execute_visual."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Awaitable, Callable
import hashlib
import json
import time
from urllib.parse import urlsplit

from planning.whole_lesson.figure_ids import stable_figure_request_id
from planning.whole_lesson.repository import PageDocumentRepository
from planning.whole_lesson import visual_topology_recovery as topology_recovery
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

logger = logging.getLogger(__name__)

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _local_image_key_from_src(src: Any) -> str | None:
    """Derive a safe local image-store key from the native image route only."""
    raw = str(src or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    path = parsed.path if parsed.scheme or parsed.netloc else raw.split("?", 1)[0]
    prefix = "/images/"
    if not path.startswith(prefix):
        return None
    key = path[len(prefix) :].strip("/")
    parts = [part for part in key.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    # Only the app's own local image route may be converted. Never turn an
    # arbitrary remote URL into an internal store key.
    if parsed.scheme and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return None
    return "/".join(parts)


def _rendered_source_valid(src: Any) -> bool:
    """Accept only a source the document renderer can actually resolve."""
    raw = str(src or "").strip()
    if not raw:
        return False
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if raw.startswith("data:image/"):
        return True
    return bool(_local_image_key_from_src(raw))


def _visual_failure_kind(message: str) -> str:
    text = str(message or "").lower()
    if "upload" in text or "gcs" in text:
        return "upload_failure"
    if "attach" in text or "document" in text:
        return "attachment_failure"
    if "source" in text or "image_url" in text or "asset" in text:
        return "missing_asset"
    if "provider" in text or "generation_api" in text or "image_generation" in text:
        return "provider_failure"
    return "delivery_failure"


def figure_work_order_from_pending(
    *,
    generation_id: str,
    block_id: str,
    content: dict[str, Any],
    request_id: str | None = None,
    intent: str = "",
    teaching_block: Mapping[str, Any] | None = None,
    lesson_packet: Mapping[str, Any] | None = None,
    qc_correction_hint: str | None = None,
) -> VisualGeneratorWorkOrder:
    """Map a visual_pending figure block to one stable VisualGeneratorWorkOrder."""
    rid = request_id or stable_figure_request_id(
        generation_id=generation_id, block_id=block_id
    )
    teaching_block = teaching_block if isinstance(teaching_block, Mapping) else {}
    lesson_packet = lesson_packet if isinstance(lesson_packet, Mapping) else {}
    lesson = lesson_packet.get("lesson")
    lesson = lesson if isinstance(lesson, Mapping) else {}
    scope = lesson_packet.get("scope")
    scope = scope if isinstance(scope, Mapping) else {}
    block_brief = str(teaching_block.get("brief") or "").strip()
    block_evidence = str(teaching_block.get("evidence") or "").strip()
    objective = str(lesson.get("objective") or "").strip()
    anchor = lesson_packet.get("anchor")
    anchor = anchor if isinstance(anchor, Mapping) else {}
    must_establish_entries = scope.get("must_establish")
    must_establish: list[str] = []
    if isinstance(must_establish_entries, list):
        for entry in must_establish_entries:
            if isinstance(entry, Mapping):
                text = str(entry.get("statement") or "").strip()
            else:
                text = str(entry or "").strip()
            if text:
                must_establish.append(text)
    terminology = [
        str(term).strip()
        for term in (scope.get("terminology") or [])
        if str(term).strip()
    ]
    exclusions_entries = scope.get("must_not_introduce") or scope.get("exclusions")
    if not exclusions_entries:
        exclusions_entries = lesson_packet.get("exclusions")
    exclusions: list[str] = []
    if isinstance(exclusions_entries, list):
        for entry in exclusions_entries:
            if isinstance(entry, Mapping):
                text = str(entry.get("statement") or "").strip()
            else:
                text = str(entry or "").strip()
            if text:
                exclusions.append(text)

    must_show = [
        item
        for item in (content.get("must_show") or [])
        if isinstance(item, str) and item.strip()
    ]
    # Preserve the writer's visual constraints while grounding retries in the
    # persisted teaching block and immutable lesson packet.  The full records
    # are also retained in source_of_truth for downstream prompt/audit use.
    if not must_show:
        must_show = [
            "Show the requested semantic structure with shapes and arrows; no additional text."
        ]
    must_not = [
        item
        for item in (content.get("must_not_show") or [])
        if isinstance(item, str) and item.strip()
    ]
    for exclusion in exclusions:
        if exclusion not in must_not:
            must_not.append(exclusion)
    # Keep provider purpose compact and non-renderable; full persisted prose is
    # carried only in source_of_truth below.
    purpose = (intent or "lesson concept diagram").strip()[:120]
    source_of_truth = []
    if objective:
        source_of_truth.append({"key": "lesson.objective", "text": objective})
    if anchor:
        anchor_id = str(anchor.get("id") or "anchor").strip()
        anchor_description = str(anchor.get("description") or "").strip()
        if anchor_description:
            source_of_truth.append(
                {"key": f"lesson.anchor.{anchor_id}", "text": anchor_description}
            )
    if block_brief:
        source_of_truth.append({"key": f"block.{block_id}.brief", "text": block_brief})
    if block_evidence:
        source_of_truth.append({"key": f"block.{block_id}.evidence", "text": block_evidence})
    for index, statement in enumerate(must_establish):
        source_of_truth.append({"key": f"lesson.must_establish.{index}", "text": statement})
    for index, exclusion in enumerate(exclusions):
        source_of_truth.append({"key": f"lesson.exclusion.{index}", "text": exclusion})
    return VisualGeneratorWorkOrder(
        work_order_id=f"native-visual:{rid}",
        resource_type="lesson",
        dependency="blueprint_only",
        visual=VisualPlanItem(
            id=rid,
            attaches_to=block_id,
            component_id=block_id,
            mode="diagram",
            visual_style="diagram_precision",
            purpose=purpose,
            must_show=must_show,
            must_not_show=must_not,
            labels_required=terminology,
        ),
        source_of_truth=source_of_truth,
        qc_correction_hint=(str(qc_correction_hint).strip() or None)
        if qc_correction_hint
        else None,
    )


def collect_pending_figure_dispatches(
    *,
    generation_id: str,
    block_execution: dict[str, dict[str, Any]],
    teaching_blocks: Mapping[str, Mapping[str, Any]] | None = None,
    lesson_packet: Mapping[str, Any] | None = None,
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
        qc_meta = outcome.get("visual_qc")
        qc_meta = qc_meta if isinstance(qc_meta, Mapping) else {}
        if str(outcome.get("status") or "") not in {"failed", "failed_recoverable"} and status != "failed":
            # A first dispatch must not inherit stale correction metadata.
            qc_meta = {}
        order = figure_work_order_from_pending(
            generation_id=generation_id,
            block_id=block_id,
            content=content,
            request_id=request_id,
            intent=str(outcome.get("intent") or ""),
            teaching_block=(teaching_blocks or {}).get(block_id),
            lesson_packet=lesson_packet,
            qc_correction_hint=(
                str(qc_meta.get("correction_hint") or "").strip()
                or "; ".join(
                    str(reason).strip()
                    for reason in (qc_meta.get("reasons") or [])
                    if str(reason).strip()
                )
                or None
            ),
        )
        out.append((block_id, request_id, order))
    return out


async def _noop_emit(_event: str, _payload: dict[str, Any]) -> None:
    return None


def _topology_qc_adapter(
    work_order: VisualGeneratorWorkOrder,
    *,
    generation_id: str,
    request_id: str,
):
    """Bind a model-backed QC call to one topology recovery request."""

    async def _qc(
        *,
        rendered: Mapping[str, Any],
        topology: Mapping[str, Any],
        request_id: str,
        image_bytes: bytes | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from media.qc.visual_qc import evaluate_topology_raster_quality

        png = image_bytes
        if not isinstance(png, (bytes, bytearray)) or not png:
            raise topology_recovery.TopologyRecoveryError(
                "TOPOLOGY_QC_FAILED",
                f"final raster bytes missing for topology QC of {request_id!r}",
            )
        started = time.perf_counter()
        try:
            verdict = await evaluate_topology_raster_quality(
                image_bytes=bytes(png),
                order=work_order,
                trace_id=f"topology-qc:{generation_id}:{request_id}",
                generation_id=generation_id,
            )
        except Exception as exc:
            raise topology_recovery.TopologyRecoveryError(
                "TOPOLOGY_QC_FAILED",
                str(exc),
            ) from exc
        return {
            "status": str(verdict.verdict),
            "reasons": list(verdict.reasons or []),
            "correction_hint": str(verdict.correction_hint or ""),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "trace_id": f"topology-qc:{generation_id}:{request_id}",
        }

    return _qc


async def dispatch_native_pending_visuals(
    *,
    generation_id: str,
    block_execution: dict[str, dict[str, Any]],
    apply_completion: Callable[..., Any],
    emit_event: EmitFn | None = None,
    execute_visual_fn: Callable[..., Any] | None = None,
    teaching_blocks: Mapping[str, Mapping[str, Any]] | None = None,
    lesson_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke existing execute_visual once per pending request_id and patch via callback."""
    executor = execute_visual_fn or execute_visual
    emit = emit_event or _noop_emit
    dispatches = collect_pending_figure_dispatches(
        generation_id=generation_id,
        block_execution=block_execution,
        teaching_blocks=teaching_blocks,
        lesson_packet=lesson_packet,
    )
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for block_id, request_id, order in dispatches:
        outcome = next(
            (
                item
                for item in block_execution.values()
                if isinstance(item, dict)
                and str(item.get("request_id") or "") == request_id
            ),
            {},
        )
        asset_state = dict((outcome.get("content") or {}).get("asset") or {})
        bypass_cache_read = (
            str(asset_state.get("status") or "") == "failed"
            or str(outcome.get("status") or "") == "failed_recoverable"
        )
        asset_error: str | None = None
        block_error: str | None = None
        visual_qc: dict[str, Any] | None = None
        try:
            blocks = await executor(
                order,
                emit,
                trace_id=f"native-visual:{generation_id}:{request_id}",
                generation_id=generation_id,
                bypass_cache_read=bypass_cache_read,
            )
            block = blocks[0] if blocks else None
            src = None
            status = "failed"
            if block is not None:
                src = getattr(block, "fallback_image_url", None) or getattr(
                    block, "image_url", None
                )
                block_status = str(getattr(block, "status", "") or "")
                block_error = str(getattr(block, "error_message", "") or "").strip() or None
                # A QC flag is advisory once a concrete image source exists.
                # Deliver the image now and retain the QC payload so a later
                # replacement workflow can find it.
                source_valid = _rendered_source_valid(src)
                status = "ready" if block_status in {"ready", "ready_with_quality_warning"} and source_valid else "failed"
                if block_status in {"flagged_quality", "ready_with_quality_warning"} and source_valid:
                    status = "ready"
                if status == "ready" and not src:
                    # Simulation / placeholder-ready without URL still resolves text path.
                    src = getattr(block, "html_content", None)
                if block_status in {"flagged_quality", "ready_with_quality_warning"}:
                    visual_qc = {
                        "status": "flagged_quality",
                        "trace_id": getattr(block, "qc_trace_id", None)
                        or f"native-visual:{generation_id}:{request_id}",
                        "reasons": [
                            str(reason)
                            for reason in (getattr(block, "qc_reasons", None) or [])
                            if str(reason).strip()
                        ],
                        "correction_hint": getattr(
                            block, "qc_correction_hint", None
                        ),
                    }
            asset = {
                "status": status if src or status == "failed" else "failed",
                "request_id": request_id,
                "kind": "image",
            }
            if _rendered_source_valid(src):
                asset["src"] = src
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
            visual_qc=visual_qc,
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
        if visual_qc is not None:
            row["visual_qc"] = visual_qc
            row["diagnostic"] = "qc_warning"
        if asset_error:
            row["error"] = asset_error
        if block_error:
            row["error"] = block_error
        if asset["status"] == "failed":
            row["failure_kind"] = _visual_failure_kind(
                block_error or asset_error or "missing visual asset source"
            )
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
    topology_recovery_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    repo = PageDocumentRepository(session, generation_id)
    state = await repo.load_page_generation_state()
    block_execution = dict(state.get("block_execution") or {})
    teaching_blocks: dict[str, Mapping[str, Any]] = {}
    teaching_plan = state.get("teaching_plan")
    if isinstance(teaching_plan, Mapping):
        for section in teaching_plan.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for block in section.get("blocks") or []:
                if isinstance(block, Mapping) and block.get("id"):
                    teaching_blocks[str(block["id"])] = block
    lesson_packet = state.get("lesson_packet")

    # A renderer/compositor flagged figure carrying an internal source key is
    # routed through the provider-free topology recovery path.  Remove those
    # request ids from the normal dispatch set so execute_visual (and xAI) is
    # never called for this recovery mode.
    topology_results: list[dict[str, Any]] = []
    topology_request_ids: set[str] = set()
    recover = topology_recovery_fn or topology_recovery.recover_flagged_visual_topology
    for outcome in block_execution.values():
        if not isinstance(outcome, dict) or str(outcome.get("object") or "") != "figure":
            continue
        qc = outcome.get("visual_qc")
        if not isinstance(qc, Mapping):
            history = outcome.get("visual_qc_history")
            if isinstance(history, list):
                for candidate in reversed(history):
                    if isinstance(candidate, Mapping):
                        qc = candidate
                        break
        asset = dict((outcome.get("content") or {}).get("asset") or {})
        visual_error = outcome.get("error")
        has_visual_error = isinstance(visual_error, Mapping) and str(
            visual_error.get("code") or ""
        ) in {"VISUAL_DISPATCH", "VISUAL_COMPLETION"}
        if not (
            isinstance(qc, Mapping) and str(qc.get("status") or "") == "flagged_quality"
        ) and not has_visual_error:
            continue
        internal_key = str(
            asset.get("internal_asset_key") or asset.get("internal_key") or ""
        ).strip()
        if not internal_key:
            internal_key = _local_image_key_from_src(asset.get("src")) or ""
        # Native figure work orders are diagram-precision work orders. The
        # retry transition intentionally keeps only the renderable local src,
        # so reconstruct the recovery route from that local image-store key
        # when older persisted outcomes no longer retain visual_style metadata.
        if not internal_key:
            continue
        request_id = str(outcome.get("request_id") or asset.get("request_id") or "").strip()
        if not request_id:
            continue
        topology_request_ids.add(request_id)
        labels = [
            str(label).strip()
            for label in ((outcome.get("content") or {}).get("labels_required") or [])
            if str(label).strip()
        ]
        block_id = str(outcome.get("block_id") or "").strip()
        authoritative_source: dict[str, Any] = {
            "teaching_block": dict(teaching_blocks.get(block_id) or {}),
            "labels": labels,
            "labels_required": labels,
        }
        if isinstance(lesson_packet, Mapping):
            lesson = lesson_packet.get("lesson")
            scope = lesson_packet.get("scope")
            anchor = lesson_packet.get("anchor")
            if isinstance(lesson, Mapping):
                authoritative_source["lesson"] = {
                    "objective": str(lesson.get("objective") or ""),
                    "subject": str(lesson.get("subject") or ""),
                    "grade_level": str(lesson.get("grade_level") or ""),
                }
            if isinstance(scope, Mapping):
                authoritative_source["scope"] = {
                    "must_establish": scope.get("must_establish") or [],
                    "must_not_introduce": scope.get("must_not_introduce") or scope.get("exclusions") or [],
                    "terminology": scope.get("terminology") or [],
                }
                if not labels:
                    labels = [
                        str(label).strip()
                        for label in (scope.get("terminology") or [])
                        if str(label).strip()
                    ]
            if isinstance(anchor, Mapping):
                authoritative_source["anchor"] = {
                    "id": str(anchor.get("id") or ""),
                    "description": str(anchor.get("description") or ""),
                }
        evidence_keys: list[str] = []
        if authoritative_source.get("lesson", {}).get("objective"):
            evidence_keys.append("lesson.objective")
        anchor = authoritative_source.get("anchor") or {}
        if anchor.get("description"):
            evidence_keys.append(f"lesson.anchor.{anchor.get('id') or 'anchor'}")
        block = authoritative_source.get("teaching_block") or {}
        if block.get("brief"):
            evidence_keys.append(f"block.{block_id}.brief")
        if block.get("evidence"):
            evidence_keys.append(f"block.{block_id}.evidence")
        scope = authoritative_source.get("scope") or {}
        evidence_keys.extend(
            f"lesson.must_establish.{index}"
            for index, entry in enumerate(scope.get("must_establish") or [])
            if (entry.get("statement") if isinstance(entry, Mapping) else entry)
        )
        evidence_keys.extend(
            f"lesson.exclusion.{index}"
            for index, entry in enumerate(scope.get("must_not_introduce") or [])
            if (entry.get("statement") if isinstance(entry, Mapping) else entry)
        )
        authoritative_source["evidence_keys"] = evidence_keys
        authoritative_source["labels"] = labels
        authoritative_source["labels_required"] = labels
        source_text = " ".join(
            str(value).strip()
            for value in (
                (authoritative_source.get("lesson") or {}).get("objective"),
                (authoritative_source.get("teaching_block") or {}).get("brief"),
            )
            if str(value or "").strip()
        )
        source_digest = hashlib.sha256(
            json.dumps(authoritative_source, sort_keys=True, default=str).encode()
        ).hexdigest()
        qc_meta = qc if isinstance(qc, Mapping) else {}
        work_order = figure_work_order_from_pending(
            generation_id=generation_id,
            block_id=block_id,
            content=dict(outcome.get("content") or {}),
            request_id=request_id,
            intent=str(outcome.get("intent") or ""),
            teaching_block=teaching_blocks.get(block_id),
            lesson_packet=lesson_packet if isinstance(lesson_packet, Mapping) else None,
            qc_correction_hint=(
                str(qc_meta.get("correction_hint") or "").strip()
                or "; ".join(
                    str(reason).strip()
                    for reason in (qc_meta.get("reasons") or [])
                    if str(reason).strip()
                )
                or None
            ),
        )
        recover_kwargs: dict[str, Any] = {
            "session": session,
            "generation_id": generation_id,
            "request_id": request_id,
            "source_text": source_text,
            "source_digest": source_digest,
            "labels": labels,
            "internal_asset_key": internal_key,
            "persisted_source": authoritative_source,
            "supplied_block_id": block_id or None,
            "work_order": work_order,
        }
        if topology_recovery_fn is None:
            # This branch is already provider-free topology recovery. Its
            # compositor has a closed label/topology contract, so use the
            # deterministic raster preflight here; model-backed visual QC is
            # still used for ordinary provider-generated visual dispatch.
            recover_kwargs["qc_fn"] = topology_recovery._default_topology_qc
        try:
            recovered = await recover(**recover_kwargs)
            topology_results.append({"request_id": request_id, **recovered})
        except Exception as exc:  # keep retryable visual state; never fall through
            topology_results.append(
                {
                    "request_id": request_id,
                    "status": "awaiting_visuals",
                    "error": str(exc)[:500],
                    "recovery": "topology",
                }
            )

    if topology_request_ids:
        block_execution = {
            key: value
            for key, value in block_execution.items()
            if str(
                value.get("request_id")
                or ((value.get("content") or {}).get("asset") or {}).get("request_id")
                or ""
            ) not in topology_request_ids
        }

    async def _apply(**kwargs: Any) -> Any:
        return await repo.apply_visual_completion(**kwargs)

    result = await dispatch_native_pending_visuals(
        generation_id=generation_id,
        block_execution=block_execution,
        teaching_blocks=teaching_blocks,
        lesson_packet=lesson_packet if isinstance(lesson_packet, Mapping) else None,
        apply_completion=_apply,
        execute_visual_fn=execute_visual_fn,
    )
    if topology_results:
        result["topology_recovery"] = topology_results
        result["dispatched"] = int(result.get("dispatched") or 0) + len(topology_results)
        topology_failures = [
            item for item in topology_results if item.get("status") != "ready"
        ]
        result["failed"] = int(result.get("failed") or 0) + len(topology_failures)
        result.setdefault("failures", []).extend(topology_failures)
    failures = list(result.get("failures") or [])
    if failures:
        # A topology callback can finalize the document while a sibling
        # dispatch result is still being assembled. Do not overwrite the
        # truthful ready state (or raise an internal error) after that fence
        # has succeeded; the ready document is the authoritative outcome.
        from core.database.models import GenerationModel

        get_generation = getattr(getattr(repo, "session", None), "get", None)
        current_generation = (
            await get_generation(GenerationModel, generation_id)
            if callable(get_generation)
            else None
        )
        if current_generation is not None and str(current_generation.status or "") == "ready":
            result["failures"] = []
            result["failed"] = 0
            result.pop("error", None)
            result["retryable"] = False
            return result
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

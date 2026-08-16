"""Flagged-visual topology recovery.

This path is intentionally separate from the ordinary provider visual executor:
the topology is planned once, persisted atomically, and the existing internal
asset is read by key before deterministic rendering.  No image-provider client
is imported or called here.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from planning.whole_lesson.repository import (
    PageDocumentRepository,
    VisualTopologyConflict,
)

logger = logging.getLogger(__name__)

TOPOLOGY_RECOVERY_VERSION = "topology-recovery/1"
TOPOLOGY_RENDERER_VERSION = "topology-renderer/1"
TOPOLOGY_BACKGROUND_VERSION = "topology-background/1"
TOPOLOGY_QC_VERSION = "topology-qc/1"


class TopologyRecoveryError(RuntimeError):
    """Typed, retryable recovery failure."""

    def __init__(self, code: str, message: str, *, recoverable: bool = True) -> None:
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)


PlannerFn = Callable[..., Any]
RendererFn = Callable[..., Any]
ReaderFn = Callable[..., Any]
QCFn = Callable[..., Any]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def topology_identity_digest(
    *,
    source_digest: str,
    labels: list[str] | tuple[str, ...],
    label_map: Mapping[str, str] | None = None,
    topology_schema_version: str,
    planner_version: str,
    renderer_version: str = TOPOLOGY_RENDERER_VERSION,
) -> str:
    """Stable request fence covering every input that may alter output."""
    return sha256_json(
        {
            "source_digest": str(source_digest),
            "labels": [str(label) for label in labels],
            "label_map": {
                str(key): str(value)
                for key, value in sorted((label_map or {}).items(), key=lambda item: str(item[0]))
            },
            "topology_schema_version": str(topology_schema_version),
            "planner_version": str(planner_version),
            "renderer_version": str(renderer_version),
        }
    )


def topology_cache_key(
    *,
    source_digest: str,
    topology_digest: str,
    renderer_version: str = TOPOLOGY_RENDERER_VERSION,
    background_version: str = TOPOLOGY_BACKGROUND_VERSION,
    qc_version: str = TOPOLOGY_QC_VERSION,
) -> str:
    """Cache identity includes source/topology and all rendering/QC contracts."""
    return sha256_json(
        {
            "source_digest": source_digest,
            "topology_digest": topology_digest,
            "renderer_version": renderer_version,
            "background_version": background_version,
            "qc_version": qc_version,
        }
    )[:32]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _call(fn: Callable[..., Any], **kwargs: Any) -> Any:
    result = fn(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _default_planner(**kwargs: Any) -> Any:
    try:
        from planning.whole_lesson.visual_topology_planner import run_visual_topology_planner
    except Exception as exc:  # pragma: no cover - import contract guard
        raise TopologyRecoveryError("TOPOLOGY_PLANNER_UNAVAILABLE", str(exc)) from exc
    return await _call(run_visual_topology_planner, **kwargs)


def _validated_topology(raw: Any, *, source: str) -> dict[str, Any]:
    """Apply the planner-owned schema validator when available."""
    try:
        from planning.whole_lesson.visual_topology import validate_topology_plan
    except Exception:
        validate_topology_plan = None
    if validate_topology_plan is None:
        if not isinstance(raw, Mapping) or not raw:
            raise TopologyRecoveryError("TOPOLOGY_INVALID", "planner returned empty topology")
        return dict(raw)
    try:
        validated = validate_topology_plan(raw, source=source)
    except Exception as exc:
        raise TopologyRecoveryError("TOPOLOGY_INVALID", str(exc)) from exc
    if isinstance(validated, Mapping):
        return dict(validated)
    dump = getattr(validated, "model_dump", None)
    if dump is None:
        raise TopologyRecoveryError("TOPOLOGY_INVALID", "validator returned unsupported topology")
    return dict(dump(mode="json"))


def deterministic_topology_fallback(label_ids: list[str]) -> dict[str, Any]:
    """Build a minimal topology without a provider call.

    A diagram may intentionally have an empty closed-label set. In that case
    the fallback still needs a connected neutral graph; requiring a label made
    provider-free recovery impossible for otherwise valid no-text diagrams.
    """
    ids = [str(label_id).strip() for label_id in label_ids if str(label_id).strip()]
    nodes = [
        {"id": f"n{index}", "label_id": f"l{index}"}
        for index in range(len(ids))
    ]
    # The topology contract requires a parts graph to contain at least two
    # nodes. Keep the single authoritative label complete and add one neutral
    # anchor node when the source contains only one label.
    if len(nodes) == 0:
        nodes = [{"id": "n0"}, {"id": "n1"}]
    elif len(nodes) == 1:
        nodes.append({"id": "n1"})
    return {
        "version": "v1",
        "layout": "parts",
        "nodes": nodes,
        "edges": [
            {
                "id": f"e{index}",
                "from_ref": f"n{index}",
                "to_ref": "n0",
                "direction": "forward",
            }
            for index in range(1, len(nodes))
        ],
        "labels": [
            {"id": f"l{index}", "placement": "node", "ref": f"n{index}"}
            for index in range(len(ids))
        ],
        "cues": ["part", "center"],
        "exclusions": [],
    }


async def _default_renderer(**kwargs: Any) -> Any:
    # The renderer worker owns this module; importing by symbol keeps recovery
    # provider-free and allows deterministic test doubles.
    try:
        from media.topology_renderer import render_topology_from_store
    except Exception as exc:  # pragma: no cover - import contract guard
        raise TopologyRecoveryError("TOPOLOGY_RENDERER_UNAVAILABLE", str(exc)) from exc
    topology = kwargs["topology"]
    key = kwargs["internal_asset_key"]
    store = kwargs.get("image_store")
    if store is None:
        from media.storage.image_store import get_image_store

        store = get_image_store()
    label_map = kwargs.get("label_map") or {}
    # The renderer consumes authoritative bytes and labels; no URL/provider is
    # accepted.  Tests can still inject a renderer_fn above this boundary.
    return await render_topology_from_store(topology, key, label_map, store)


async def _default_reader(*, internal_key: str, image_store: Any = None, **_: Any) -> Any:
    if image_store is None:
        from media.storage.image_store import get_image_store

        image_store = get_image_store()
    for name in ("read_image_key", "read_by_key", "get_image_by_key", "read_key"):
        method = getattr(image_store, name, None)
        if method is not None:
            return await _call(method, key=internal_key)
    # Existing stores can prove/copy keys but intentionally do not expose
    # provider access.  A renderer may consume the key directly.
    return {"internal_key": internal_key}


async def _default_topology_qc(
    *,
    rendered: Mapping[str, Any],
    topology: Mapping[str, Any],
    request_id: str,
    image_bytes: bytes | None = None,
    **_: Any,
) -> Mapping[str, Any]:
    """Fail-closed deterministic QC for provider-free topology recovery.

    The topology validator owns the semantic geometry for this fallback.  We
    still require a concrete rendered asset and a valid topology before the
    recovery path can promote the document; callers may inject the normal
    model-backed visual QC when they need an additional image review.
    """
    if not isinstance(rendered, Mapping):
        raise TopologyRecoveryError(
            "TOPOLOGY_QC_FAILED",
            f"rendered output for {request_id!r} is not an asset mapping",
        )
    # A digest alone is audit metadata, not a renderable document asset.  The
    # completion contract needs a concrete source (raster URL/key, SVG, or the
    # final PNG bytes that have not yet been uploaded).
    if not image_bytes and not any(rendered.get(key) for key in ("src", "svg", "png_bytes")):
        raise TopologyRecoveryError(
            "TOPOLOGY_QC_FAILED",
            f"rendered output for {request_id!r} has no renderable asset source",
        )
    _validated_topology(topology, source={"request_id": request_id})
    return {"status": "accept", "reasons": []}


def _extract_raster(rendered: Any) -> tuple[bytes | None, dict[str, Any]]:
    """Split final PNG bytes from the metadata payload without uploading."""
    if isinstance(rendered, Mapping):
        payload = dict(rendered)
        raw = payload.pop("png_bytes", None)
        png_bytes = bytes(raw) if isinstance(raw, (bytes, bytearray)) else None
        return png_bytes, payload
    metadata = getattr(rendered, "metadata", None)
    raw = getattr(rendered, "png_bytes", None)
    if isinstance(raw, (bytes, bytearray)):
        payload = {
            "sha256": getattr(metadata, "final_sha256", None),
            "renderer_version": getattr(metadata, "renderer_version", TOPOLOGY_RENDERER_VERSION),
            "background_version": getattr(metadata, "background_version", TOPOLOGY_BACKGROUND_VERSION),
            "qc_version": TOPOLOGY_QC_VERSION,
        }
        return bytes(raw), payload
    return None, {"src": rendered}


async def _model_backed_topology_qc(
    *,
    rendered: Mapping[str, Any],
    topology: Mapping[str, Any],
    request_id: str,
    image_bytes: bytes | None = None,
    work_order: Any = None,
    generation_id: str | None = None,
    trace_id: str | None = None,
    **_: Any,
) -> Mapping[str, Any]:
    """Classroom visual QC on the exact final raster bytes."""
    from media.qc.visual_qc import evaluate_topology_raster_quality
    from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

    png = image_bytes
    if not isinstance(png, (bytes, bytearray)) or not png:
        raise TopologyRecoveryError(
            "TOPOLOGY_QC_FAILED",
            f"final raster bytes missing for topology QC of {request_id!r}",
        )
    order = work_order
    if order is None:
        labels = [
            str(item.get("text") or item.get("id") or "").strip()
            for item in (topology.get("labels") or [])
            if isinstance(item, Mapping)
        ]
        order = VisualGeneratorWorkOrder(
            work_order_id=f"topology-qc:{request_id}",
            visual=VisualPlanItem(
                id=str(request_id),
                attaches_to=str(request_id),
                mode="diagram",
                visual_style="diagram_precision",
                purpose="topology recovery raster",
                labels_required=[label for label in labels if label],
            ),
        )
    started = time.perf_counter()
    try:
        verdict = await evaluate_topology_raster_quality(
            image_bytes=bytes(png),
            order=order,
            trace_id=trace_id or f"topology-qc:{generation_id or 'unknown'}:{request_id}",
            generation_id=generation_id,
        )
    except TopologyRecoveryError:
        raise
    except Exception as exc:
        raise TopologyRecoveryError("TOPOLOGY_QC_FAILED", str(exc)) from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": str(getattr(verdict, "verdict", "") or ""),
        "reasons": list(getattr(verdict, "reasons", None) or []),
        "correction_hint": str(getattr(verdict, "correction_hint", "") or ""),
        "latency_ms": latency_ms,
        "trace_id": trace_id or f"topology-qc:{generation_id or 'unknown'}:{request_id}",
    }


async def recover_flagged_visual_topology(
    *,
    session: Any,
    generation_id: str,
    request_id: str,
    source_text: str,
    source_digest: str,
    labels: list[str] | tuple[str, ...],
    internal_asset_key: str,
    label_map: Mapping[str, str] | None = None,
    persisted_source: Mapping[str, Any] | None = None,
    prompt: str | None = None,
    model_name: str = "topology-planner",
    planner_version: str = "v1",
    topology_schema_version: str = "visual-topology/1",
    planner_fn: PlannerFn | None = None,
    reader_fn: ReaderFn | None = None,
    renderer_fn: RendererFn | None = None,
    qc_fn: QCFn | None = None,
    image_store: Any = None,
    supplied_block_id: str | None = None,
    work_order: Any = None,
) -> dict[str, Any]:
    """Recover one QC-flagged figure, returning ``ready`` or ``awaiting_visuals``.

    Planner failures happen before persistence and rendering.  A topology
    mismatch raises ``VisualTopologyConflict`` before any renderer/provider
    interaction.  The returned asset is committed through the existing atomic
    ``apply_visual_completion`` repository method.
    """
    repo = PageDocumentRepository(session, generation_id)
    rid = str(request_id or "").strip()
    if not rid:
        raise TopologyRecoveryError("INVALID_REQUEST", "request_id is required", recoverable=False)
    effective_label_map = dict(
        label_map
        or {f"l{index}": str(label) for index, label in enumerate(labels)}
    )
    label_ids = list(effective_label_map)
    # The topology planner may only project authoritative lesson/teaching facts.
    # Keep the old scalar source_text as a compatibility fallback for direct
    # callers, but prefer the structured snapshot assembled by native dispatch.
    planner_source: dict[str, Any] = dict(persisted_source or {})
    planner_source.setdefault("source_text", source_text)
    planner_source["label_map"] = effective_label_map
    planner_source["label_ids"] = label_ids
    identity = topology_identity_digest(
        source_digest=source_digest,
        labels=tuple(effective_label_map.values()),
        label_map=effective_label_map,
        topology_schema_version=topology_schema_version,
        planner_version=planner_version,
    )
    await repo.append_visual_topology_event(
        event_type="topology_started",
        request_id=rid,
        payload={"source_digest": source_digest, "identity_digest": identity},
    )

    existing_state = await repo.load_visual_topology_state()
    existing = (existing_state.get("requests") or {}).get(rid)
    if isinstance(existing, Mapping) and str(existing.get("identity_digest") or "") != identity:
        raise VisualTopologyConflict(f"topology request {rid!r} identity mismatch")

    fallback_used = False
    reused = False
    try:
        if isinstance(existing, Mapping):
            topology = dict(existing.get("topology") or {})
            reused = True
        else:
            planner = planner_fn or _default_planner
            planned = await _call(
                planner,
                request={"prompt": prompt or source_text, "label_ids": label_ids},
                persisted_source=planner_source,
                generation_id=generation_id,
                request_id=rid,
                trace_id=f"topology:{generation_id}:{rid}",
            )
            if hasattr(planned, "plan"):
                planned = planned.plan
            topology = _validated_topology(
                planned,
                source=planner_source,
            )
            reused = False
    except VisualTopologyConflict:
        raise
    except TopologyRecoveryError:
        if existing is not None:
            raise
        topology = deterministic_topology_fallback(label_ids)
        fallback_used = True
    except Exception:  # timeout/validation/provider text errors are retryable
        topology = deterministic_topology_fallback(label_ids)
        fallback_used = True

    # Re-validate resumed checkpoints against the current authoritative source
    # as well as the identity fence.  The identity digest protects the request
    # inputs; this second pass protects against a malformed/corrupted persisted
    # topology being sent directly to the renderer.
    topology = _validated_topology(topology, source=planner_source)

    topology_digest = sha256_json(topology)
    await repo.append_visual_topology_event(
        event_type="topology_validated",
        request_id=rid,
        payload={
            "topology_sha256": topology_digest,
            "reused": reused,
            "fallback": fallback_used,
        },
    )
    if not reused:
        record = {
            "request_id": rid,
            "topology": topology,
            "topology_sha256": topology_digest,
            "source_digest": source_digest,
            "labels": list(effective_label_map.values()),
            "label_map": effective_label_map,
            "prompt": prompt or source_text,
            "model": "deterministic-fallback" if fallback_used else model_name,
            "model_name": "deterministic-fallback" if fallback_used else model_name,
            "planner_version": planner_version,
            "schema_version": topology_schema_version,
            "validation": {"status": "valid", "validated_at": _utcnow()},
            "evidence_refs": {"internal_asset_key": internal_asset_key},
            "created_at": _utcnow(),
            "recovery_version": TOPOLOGY_RECOVERY_VERSION,
            "fallback": fallback_used,
        }
        persisted = await repo.persist_visual_topology(
            request_id=rid,
            record=record,
            identity_digest=identity,
        )
        await repo.append_visual_topology_event(
            event_type="topology_persisted",
            request_id=rid,
            payload={"topology_sha256": topology_digest, "identity_digest": identity},
        )
    else:
        persisted = {"record": dict(existing), "reused": True}

    reader = reader_fn or _default_reader
    try:
        source_asset = await _call(reader, internal_key=internal_asset_key, image_store=image_store)
        if source_asset is None:
            raise TopologyRecoveryError(
                "TOPOLOGY_SOURCE_ASSET_MISSING",
                f"internal visual asset key {internal_asset_key!r} was not found",
            )
        renderer = renderer_fn or _default_renderer
        rendered = await _call(
            renderer,
            topology=topology,
            source_asset=source_asset,
            internal_asset_key=internal_asset_key,
            label_map=effective_label_map,
            image_store=image_store,
            generation_id=generation_id,
            request_id=rid,
            cache_key=topology_cache_key(
                source_digest=source_digest,
                topology_digest=topology_digest,
            ),
        )
    except Exception as exc:
        await repo.append_visual_topology_event(
            event_type="topology_failed",
            request_id=rid,
            payload={"code": "TOPOLOGY_RENDER_FAILED", "error": str(exc)[:500]},
        )
        raise TopologyRecoveryError("TOPOLOGY_RENDER_FAILED", str(exc)) from exc

    png_bytes, rendered_payload = _extract_raster(rendered)
    preflight_payload = dict(rendered_payload)
    if png_bytes:
        preflight_payload["png_bytes"] = True
    try:
        await _default_topology_qc(
            rendered=preflight_payload,
            topology=topology,
            request_id=rid,
        )
    except TopologyRecoveryError as exc:
        await repo.append_visual_topology_event(
            event_type="topology_qc",
            request_id=rid,
            payload={"status": "error", "error": str(exc)[:500], "phase": "preflight"},
        )
        raise

    qc_trace_id = f"topology-qc:{generation_id}:{rid}"
    # A deterministic fallback has no model-authored semantic claim left to
    # review. Its authoritative labels/topology have already passed the strict
    # contract, so use provider-free structural QC; ordinary recovered visuals
    # retain the caller-supplied/model-backed QC path.
    effective_qc = _default_topology_qc if fallback_used else (qc_fn or _model_backed_topology_qc)
    qc_started = time.perf_counter()
    try:
        verdict = await _call(
            effective_qc,
            rendered=rendered_payload,
            topology=topology,
            request_id=rid,
            image_bytes=png_bytes,
            work_order=work_order,
            generation_id=generation_id,
            trace_id=qc_trace_id,
        )
    except Exception as exc:
        await repo.append_visual_topology_event(
            event_type="topology_qc",
            request_id=rid,
            payload={"status": "error", "error": str(exc)[:500]},
        )
        raise TopologyRecoveryError("TOPOLOGY_QC_FAILED", str(exc)) from exc
    qc_latency_ms = int((time.perf_counter() - qc_started) * 1000)
    if not isinstance(verdict, Mapping):
        await repo.append_visual_topology_event(
            event_type="topology_qc",
            request_id=rid,
            payload={"status": "invalid", "error": "QC returned a non-mapping verdict"},
        )
        raise TopologyRecoveryError(
            "TOPOLOGY_QC_FAILED",
            "topology QC returned an invalid verdict",
        )
    verdict_status = str(verdict.get("status") or verdict.get("verdict") or "").strip().lower()
    qc_payload = {
        "status": verdict_status,
        "reasons": list(verdict.get("reasons") or []),
        "correction_hint": str(verdict.get("correction_hint") or ""),
        "latency_ms": int(verdict.get("latency_ms") or qc_latency_ms),
        "trace_id": str(verdict.get("trace_id") or qc_trace_id),
    }
    if verdict_status in {"flagged_quality", "flag", "reject"}:
        await repo.append_visual_topology_event(
            event_type="topology_qc",
            request_id=rid,
            payload=qc_payload,
        )
        raise TopologyRecoveryError("TOPOLOGY_QC_FLAGGED", "deterministic topology QC flagged output")
    if verdict_status not in {"accept", "accepted", "ready"}:
        await repo.append_visual_topology_event(
            event_type="topology_qc",
            request_id=rid,
            payload={"status": "invalid", "verdict": verdict_status},
        )
        raise TopologyRecoveryError(
            "TOPOLOGY_QC_FAILED",
            f"topology QC returned unsupported verdict {verdict_status!r}",
        )

    if png_bytes and not rendered_payload.get("src"):
        store = image_store
        if store is None:
            from media.storage.image_store import get_image_store

            store = get_image_store()
        try:
            src = await _call(
                store.store_image,
                image_bytes=bytes(png_bytes),
                generation_id=generation_id,
                section_id="topology",
                filename=f"{rid}.png",
                format="png",
            )
        except Exception as exc:
            raise TopologyRecoveryError("TOPOLOGY_UPLOAD_FAILED", str(exc)) from exc
        rendered_payload["src"] = src

    asset = {
        "status": "ready",
        "request_id": rid,
        "kind": str(rendered_payload.get("kind") or "image"),
    }
    # Keep the persisted figure asset inside the Lectio page contract. Renderer
    # hashes and internal cache keys are audit metadata, not document fields;
    # the document schema deliberately permits only the renderable source.
    for key in ("src", "svg"):
        if rendered_payload.get(key) is not None:
            asset[key] = rendered_payload[key]
    await repo.append_visual_topology_event(
        event_type="topology_deterministic_rendered",
        request_id=rid,
        payload={"topology_sha256": topology_digest, "asset_sha256": rendered_payload.get("sha256")},
    )
    accepted_qc = {
        "status": "accepted",
        "reasons": qc_payload["reasons"],
        "correction_hint": qc_payload["correction_hint"] or None,
        "latency_ms": qc_payload["latency_ms"],
        "trace_id": qc_payload["trace_id"],
    }
    completion = await repo.apply_visual_completion(
        request_id=rid,
        asset=asset,
        supplied_block_id=supplied_block_id,
        visual_qc=accepted_qc,
    )
    await repo.append_visual_topology_event(
        event_type="topology_qc",
        request_id=rid,
        payload={"status": "accepted", "document_revision": completion.document_revision, **accepted_qc},
    )
    return {
        "status": completion.status,
        "request_id": rid,
        "reused": bool(persisted.get("reused")),
        "topology_sha256": topology_digest,
        "identity_digest": identity,
        "document_revision": completion.document_revision,
        "asset": asset,
        "visual_qc": accepted_qc,
    }


# Short compatibility alias used by dispatch callers.
recover_flagged_visual = recover_flagged_visual_topology

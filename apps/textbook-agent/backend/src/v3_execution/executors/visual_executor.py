from __future__ import annotations

import hashlib
import json
import logging
import os
import traceback
import uuid
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

import core.events as core_events
from media.qc.visual_qc import evaluate_visual_quality, visual_qc_enabled
from media.diagram_compositor import (
    COMPOSITOR_VERSION,
    FONT_VERSION,
    LAYOUT_VERSION,
    compose_diagram_precision,
    preflight_diagram_labels,
)
from media.providers.registry import get_image_client, load_image_provider_spec

from v3_execution.models import ExecutorOutcome, GeneratedVisualBlock, VisualGeneratorWorkOrder
from v3_execution.prompts.visual_executor import build_visual_prompt
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.runtime.retry_runner import run_with_retries
from v3_execution.runtime.validation import validate_visual_block


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]
logger = logging.getLogger(__name__)
VISUAL_QC_CONTRACT_VERSION = "visual-qc/2"


def _image_cache_enabled() -> bool:
    return os.getenv("V3_IMAGE_CACHE_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _cache_key_for_visual(
    *,
    prompt: str,
    order: VisualGeneratorWorkOrder,
    model_name: str,
) -> str:
    payload = {
        "prompt": prompt,
        "mode": order.visual.mode,
        "model_name": model_name,
        "must_show": order.visual.must_show,
        "must_not_show": order.visual.must_not_show,
        "labels_required": order.visual.labels_required,
        "purpose": order.visual.purpose,
        "qc_correction_hint": order.qc_correction_hint,
        "source_of_truth": [
            {"key": item.key, "text": item.text}
            for item in order.source_of_truth
        ],
        # Cache entries contain the final (possibly composed) raster.  Bump the
        # contract whenever compositor/QC semantics change so stale provider
        # bytes can never masquerade as accepted output.
        "compositor_version": COMPOSITOR_VERSION,
        "font_version": FONT_VERSION,
        "layout_version": LAYOUT_VERSION,
        "visual_qc_contract_version": VISUAL_QC_CONTRACT_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]


class VisualStageError(RuntimeError):
    def __init__(
        self,
        *,
        stage: str,
        original_exception: Exception,
        traceback_text: str,
    ) -> None:
        self.stage = stage
        self.original_exception = original_exception
        self.original_exception_type = type(original_exception).__name__
        self.original_message = str(original_exception)
        self.traceback_text = traceback_text
        super().__init__(self.to_error_message())

    @classmethod
    def from_exception(cls, *, stage: str, exc: Exception) -> "VisualStageError":
        if isinstance(exc, cls):
            return exc
        traceback_text = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        return cls(
            stage=stage,
            original_exception=exc,
            traceback_text=traceback_text,
        )

    def to_error_message(self) -> str:
        return (
            f"{self.stage} failed ({self.original_exception_type}): "
            f"{self.original_message}"
        )


def _visual_log_extra(
    *,
    order: VisualGeneratorWorkOrder,
    generation_id: str,
    visual_id: str,
    frame_index: int | None,
    component_id: str | None,
    parent_visual_id: str | None,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generation_id": generation_id,
        "visual_id": visual_id,
        "attaches_to": order.visual.attaches_to,
        "component_id": component_id,
        "parent_visual_id": parent_visual_id,
        "mode": order.visual.mode,
        "frame_index": frame_index,
        "node_name": "visual_executor",
    }
    payload.update(extra)
    return payload


async def _render_frame(
    *,
    order: VisualGeneratorWorkOrder,
    generation_id: str,
    trace_id: str | None,
    prompt: str,
    frame_suffix: str,
    frame_index: int | None,
    component_id: str | None = None,
    parent_visual_id: str | None = None,
    model_name: str,
    bypass_cache_read: bool = False,
    provider_name: str = "image",
    provider_attempt_counter: list[int] | None = None,
    provider_failure_retryable: bool = True,
) -> GeneratedVisualBlock:
    from media.storage.image_store import get_image_store

    visual_id = f"{order.visual.id}{frame_suffix}"
    cache_enabled = _image_cache_enabled()
    cache_key = _cache_key_for_visual(prompt=prompt, order=order, model_name=model_name)
    cache_object_key = f"images/cache/{cache_key}.png"
    destination_key = f"{generation_id}/{order.visual.attaches_to or 'visuals'}/{visual_id}.png"

    is_diagram_precision = getattr(order.visual, "visual_style", None) == "diagram_precision"
    # Fail before touching the provider (and before accepting a cache entry) if
    # the deterministic label band cannot fit at print-safe font size.
    if is_diagram_precision:
        try:
            canonical_labels = preflight_diagram_labels(
                (1024, 1024), order.visual.labels_required
            )
        except Exception as exc:  # noqa: BLE001
            raise VisualStageError.from_exception(
                stage="diagram_compositor_preflight",
                exc=exc,
            ) from exc
        else:
            # The model validator normally canonicalizes this already; retain
            # the preflight result only to prove deterministic capacity before
            # provider execution.
            _ = canonical_labels

    try:
        store = get_image_store()
    except Exception as exc:  # noqa: BLE001
        raise VisualStageError.from_exception(
            stage="gcs_upload",
            exc=exc,
        ) from exc

    if cache_enabled and not bypass_cache_read:
        try:
            if await store.image_exists(key=cache_object_key):
                url = await store.copy_image(
                    source_key=cache_object_key,
                    destination_key=destination_key,
                )
                if url:
                    if not await store.image_exists(key=destination_key):
                        logger.warning(
                            "v3 visual cache copy missing destination; generating image",
                            extra=_visual_log_extra(
                                order=order,
                                generation_id=generation_id,
                                visual_id=visual_id,
                                frame_index=frame_index,
                                component_id=component_id,
                                parent_visual_id=parent_visual_id,
                                cache_key=cache_key,
                                destination_key=destination_key,
                            ),
                        )
                        raise RuntimeError("cache copy destination missing")
                    logger.info(
                        "v3 visual cache hit",
                        extra=_visual_log_extra(
                            order=order,
                            generation_id=generation_id,
                            visual_id=visual_id,
                            frame_index=frame_index,
                            component_id=component_id,
                            parent_visual_id=parent_visual_id,
                            cache_key=cache_key,
                        ),
                    )
                    block = GeneratedVisualBlock(
                        visual_id=visual_id,
                        attaches_to=order.visual.attaches_to,
                        frame_index=frame_index,
                        mode=order.visual.mode,
                        image_url=url,
                        caption=order.visual.purpose,
                        alt_text=order.visual.purpose,
                        source_work_order_id=order.work_order_id,
                        component_id=component_id,
                        parent_visual_id=parent_visual_id,
                        status="ready",
                    )
                    errs = validate_visual_block(block, order)
                    if errs:
                        raise RuntimeError("; ".join(errs))
                    return block
            logger.info(
                "v3 visual cache miss",
                extra=_visual_log_extra(
                    order=order,
                    generation_id=generation_id,
                    visual_id=visual_id,
                    frame_index=frame_index,
                    component_id=component_id,
                    parent_visual_id=parent_visual_id,
                    cache_key=cache_key,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "v3 visual cache read failed; generating image",
                extra=_visual_log_extra(
                    order=order,
                    generation_id=generation_id,
                    visual_id=visual_id,
                    frame_index=frame_index,
                    component_id=component_id,
                    parent_visual_id=parent_visual_id,
                    cache_key=cache_key,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )

    try:
        client = get_image_client()
    except Exception as exc:  # noqa: BLE001
        raise VisualStageError.from_exception(
            stage="image_generation_api_call",
            exc=exc,
        ) from exc

    logger.info(
        "v3 visual request constructed",
        extra=_visual_log_extra(
            order=order,
            generation_id=generation_id,
            visual_id=visual_id,
            frame_index=frame_index,
            component_id=component_id,
            parent_visual_id=parent_visual_id,
            prompt_length=len(prompt),
            target_section=order.visual.attaches_to,
        ),
    )
    attempt_counter = provider_attempt_counter if provider_attempt_counter is not None else [0]
    attempt_counter[0] += 1
    provider_attempt = attempt_counter[0]
    event_trace_id = trace_id or generation_id
    core_events.event_bus.publish(
        event_trace_id,
        core_events.LLMCallStartedEvent(
            trace_id=event_trace_id,
            generation_id=generation_id,
            caller="visual_provider",
            node="visual_executor",
            slot="visual",
            family=provider_name,
            model_name=model_name,
            endpoint_host=None,
            attempt=provider_attempt,
            section_id=order.visual.attaches_to,
        ),
    )
    provider_started = time.perf_counter()
    try:
        image = await client.generate_image(prompt=prompt)
    except Exception as exc:  # noqa: BLE001
        core_events.event_bus.publish(
            event_trace_id,
            core_events.LLMCallFailedEvent(
                trace_id=event_trace_id,
                generation_id=generation_id,
                caller="visual_provider",
                node="visual_executor",
                slot="visual",
                family=provider_name,
                model_name=model_name,
                endpoint_host=None,
                attempt=provider_attempt,
                section_id=order.visual.attaches_to,
                latency_ms=(time.perf_counter() - provider_started) * 1000.0,
                retryable=provider_failure_retryable,
                error=str(exc),
                error_class=type(exc).__name__,
            ),
        )
        raise VisualStageError.from_exception(
            stage="image_generation_api_call",
            exc=exc,
        ) from exc

    core_events.event_bus.publish(
        event_trace_id,
        core_events.LLMCallSucceededEvent(
            trace_id=event_trace_id,
            generation_id=generation_id,
            caller="visual_provider",
            node="visual_executor",
            slot="visual",
            family=provider_name,
            model_name=model_name,
            endpoint_host=None,
            attempt=provider_attempt,
            section_id=order.visual.attaches_to,
            latency_ms=(time.perf_counter() - provider_started) * 1000.0,
        ),
    )

    logger.info(
        "v3 visual image bytes received",
        extra=_visual_log_extra(
            order=order,
            generation_id=generation_id,
            visual_id=visual_id,
            frame_index=frame_index,
            component_id=component_id,
            parent_visual_id=parent_visual_id,
            byte_count=len(image.bytes),
            content_type=image.mime_type,
            base_sha256=hashlib.sha256(image.bytes).hexdigest(),
            provider_name=provider_name,
            model_name=model_name,
        ),
    )

    base_bytes = image.bytes
    composed_bytes = base_bytes
    composed_mime_type = image.mime_type
    composition_metadata: dict[str, Any] | None = None
    if is_diagram_precision:
        try:
            composed = compose_diagram_precision(
                base_bytes,
                order.visual.labels_required,
            )
        except Exception as exc:  # noqa: BLE001
            raise VisualStageError.from_exception(
                stage="diagram_compositor",
                exc=exc,
            ) from exc
        composed_bytes = composed.png_bytes
        composed_mime_type = "image/png"
        composition_metadata = composed.metadata.as_dict()
        logger.info(
            "v3 visual diagram composed",
            extra=_visual_log_extra(
                order=order,
                generation_id=generation_id,
                visual_id=visual_id,
                frame_index=frame_index,
                component_id=component_id,
                parent_visual_id=parent_visual_id,
                provider_name=provider_name,
                model_name=model_name,
                **composition_metadata,
            ),
        )

    qc_status: Literal["ready", "flagged_quality"] = "ready"
    qc_reasons: list[str] = []
    qc_correction_hint: str | None = None
    if visual_qc_enabled() and order.visual.mode != "simulation":
        try:
            verdict = await evaluate_visual_quality(
                image_bytes=composed_bytes,
                mime_type=composed_mime_type,
                order=order,
                trace_id=trace_id,
                generation_id=generation_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "v3 visual qc failed",
                extra=_visual_log_extra(
                    order=order,
                    generation_id=generation_id,
                    visual_id=visual_id,
                    frame_index=frame_index,
                    component_id=component_id,
                    parent_visual_id=parent_visual_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
            if is_diagram_precision:
                # Precision visuals are closed-label outputs.  Without QC we
                # cannot establish that the provider artwork contains no text
                # or that the deterministic band is correct, so fail closed:
                # retain the composed raster for generation-specific review,
                # but mark it retryable and keep it out of the shared cache.
                qc_status = "flagged_quality"
                qc_reasons = [f"visual QC unavailable: {type(exc).__name__}: {exc}"]
                qc_correction_hint = "rerun visual quality review"
        else:
            if verdict.verdict == "reject":
                return GeneratedVisualBlock(
                    visual_id=visual_id,
                    attaches_to=order.visual.attaches_to,
                    frame_index=frame_index,
                    mode=order.visual.mode,
                    image_url=None,
                    caption=order.visual.purpose,
                    alt_text=order.visual.purpose,
                    source_work_order_id=order.work_order_id,
                    component_id=component_id,
                    parent_visual_id=parent_visual_id,
                    status="omitted_quality",
                    error_message="; ".join(verdict.reasons),
                )
            if verdict.verdict == "flag":
                qc_status = "flagged_quality"
                qc_reasons = verdict.reasons
                qc_correction_hint = verdict.correction_hint or None

    try:
        url = await store.store_image(
            composed_bytes,
            generation_id=generation_id,
            section_id=order.visual.attaches_to or "visuals",
            filename=f"{visual_id}.png",
            format="png" if is_diagram_precision else image.format,
        )
        # Only accepted output is eligible for shared cache.  Flagged output
        # remains available on the generation for review/retry but must never
        # poison future requests.
        if cache_enabled and qc_status == "ready":
            try:
                await store.store_image_key(
                    key=cache_object_key,
                    image_bytes=composed_bytes,
                    content_type=composed_mime_type,
                )
                logger.info(
                    "v3 visual cache write complete",
                    extra=_visual_log_extra(
                        order=order,
                        generation_id=generation_id,
                        visual_id=visual_id,
                        frame_index=frame_index,
                        component_id=component_id,
                        parent_visual_id=parent_visual_id,
                        cache_key=cache_key,
                        **(composition_metadata or {}),
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "v3 visual cache write failed",
                    extra=_visual_log_extra(
                        order=order,
                        generation_id=generation_id,
                        visual_id=visual_id,
                        frame_index=frame_index,
                        component_id=component_id,
                        parent_visual_id=parent_visual_id,
                        cache_key=cache_key,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    ),
                )
    except Exception as exc:  # noqa: BLE001
        raise VisualStageError.from_exception(
            stage="gcs_upload",
            exc=exc,
        ) from exc

    block = GeneratedVisualBlock(
        visual_id=visual_id,
        attaches_to=order.visual.attaches_to,
        frame_index=frame_index,
        mode=order.visual.mode,
        image_url=url,
        caption=order.visual.purpose,
        alt_text=order.visual.purpose,
        source_work_order_id=order.work_order_id,
        component_id=component_id,
        parent_visual_id=parent_visual_id,
        status=qc_status,
        qc_reasons=qc_reasons,
        qc_correction_hint=qc_correction_hint,
    )
    errs = validate_visual_block(block, order)
    if errs:
        raise VisualStageError.from_exception(
            stage="visual_block_validation",
            exc=RuntimeError("; ".join(errs)),
        )
    return block


async def execute_visual(
    order: VisualGeneratorWorkOrder,
    emit_event: EmitFn,
    *,
    trace_id: str | None,
    generation_id: str | None,
    bypass_cache_read: bool = False,
) -> list[GeneratedVisualBlock]:
    _ = trace_id
    gid = generation_id or str(uuid.uuid4())
    spec = load_image_provider_spec()
    last_failure: VisualStageError | None = None
    provider_attempt_counter = [0]
    executor_attempt_number = 0

    async def _attempt(_: bool) -> ExecutorOutcome:
        nonlocal executor_attempt_number, last_failure
        executor_attempt_number += 1
        provider_failure_retryable = executor_attempt_number < (
            1 + V3_MAX_RETRIES["visual_executor_frame"]
        )
        await emit_event(
            "visual_generation_started",
            {
                "visual_id": order.visual.id,
                "generation_id": gid,
                "image_provider": spec.provider,
                "image_model": spec.model_name,
            },
        )
        blocks: list[GeneratedVisualBlock] = []
        try:
            if order.visual.mode == "simulation":
                block = GeneratedVisualBlock(
                    visual_id=order.visual.id,
                    attaches_to=order.visual.attaches_to,
                    frame_index=None,
                    mode="simulation",
                    html_content="<section class='simulation-placeholder'></section>",
                    fallback_image_url=None,
                    caption=order.visual.purpose,
                    alt_text=order.visual.purpose,
                    source_work_order_id=order.work_order_id,
                    component_id=order.visual.component_id,
                    parent_visual_id=None,
                    status="ready",
                )
                errs = validate_visual_block(block, order)
                if errs:
                    return ExecutorOutcome(ok=False, errors=errs)
                blocks.append(block)
            elif order.visual.mode == "diagram_series" and order.visual.frames:
                parent_id = order.visual.id
                previous = None
                for idx, frame in enumerate(order.visual.frames):
                    frame_order = order.model_copy(deep=True)
                    frame_order.visual.must_show = frame.must_show or frame_order.visual.must_show
                    frame_order.visual.purpose = frame.description or frame_order.visual.purpose
                    prompt = build_visual_prompt(frame_order, previous_frame_description=previous)
                    block = await _render_frame(
                        order=frame_order,
                        generation_id=gid,
                        trace_id=trace_id,
                        prompt=prompt,
                        frame_suffix=f"_frame_{idx}",
                        frame_index=idx,
                        component_id=order.visual.component_id,
                        parent_visual_id=parent_id,
                        model_name=spec.model_name,
                        bypass_cache_read=bypass_cache_read,
                        provider_name=spec.provider,
                        provider_attempt_counter=provider_attempt_counter,
                        provider_failure_retryable=provider_failure_retryable,
                    )
                    blocks.append(block)
                    previous = frame.description
            else:
                prompt = build_visual_prompt(order)
                block = await _render_frame(
                    order=order,
                    generation_id=gid,
                    trace_id=trace_id,
                    prompt=prompt,
                    frame_suffix="",
                    frame_index=None,
                    component_id=order.visual.component_id,
                    parent_visual_id=None,
                    model_name=spec.model_name,
                    bypass_cache_read=bypass_cache_read,
                    provider_name=spec.provider,
                    provider_attempt_counter=provider_attempt_counter,
                    provider_failure_retryable=provider_failure_retryable,
                )
                blocks.append(block)

            for block in blocks:
                await emit_event(
                    "visual_ready",
                    {
                        "generation_id": gid,
                        "visual_id": block.visual_id,
                        "attaches_to": block.attaches_to,
                        "component_id": block.component_id,
                        "parent_visual_id": block.parent_visual_id,
                        "mode": block.mode,
                        "frame_index": block.frame_index,
                        "frame_count": len(blocks),
                        "image_url": block.image_url,
                        "status": block.status,
                        "image_provider": spec.provider,
                        "image_model": spec.model_name,
                    },
                )
            return ExecutorOutcome(ok=True, blocks=blocks)
        except Exception as exc:  # noqa: BLE001
            last_failure = VisualStageError.from_exception(
                stage="visual_executor",
                exc=exc,
            )
            original = last_failure.original_exception
            response = getattr(original, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code is None:
                status_code = getattr(original, "status_code", None)
            non_retryable = int(status_code or 0) == 400 or last_failure.stage.startswith(
                "diagram_compositor"
            )
            logger.error(
                "v3 visual execution failed",
                extra=_visual_log_extra(
                    order=order,
                    generation_id=gid,
                    visual_id=order.visual.id,
                    frame_index=None,
                    component_id=order.visual.component_id,
                    parent_visual_id=None,
                    failure_stage=last_failure.stage,
                    original_exception_type=last_failure.original_exception_type,
                    original_exception_message=last_failure.original_message,
                    traceback=last_failure.traceback_text,
                ),
            )
            return ExecutorOutcome(
                ok=False,
                errors=[last_failure.to_error_message()],
                retryable=not non_retryable,
            )

    outcome = await run_with_retries(
        f"visual:{order.visual.id}",
        _attempt,
        max_retries=V3_MAX_RETRIES["visual_executor_frame"],
    )
    if not outcome.ok:
        if last_failure is not None:
            logger.error(
                "v3 visual failed block error_message set",
                extra=_visual_log_extra(
                    order=order,
                    generation_id=gid,
                    visual_id=order.visual.id,
                    frame_index=None,
                    component_id=order.visual.component_id,
                    parent_visual_id=None,
                    failure_stage=last_failure.stage,
                    original_exception_type=last_failure.original_exception_type,
                    original_exception_message=last_failure.original_message,
                    traceback=last_failure.traceback_text,
                ),
            )
        await emit_event(
            "visual_failed",
            {
                "generation_id": gid,
                "visual_id": order.visual.id,
                "attaches_to": order.visual.attaches_to,
                "component_id": order.visual.component_id,
                "parent_visual_id": None,
                "mode": order.visual.mode,
                "frame_count": len(order.visual.frames) if order.visual.frames else 1,
                "error_summary": "; ".join(outcome.errors),
                "image_provider": spec.provider,
                "image_model": spec.model_name,
            },
        )
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                frame_index=None,
                mode=order.visual.mode,
                image_url=None,
                caption=order.visual.purpose,
                alt_text=order.visual.purpose,
                source_work_order_id=order.work_order_id,
                component_id=order.visual.component_id,
                parent_visual_id=None,
                status="failed",
                error_message="; ".join(outcome.errors),
            )
        ]
    return [
        block
        for block in outcome.blocks
        if isinstance(block, GeneratedVisualBlock)
    ]


__all__ = ["execute_visual"]

from __future__ import annotations

import hashlib
import json
import logging
import os
import traceback
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from media.qc.visual_qc import evaluate_visual_quality, visual_qc_enabled
from media.providers.registry import get_image_client, load_image_provider_spec

from v3_execution.models import ExecutorOutcome, GeneratedVisualBlock, VisualGeneratorWorkOrder
from v3_execution.prompts.visual_executor import build_visual_prompt
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.runtime.retry_runner import run_with_retries
from v3_execution.runtime.validation import validate_visual_block


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]
logger = logging.getLogger(__name__)


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
) -> GeneratedVisualBlock:
    from media.storage.image_store import get_image_store

    visual_id = f"{order.visual.id}{frame_suffix}"
    cache_enabled = _image_cache_enabled()
    cache_key = _cache_key_for_visual(prompt=prompt, order=order, model_name=model_name)
    cache_object_key = f"images/cache/{cache_key}.png"
    destination_key = f"{generation_id}/{order.visual.attaches_to or 'visuals'}/{visual_id}.png"

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
    try:
        image = await client.generate_image(prompt=prompt)
    except Exception as exc:  # noqa: BLE001
        raise VisualStageError.from_exception(
            stage="image_generation_api_call",
            exc=exc,
        ) from exc

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
        ),
    )

    if visual_qc_enabled() and order.visual.mode != "simulation":
        try:
            verdict = await evaluate_visual_quality(
                image_bytes=image.bytes,
                mime_type=image.mime_type,
                order=order,
                trace_id=trace_id,
                generation_id=generation_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "v3 visual qc failed open",
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
        else:
            if verdict.verdict == "reject":
                correction_hint = verdict.correction_hint or "; ".join(verdict.reasons)
                corrected_prompt = f"{prompt}\n\nCorrection: {correction_hint}"
                logger.info(
                    "v3 visual qc rejected initial image; retrying once",
                    extra=_visual_log_extra(
                        order=order,
                        generation_id=generation_id,
                        visual_id=visual_id,
                        frame_index=frame_index,
                        component_id=component_id,
                        parent_visual_id=parent_visual_id,
                        qc_reasons=verdict.reasons,
                    ),
                )
                try:
                    image = await client.generate_image(prompt=corrected_prompt)
                    retry_verdict = await evaluate_visual_quality(
                        image_bytes=image.bytes,
                        mime_type=image.mime_type,
                        order=order,
                        trace_id=trace_id,
                        generation_id=generation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "v3 visual qc retry failed open",
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
                else:
                    if retry_verdict.verdict == "reject":
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
                            error_message="; ".join(retry_verdict.reasons),
                        )

    try:
        url = await store.store_image(
            image.bytes,
            generation_id=generation_id,
            section_id=order.visual.attaches_to or "visuals",
            filename=f"{visual_id}.png",
            format=image.format,
        )
        if cache_enabled:
            try:
                await store.store_image_key(
                    key=cache_object_key,
                    image_bytes=image.bytes,
                    content_type=image.mime_type,
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
        status="ready",
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

    async def _attempt(_: bool) -> ExecutorOutcome:
        nonlocal last_failure
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

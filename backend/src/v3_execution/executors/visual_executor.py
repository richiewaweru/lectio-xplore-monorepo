from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from media.providers.registry import get_image_client, load_image_provider_spec

from v3_execution.models import ExecutorOutcome, GeneratedVisualBlock, VisualGeneratorWorkOrder
from v3_execution.prompts.visual_executor import build_visual_prompt
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.runtime.retry_runner import run_with_retries
from v3_execution.runtime.validation import validate_visual_block


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _render_frame(
    *,
    order: VisualGeneratorWorkOrder,
    generation_id: str,
    prompt: str,
    frame_suffix: str,
    frame_index: int | None,
    component_id: str | None = None,
    parent_visual_id: str | None = None,
) -> GeneratedVisualBlock:
    from media.storage.image_store import get_image_store

    client = get_image_client()
    store = get_image_store()
    image = await client.generate_image(prompt=prompt)

    visual_id = f"{order.visual.id}{frame_suffix}"
    url = await store.store_image(
        image.bytes,
        generation_id=generation_id,
        section_id=order.visual.attaches_to or "visuals",
        filename=f"{visual_id}.png",
        format=image.format,
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


async def execute_visual(
    order: VisualGeneratorWorkOrder,
    emit_event: EmitFn,
    *,
    trace_id: str | None,
    generation_id: str | None,
) -> list[GeneratedVisualBlock]:
    _ = trace_id
    gid = generation_id or str(uuid.uuid4())
    spec = load_image_provider_spec()

    async def _attempt(_: bool) -> ExecutorOutcome:
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
                        prompt=prompt,
                        frame_suffix=f"_frame_{idx}",
                        frame_index=idx,
                        component_id=order.visual.component_id,
                        parent_visual_id=parent_id,
                    )
                    blocks.append(block)
                    previous = frame.description
            else:
                prompt = build_visual_prompt(order)
                block = await _render_frame(
                    order=order,
                    generation_id=gid,
                    prompt=prompt,
                    frame_suffix="",
                    frame_index=None,
                    component_id=order.visual.component_id,
                    parent_visual_id=None,
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
                        "image_provider": spec.provider,
                        "image_model": spec.model_name,
                    },
                )
            return ExecutorOutcome(ok=True, blocks=blocks)
        except Exception as exc:  # noqa: BLE001
            return ExecutorOutcome(ok=False, errors=[str(exc)])

    outcome = await run_with_retries(
        f"visual:{order.visual.id}",
        _attempt,
        max_retries=V3_MAX_RETRIES["visual_executor_frame"],
    )
    if not outcome.ok:
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

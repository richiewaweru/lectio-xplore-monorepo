from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from contracts.lectio import get_section_field_for_component

from v3_execution.llm_helpers import run_json_agent
from v3_execution.models import ExecutorOutcome, GeneratedComponentBlock
from v3_execution.prompts.section_writer import (
    build_section_writer_prompt,
    build_section_writer_retry_prompt,
)
from v3_execution.config.retries import V3_MAX_RETRIES
from v3_execution.runtime import events
from v3_execution.runtime.lectio_validation import validate_lectio_field_payload
from v3_execution.runtime.retry_runner import run_with_retries
from v3_execution.runtime.validation import validate_component_batch
from v3_execution.models import SectionWriterWorkOrder


EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _extract_fields(payload: dict[str, Any]) -> dict[str, Any]:
    if "fields" in payload and isinstance(payload["fields"], dict):
        return payload["fields"]
    return payload


async def execute_section(
    order: SectionWriterWorkOrder,
    emit_event: EmitFn,
    *,
    trace_id: str | None,
    generation_id: str | None,
    model_overrides: dict | None = None,
    max_retries: int | None = None,
) -> list[GeneratedComponentBlock]:
    await emit_event(
        "section_writing_started",
        {"section_id": order.section.id, "generation_id": generation_id},
    )
    _prior_errors: list[str] = []

    async def _attempt(already_retried: bool) -> ExecutorOutcome:
        warnings: list[str] = []
        errors: list[str] = []
        try:
            if already_retried and _prior_errors:
                prompt = build_section_writer_retry_prompt(order, _prior_errors)
            else:
                prompt = build_section_writer_prompt(order)
            response = await run_json_agent(
                node_name="v3_section_writer",
                trace_id=trace_id,
                generation_id=generation_id,
                system_prompt="Return compact JSON matching the user's contract.",
                user_prompt=prompt,
                model_overrides=model_overrides,
            )
            fields = _extract_fields(response)
            blocks: list[GeneratedComponentBlock] = []
            for position, component in enumerate(order.section.components):
                card = order.component_cards.get(component.component_id, {})
                field_name = card.get("section_field") or get_section_field_for_component(
                    component.component_id
                )
                if field_name is None:
                    errors.append(
                        f"No section_field mapping for component '{component.component_id}'. "
                        "Check that lectio-content-contract.json is up to date."
                    )
                    continue
                raw_data = fields.get(field_name)
                if raw_data is None:
                    errors.append(
                        f"Writer produced no output for field '{field_name}' ({component.component_id})"
                    )
                    continue
                data_dict = raw_data if isinstance(raw_data, dict) else {"value": raw_data}
                validated_data, field_errors = validate_lectio_field_payload(field_name, data_dict)
                if field_errors:
                    errors.extend(field_errors)
                    validated_data = data_dict
                blocks.append(
                    GeneratedComponentBlock(
                        block_id=str(uuid.uuid4()),
                        section_id=order.section.id,
                        component_id=component.component_id,
                        section_field=field_name,
                        position=position,
                        data=validated_data,
                        source_work_order_id=order.work_order_id,
                    )
                )

            errs = validate_component_batch(
                blocks,
                order,
                component_cards=order.component_cards,
            )
            if errs:
                errors.extend(errs)

            ok = len(errors) == 0 and len(blocks) == len(order.section.components)
            if ok:
                for block in blocks:
                    await emit_event(
                        "component_ready",
                        {
                            "generation_id": generation_id,
                            "component_id": block.component_id,
                            "section_id": block.section_id,
                            "position": block.position,
                            "section_field": block.section_field,
                            "data": block.data,
                        },
                    )
            if already_retried and not ok:
                warnings.append("section writer retry unsuccessful")
            if not ok:
                _prior_errors.clear()
                _prior_errors.extend(errors)
            return ExecutorOutcome(ok=ok, blocks=blocks, warnings=warnings, errors=errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            _prior_errors.clear()
            _prior_errors.extend(errors)
            return ExecutorOutcome(ok=False, warnings=warnings, errors=errors)

    outcome = await run_with_retries(
        f"section:{order.section.id}",
        _attempt,
        max_retries=V3_MAX_RETRIES["section_writer"] if max_retries is None else max_retries,
    )
    if not outcome.ok:
        await emit_event(
            events.SECTION_WRITER_FAILED,
            {
                "generation_id": generation_id,
                "section_id": order.section.id,
                "errors": list(outcome.errors),
                "warnings": list(outcome.warnings),
            },
        )
        raise RuntimeError(
            "; ".join(outcome.errors) or "section writer failed"
        )
    return [b for b in outcome.blocks if isinstance(b, GeneratedComponentBlock)]


__all__ = ["execute_section"]

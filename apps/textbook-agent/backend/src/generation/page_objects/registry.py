"""Stub writers, registry dispatch, and LLM write-with-repair."""

from __future__ import annotations

import json
import uuid
from typing import Any, Protocol

from generation.page_objects.assessment import assemble_choices, assemble_questions
from generation.page_objects.models import (
    FORM_OUTPUTS,
    WriterContext,
    WriterError,
    WriterOutcome,
    WriterResult,
)
from generation.page_objects.prompts import build_repair_prompt, build_writer_prompt
from generation.page_objects.validation import (
    ContentValidationError,
    UnsupportedObject,
    validate_content,
)
from planning.whole_lesson.figure_ids import stable_figure_request_id


def _assert_fixed_object(ctx: WriterContext, expected: str) -> None:
    if ctx.planned.object != expected:
        raise WriterError(
            f"writer for {expected!r} cannot run on planned object {ctx.planned.object!r}"
        )


def write_prose(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "prose")
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={
            "paragraphs": [
                ctx.planned.brief.strip()
                or "Prose content derived from the assigned block brief."
            ]
        },
    )


def write_list(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "list")
    items = [
        {"text": part.strip()}
        for part in ctx.planned.brief.replace(";", ".").split(".")
        if part.strip()
    ][:6] or [{"text": ctx.planned.brief}]
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={"style": "unordered", "items": items},
    )


def write_table(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "table")
    columns = [
        {"id": "case", "label": "Case"},
        {"id": "observation", "label": "Observation"},
    ]
    rows = [
        {"cells": {"case": "Lit leaf", "observation": "Receives light; can make food"}},
        {"cells": {"case": "Covered leaf", "observation": "No light; cannot make food"}},
    ]
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={
            "columns": columns,
            "rows": rows,
            "caption": ctx.planned.brief[:120],
            "presentation": "comparison",
        },
    )


def write_worked_example(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "worked-example")
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={
            "problem": ctx.planned.brief,
            "steps": [
                {"text": "Identify the controlled conditions."},
                {"text": "Change only the target variable."},
                {"text": "State the outcome that follows."},
            ],
            "answer": "The outcome tracks the changed condition.",
        },
    )


def write_figure(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "figure")
    request_id = (
        stable_figure_request_id(
            generation_id=ctx.generation_id or "local",
            block_id=ctx.planned.id,
        )
        if ctx.generation_id
        else f"fig-req-{uuid.uuid4().hex[:12]}"
    )
    alt = (ctx.planned.brief or "").strip()[:160] or "Figure"
    return WriterOutcome(
        block_id=ctx.planned.id,
        status="visual_pending",
        request_id=request_id,
        content={
            "alt_text": alt,
            "caption": alt,
            "asset": {"status": "pending", "request_id": request_id, "kind": "image"},
        },
    )


def write_aside(ctx: WriterContext) -> WriterOutcome:
    _assert_fixed_object(ctx, "aside")
    brief = (ctx.planned.brief or "").strip()
    first_sentence = brief.split(".")[0].strip() if brief else ""
    label = first_sentence[:80] if first_sentence else "Note"
    body = brief or "Note"
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={"label": label, "body": body},
    )


_STUB_WRITERS = {
    "prose": write_prose,
    "list": write_list,
    "table": write_table,
    "figure": write_figure,
    "aside": write_aside,
    "worked-example": write_worked_example,
    "questions": assemble_questions,
    "choices": assemble_choices,
}


def _finalize_result(ctx: WriterContext, result: WriterOutcome) -> WriterOutcome:
    if result.block_id != ctx.planned.id:
        raise WriterError("writer attempted to change block id")
    result.content = validate_content(ctx.planned.object, result.content)
    return result


def dispatch_writer(ctx: WriterContext) -> WriterOutcome:
    writer = _STUB_WRITERS.get(ctx.planned.object)
    if writer is None:
        raise WriterError(f"no writer for object {ctx.planned.object!r}")
    result = writer(ctx)
    return _finalize_result(ctx, result)


def _coerce_raw_content(raw: object) -> object:
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return dict(raw.model_dump(mode="json"))
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            # Strip optional markdown fences.
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return json.loads(text)
    raise WriterError(f"unexpected writer output type: {type(raw)!r}")


def _validation_errors_from_exc(exc: Exception) -> list[dict[str, Any]]:
    if isinstance(exc, ContentValidationError):
        return list(exc.errors)
    if isinstance(exc, json.JSONDecodeError):
        return [{"path": "", "message": f"invalid JSON: {exc.msg}"}]
    return [{"path": "", "message": str(exc)}]


class WriterProvider(Protocol):
    async def write(
        self,
        *,
        object_id: str,
        section_id: str,
        block_id: str,
        attempt: int,
        prompt: str,
        output_model: type[Any],
    ) -> object: ...


def _writer_contract(object_id: str) -> Any:
    try:
        from planning.catalogue_projections import project_writer_contract

        return project_writer_contract(object_id)
    except Exception:  # noqa: BLE001 — contract is advisory for prompts
        return {"object_id": object_id}


async def _llm_write(ctx: WriterContext, *, prompt: str | None = None) -> object:
    from pydantic_ai import Agent

    from contracts.lectio_page import get_intent_catalogue
    from core.config import settings
    from core.llm.runner import RetryPolicy, run_llm
    from planning.model_tiers import tier_for_object_writer
    from planning.prompts import page_writer_common_prompt, prompt_text
    from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
    from v3_execution.config.models import V3_BLOCK_WRITER_FAST, V3_BLOCK_WRITER_STANDARD

    tier = tier_for_object_writer(ctx.planned.object) or "FAST"
    node = V3_BLOCK_WRITER_STANDARD if tier == "STANDARD" else V3_BLOCK_WRITER_FAST
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)

    if prompt is None:
        common = page_writer_common_prompt()
        specific_name = {
            "prose": "prose-writer-v1.txt",
            "list": "list-writer-v1.txt",
            "table": "table-writer-v1.txt",
            "worked-example": "worked-example-writer-v1.txt",
            "figure": "figure-brief-writer-v1.txt",
            "aside": "list-writer-v1.txt",
        }.get(ctx.planned.object)
        specific = prompt_text(specific_name) if specific_name else ""
        intent_rec = (get_intent_catalogue().get("intents") or {}).get(ctx.planned.intent) or {}
        contract = _writer_contract(ctx.planned.object)
        prev_brief = ctx.neighbour_summaries[0] if len(ctx.neighbour_summaries) > 0 else ""
        next_brief = ctx.neighbour_summaries[1] if len(ctx.neighbour_summaries) > 1 else ""
        payload = {
            "lesson_context": ctx.lesson_context or {},
            "terminology": list(ctx.terminology),
            "block": {
                "id": ctx.planned.id,
                "position": ctx.planned.position,
                "intent": ctx.planned.intent,
                "intent_generation_guidance": intent_rec.get("generation_guidance"),
                "brief": ctx.planned.brief,
                "object": ctx.planned.object,
                "placement": ctx.planned.placement,
            },
            "neighbours": {"before": prev_brief, "after": next_brief},
            "writer_contract": contract.to_dict()
            if hasattr(contract, "to_dict")
            else contract,
        }
        prompt = f"{common}\n\n{specific}\n\n## INPUT JSON\n{json.dumps(payload, indent=2, sort_keys=True)}"

    agent = Agent(model=model, system_prompt=prompt)
    result = await run_llm(
        trace_id=str(uuid.uuid4()),
        caller=f"v3_block_writer_{ctx.planned.object}",
        generation_id=ctx.generation_id,
        agent=agent,
        user_prompt="Return JSON only for this block's content schema.",
        model=model,
        slot=slot,
        spec=spec,
        node=node,
        model_settings=get_v3_model_settings(node),
        retry_policy=RetryPolicy(
            max_attempts=1 + int(settings.xplore_page_writer_retries),
            call_timeout_seconds=float(
                settings.page_standard_writer_timeout_seconds
                if tier == "STANDARD"
                else settings.page_fast_writer_timeout_seconds
            ),
        ),
    )
    return result.output


def _figure_result_from_content(
    ctx: WriterContext,
    content: dict[str, Any],
    *,
    base: WriterOutcome | None = None,
) -> WriterOutcome:
    base = base or write_figure(ctx)
    merged = dict(base.content)
    merged.update({k: v for k, v in content.items() if k != "asset"})
    asset = dict(merged.get("asset") or {})
    incoming_asset = content.get("asset") if isinstance(content.get("asset"), dict) else {}
    if incoming_asset:
        asset.update({k: v for k, v in incoming_asset.items() if k != "request_id"})
    asset["request_id"] = base.request_id
    asset.setdefault("status", "pending")
    asset.setdefault("kind", "image")
    merged["asset"] = asset
    if not merged.get("alt_text"):
        merged["alt_text"] = base.content.get("alt_text") or "Figure"
    validated = validate_content("figure", merged)
    return WriterOutcome(
        block_id=base.block_id,
        content=validated,
        status="visual_pending",
        request_id=base.request_id,
    )


async def _write_validated_llm(
    ctx: WriterContext,
    *,
    provider: WriterProvider | None = None,
) -> WriterOutcome:
    object_id = ctx.planned.object
    if object_id not in FORM_OUTPUTS:
        raise UnsupportedObject(object_id)
    contract = _writer_contract(object_id)
    prompt = build_writer_prompt(ctx, contract)
    output_model = FORM_OUTPUTS[object_id]

    async def _call(attempt: int, call_prompt: str) -> object:
        if provider is not None:
            return await provider.write(
                object_id=object_id,
                section_id=ctx.section_id or "",
                block_id=ctx.planned.id,
                attempt=attempt,
                prompt=call_prompt,
                output_model=output_model,
            )
        return await _llm_write(ctx, prompt=call_prompt)

    raw = await _call(1, prompt)
    try:
        coerced = _coerce_raw_content(raw)
        content = validate_content(object_id, coerced)
    except (ContentValidationError, json.JSONDecodeError, WriterError) as first_exc:
        errors = _validation_errors_from_exc(first_exc)
        previous = raw
        try:
            previous = _coerce_raw_content(raw) if not isinstance(raw, str) else raw
        except Exception:  # noqa: BLE001
            previous = raw if isinstance(raw, (dict, list, str)) else str(raw)
        repair_prompt = build_repair_prompt(
            ctx,
            previous_output=previous,
            validation_errors=errors,
            contract=contract,
        )
        try:
            repaired_raw = await _call(2, repair_prompt)
            coerced = _coerce_raw_content(repaired_raw)
            content = validate_content(object_id, coerced)
        except (ContentValidationError, json.JSONDecodeError, WriterError) as final_exc:
            if isinstance(final_exc, ContentValidationError):
                raise final_exc
            raise ContentValidationError(
                object_id, _validation_errors_from_exc(final_exc)
            ) from final_exc

    if object_id == "figure":
        return _figure_result_from_content(ctx, content)

    return WriterOutcome(
        block_id=ctx.planned.id,
        content=content,
        status="ready",
    )


async def dispatch_writer_async(
    ctx: WriterContext,
    *,
    provider: WriterProvider | None = None,
) -> WriterOutcome:
    # Scripted/mock providers may exercise questions/choices validation+repair.
    if provider is not None and ctx.use_llm:
        return await _write_validated_llm(ctx, provider=provider)

    if ctx.planned.object in {"questions", "choices"} or not ctx.use_llm:
        return dispatch_writer(ctx)

    if ctx.planned.object == "figure":
        try:
            return await _write_validated_llm(ctx)
        except Exception:
            # Deterministic pending fallback when figure LLM path fails.
            return dispatch_writer(ctx)

    return await _write_validated_llm(ctx)

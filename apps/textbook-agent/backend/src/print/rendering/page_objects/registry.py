"""Stub writers, registry dispatch, and LLM write-with-repair."""

from __future__ import annotations

import json
import uuid
from typing import Any, Protocol

from print.rendering.page_objects.assessment import assemble_choices, assemble_questions
from print.rendering.page_objects.models import (
    FORM_OUTPUTS,
    WRITER_PROVIDER_OUTPUTS,
    WriterContext,
    WriterError,
    WriterOutcome,
)
from print.rendering.page_objects.validation import (
    ContentValidationError,
    UnsupportedObject,
    validate_content,
)
from infra.authoring import (
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringProviderCall,
    AuthoringTransportError,
)
from print.generation.work_orders import (
    PrintWorkOrder,
    build_print_work_order_from_planned_block,
)
from print.generation.whole_lesson.figure_ids import stable_figure_request_id


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


def _rich_text_to_plain_text(value: object) -> object:
    """Unwrap editor-document text when a scalar form field receives it."""
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text.startswith('{"type":"doc"'):
            return value
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return value
    if not isinstance(parsed, dict) or parsed.get("type") != "doc":
        return value

    parts: list[str] = []

    def visit(node: object) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            parts.append(node["text"])
            return
        for child in node.get("content") or []:
            visit(child)
        if node.get("type") in {"paragraph", "heading", "listItem"}:
            parts.append("\n")

    visit(parsed)
    return " ".join("".join(parts).split())


def _normalize_scalar_rich_text(object_id: str, content: object) -> object:
    if not isinstance(content, dict):
        return content
    normalized = dict(content)
    scalar_fields = {"aside": ("body",), "list": ("lead_in",)}.get(object_id, ())
    for field in scalar_fields:
        if field in normalized:
            normalized[field] = _rich_text_to_plain_text(normalized[field])
    return normalized


def normalize_persisted_document_json(document: object) -> object:
    """Normalize rich-text scalar fields in a persisted V2 page document."""
    if not isinstance(document, dict):
        return document
    normalized = dict(document)
    page_document = normalized.get("lectio_document")
    if not isinstance(page_document, dict):
        return normalized
    page_document = dict(page_document)
    sections = []
    for section in page_document.get("sections") or []:
        if not isinstance(section, dict):
            sections.append(section)
            continue
        section = dict(section)
        blocks = []
        for block in section.get("blocks") or []:
            if not isinstance(block, dict):
                blocks.append(block)
                continue
            block = dict(block)
            block["content"] = _normalize_scalar_rich_text(
                str(block.get("object") or ""), block.get("content")
            )
            blocks.append(block)
        section["blocks"] = blocks
        sections.append(section)
    page_document["sections"] = sections
    normalized["lectio_document"] = page_document
    return normalized


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


class _LegacyWriterAuthoringProvider:
    def __init__(self, inner: WriterProvider, *, ctx: WriterContext) -> None:
        self.inner = inner
        self.ctx = ctx

    async def invoke(self, call: AuthoringProviderCall) -> object:
        output_model = WRITER_PROVIDER_OUTPUTS[call.capability_id]
        try:
            result = await self.inner.write(
                object_id=call.capability_id,
                section_id=self.ctx.section_id or "",
                block_id=self.ctx.planned.id,
                attempt=call.attempt,
                prompt=call.prompt,
                output_model=output_model,
            )
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise AuthoringTransportError(str(exc)) from exc
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json", exclude_none=True)
        return _normalize_scalar_rich_text(call.capability_id, result)


def _authoring_provider(
    provider: WriterProvider | AuthoringProvider | None,
    *,
    ctx: WriterContext,
) -> AuthoringProvider | None:
    if provider is None:
        return None
    if hasattr(provider, "invoke"):
        return provider  # type: ignore[return-value]
    return _LegacyWriterAuthoringProvider(provider, ctx=ctx)  # type: ignore[arg-type]


def _work_order_for_context(ctx: WriterContext) -> PrintWorkOrder:
    if ctx.print_work_order is not None:
        return ctx.print_work_order
    return build_print_work_order_from_planned_block(
        ctx.planned,
        section_id=ctx.section_id,
    )


def _content_validation_from_authoring_error(
    object_id: str,
    exc: AuthoringEngineError,
) -> ContentValidationError | None:
    if exc.code not in {
        "INVALID_PAYLOAD",
        "INCOMPATIBLE_APPROVED_ITEM",
        "REPAIR_EXHAUSTED",
    }:
        return None
    if not exc.errors:
        return None
    return ContentValidationError(
        object_id,
        [error.to_dict() for error in exc.errors],
    )


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
    # Lazy import avoids circular import via page_objects.__init__ → registry.
    from print.generation.authoring_adapter import run_print_authoring

    object_id = ctx.planned.object
    if object_id not in FORM_OUTPUTS:
        raise UnsupportedObject(object_id)
    try:
        authoring_result = await run_print_authoring(
            _work_order_for_context(ctx),
            provider=_authoring_provider(provider, ctx=ctx),
            lesson_context=ctx.lesson_context,
            allowed_facts=list(ctx.lesson_context.get("allowed_facts") or [])
            if isinstance(ctx.lesson_context, dict)
            else None,
            terminology=ctx.terminology,
            approved_items=ctx.item_records if object_id in {"questions", "choices"} else None,
            mode="generate",
        )
    except AuthoringEngineError as exc:
        content_error = _content_validation_from_authoring_error(object_id, exc)
        if content_error is not None:
            raise content_error from exc
        raise
    content = validate_content(
        object_id,
        _normalize_scalar_rich_text(object_id, authoring_result.payload),
    )

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
    provider: WriterProvider | AuthoringProvider | None = None,
) -> WriterOutcome:
    if ctx.planned.object in {"questions", "choices"} or not ctx.use_llm:
        return dispatch_writer(ctx)

    return await _write_validated_llm(ctx, provider=provider)

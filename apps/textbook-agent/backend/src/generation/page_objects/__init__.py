"""Native page-object writers and questions assembler.

Writers fill a fixed planned object. They cannot change intent/object.
Questions are assembled from item IDs only (question wall).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from v3_blueprint.planning.models import PlannedBlock

PageObjectId = Literal[
    "prose", "list", "table", "figure", "worked-example", "questions"
]


class WriterError(ValueError):
    pass


@dataclass(frozen=True)
class WriterContext:
    """Immutable writer context. No alternative objects. No lesson prose for questions."""

    planned: PlannedBlock
    terminology: tuple[str, ...] = ()
    neighbour_summaries: tuple[str, ...] = ()
    item_records: tuple[dict[str, Any], ...] = ()


@dataclass
class WriterResult:
    block_id: str
    object: str
    intent: str
    content: dict[str, Any]
    status: str = "ready"
    request_id: str | None = None


def _assert_fixed_object(ctx: WriterContext, expected: str) -> None:
    if ctx.planned.object != expected:
        raise WriterError(
            f"writer for {expected!r} cannot run on planned object {ctx.planned.object!r}"
        )


def write_prose(ctx: WriterContext) -> WriterResult:
    _assert_fixed_object(ctx, "prose")
    return WriterResult(
        block_id=ctx.planned.id,
        object="prose",
        intent=ctx.planned.intent,
        content={
            "paragraphs": [
                ctx.planned.brief.strip()
                or "Prose content derived from the assigned block brief."
            ]
        },
    )


def write_list(ctx: WriterContext) -> WriterResult:
    _assert_fixed_object(ctx, "list")
    items = [
        {"text": part.strip()}
        for part in ctx.planned.brief.replace(";", ".").split(".")
        if part.strip()
    ][:6] or [{"text": ctx.planned.brief}]
    return WriterResult(
        block_id=ctx.planned.id,
        object="list",
        intent=ctx.planned.intent,
        content={"style": "unordered", "items": items},
    )


def write_table(ctx: WriterContext) -> WriterResult:
    _assert_fixed_object(ctx, "table")
    columns = [
        {"id": "case", "label": "Case"},
        {"id": "observation", "label": "Observation"},
    ]
    rows = [
        {"cells": {"case": "Lit leaf", "observation": "Receives light; can make food"}},
        {"cells": {"case": "Covered leaf", "observation": "No light; cannot make food"}},
    ]
    return WriterResult(
        block_id=ctx.planned.id,
        object="table",
        intent=ctx.planned.intent,
        content={
            "columns": columns,
            "rows": rows,
            "caption": ctx.planned.brief[:120],
            "presentation": "comparison",
        },
    )


def write_worked_example(ctx: WriterContext) -> WriterResult:
    _assert_fixed_object(ctx, "worked-example")
    return WriterResult(
        block_id=ctx.planned.id,
        object="worked-example",
        intent=ctx.planned.intent,
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


def write_figure(ctx: WriterContext) -> WriterResult:
    _assert_fixed_object(ctx, "figure")
    request_id = f"fig-req-{uuid4().hex[:12]}"
    return WriterResult(
        block_id=ctx.planned.id,
        object="figure",
        intent=ctx.planned.intent,
        status="pending",
        request_id=request_id,
        content={
            "alt_text": ctx.planned.brief[:160],
            "caption": ctx.planned.brief[:160],
            "asset": {"status": "pending", "request_id": request_id, "kind": "image"},
        },
    )


def assemble_questions(ctx: WriterContext) -> WriterResult:
    """Deterministic assembler. Must not receive or use section prose/briefs as item text."""
    _assert_fixed_object(ctx, "questions")
    if not ctx.planned.source_question_ids:
        raise WriterError("questions block requires source_question_ids")
    # Question wall: only item_records keyed by ID — never planned.brief/prose.
    by_id = {str(item.get("id")): item for item in ctx.item_records}
    items: list[dict[str, Any]] = []
    for qid in ctx.planned.source_question_ids:
        record = by_id.get(qid)
        if record is None:
            raise WriterError(f"missing item record for question id {qid!r}")
        items.append(
            {
                "id": qid,
                "prompt": record.get("prompt") or record.get("stem") or f"Question {qid}",
            }
        )
    return WriterResult(
        block_id=ctx.planned.id,
        object="questions",
        intent=ctx.planned.intent,
        content={"items": items},
    )


_WRITERS = {
    "prose": write_prose,
    "list": write_list,
    "table": write_table,
    "figure": write_figure,
    "worked-example": write_worked_example,
    "questions": assemble_questions,
}


def dispatch_writer(ctx: WriterContext) -> WriterResult:
    writer = _WRITERS.get(ctx.planned.object)
    if writer is None:
        raise WriterError(f"no writer for object {ctx.planned.object!r}")
    result = writer(ctx)
    if result.object != ctx.planned.object or result.intent != ctx.planned.intent:
        raise WriterError("writer attempted to change planned object or intent")
    if result.block_id != ctx.planned.id:
        raise WriterError("writer attempted to change block id")
    return result

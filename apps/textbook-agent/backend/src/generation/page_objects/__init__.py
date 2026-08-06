"""Native page-object writers and questions assembler.

Writers fill a fixed planned object. They cannot change intent/object.
Questions are assembled from item IDs only (question wall).
LLM writers are optional and lazy-imported so unit tests stay offline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from planning.whole_lesson.figure_ids import stable_figure_request_id
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
    lesson_context: dict[str, Any] | None = None
    generation_id: str | None = None
    use_llm: bool = False


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
    request_id = (
        stable_figure_request_id(
            generation_id=ctx.generation_id or "local",
            block_id=ctx.planned.id,
        )
        if ctx.generation_id
        else f"fig-req-{uuid.uuid4().hex[:12]}"
    )
    return WriterResult(
        block_id=ctx.planned.id,
        object="figure",
        intent=ctx.planned.intent,
        status="visual_pending",
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
    # Optional answer metadata when present (teacher edition).
    enriched: list[dict[str, Any]] = []
    for item in items:
        record = by_id[item["id"]]
        row = dict(item)
        if record.get("options"):
            row["options"] = record.get("options")
        if record.get("correct_key"):
            row["correct_key"] = record.get("correct_key")
            row["answer_key_ref"] = record.get("correct_key")
        enriched.append(row)
    return WriterResult(
        block_id=ctx.planned.id,
        object="questions",
        intent=ctx.planned.intent,
        content={"items": enriched},
    )


_STUB_WRITERS = {
    "prose": write_prose,
    "list": write_list,
    "table": write_table,
    "figure": write_figure,
    "worked-example": write_worked_example,
    "questions": assemble_questions,
}


def dispatch_writer(ctx: WriterContext) -> WriterResult:
    writer = _STUB_WRITERS.get(ctx.planned.object)
    if writer is None:
        raise WriterError(f"no writer for object {ctx.planned.object!r}")
    result = writer(ctx)
    if result.object != ctx.planned.object or result.intent != ctx.planned.intent:
        raise WriterError("writer attempted to change planned object or intent")
    if result.block_id != ctx.planned.id:
        raise WriterError("writer attempted to change block id")
    return result


async def _llm_write(ctx: WriterContext) -> dict[str, Any]:
    from pydantic_ai import Agent

    from contracts.lectio_page import get_intent_catalogue
    from core.config import settings
    from core.llm.runner import RetryPolicy, run_llm
    from planning.catalogue_projections import project_writer_contract
    from planning.model_tiers import tier_for_object_writer
    from planning.prompts import page_writer_common_prompt, prompt_text
    from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
    from v3_execution.config.models import V3_BLOCK_WRITER_FAST, V3_BLOCK_WRITER_STANDARD

    tier = tier_for_object_writer(ctx.planned.object)
    node = V3_BLOCK_WRITER_STANDARD if tier == "STANDARD" else V3_BLOCK_WRITER_FAST
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    common = page_writer_common_prompt()
    specific_name = {
        "prose": "prose-writer-v1.txt",
        "list": "list-writer-v1.txt",
        "table": "table-writer-v1.txt",
        "worked-example": "worked-example-writer-v1.txt",
        "figure": "figure-brief-writer-v1.txt",
    }[ctx.planned.object]
    specific = prompt_text(specific_name)
    intent_rec = (get_intent_catalogue().get("intents") or {}).get(ctx.planned.intent) or {}
    contract = project_writer_contract(ctx.planned.object)
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
        "writer_contract": contract.to_dict(),
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
    raw = result.output
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return dict(raw.model_dump())
    if isinstance(raw, str):
        return json.loads(raw)
    raise WriterError(f"unexpected writer output type: {type(raw)!r}")


async def dispatch_writer_async(ctx: WriterContext) -> WriterResult:
    if ctx.planned.object == "questions" or not ctx.use_llm:
        return dispatch_writer(ctx)
    if ctx.planned.object == "figure":
        try:
            content = await _llm_write(ctx)
            base = write_figure(ctx)
            merged = dict(base.content)
            merged.update({k: v for k, v in content.items() if k != "asset"})
            asset = dict(merged.get("asset") or {})
            asset["request_id"] = base.request_id
            asset.setdefault("status", "pending")
            merged["asset"] = asset
            return WriterResult(
                block_id=base.block_id,
                object=base.object,
                intent=base.intent,
                content=merged,
                status="visual_pending",
                request_id=base.request_id,
            )
        except Exception:
            return write_figure(ctx)
    content = await _llm_write(ctx)
    return WriterResult(
        block_id=ctx.planned.id,
        object=ctx.planned.object,
        intent=ctx.planned.intent,
        content=content,
        status="ready",
    )

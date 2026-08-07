"""Registry covers all 8 forms and rejects object/intent/id mutation."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    GENERATED_FORM_IDS,
    WriterContext,
    WriterError,
    dispatch_writer,
    write_aside,
    write_prose,
)
from planning.model_tiers import tier_for_object_writer
from v3_blueprint.planning.models import PlannedBlock


def _block(**kwargs) -> PlannedBlock:
    return PlannedBlock.model_validate(kwargs)


def test_dispatch_all_eight_forms() -> None:
    items = (
        {
            "id": "i1",
            "prompt": "Open prompt?",
            "answer": "Because light.",
        },
        {
            "id": "mcq-1",
            "stem": "Which is true?",
            "options": [
                {"key": "A", "text": "Soil is food"},
                {"key": "B", "text": "Soil supplies minerals"},
            ],
            "correct_key": "B",
        },
    )
    specs = [
        ("prose", "explain", {}),
        ("list", "name-parts", {}),
        ("table", "compare", {}),
        ("figure", "show-structure", {}),
        ("aside", "warn", {}),
        ("worked-example", "demonstrate", {}),
        ("questions", "check-understanding", {"source_question_ids": ["i1"]}),
        ("choices", "diagnose-misconception", {}),
    ]
    assert {s[0] for s in specs} == set(GENERATED_FORM_IDS)
    for index, (obj, intent, extra) in enumerate(specs):
        planned = _block(
            id="mcq-1" if obj == "choices" else f"b-{obj}",
            position=index,
            intent=intent,
            object=obj,
            evidence="e",
            brief="Important brief about light and food.",
            **extra,
        )
        ctx = WriterContext(
            planned=planned,
            item_records=items if obj in {"questions", "choices"} else (),
        )
        result = dispatch_writer(ctx)
        assert result.block_id == planned.id
        assert ctx.planned.object == obj
        assert ctx.planned.intent == intent
        assert isinstance(result.content, dict)


def test_write_aside_uses_brief() -> None:
    ctx = WriterContext(
        planned=_block(
            id="a1",
            position=0,
            intent="warn",
            object="aside",
            evidence="misconception",
            brief="Do not treat soil as food. Plants make food.",
        )
    )
    result = write_aside(ctx)
    assert result.content["label"]
    assert "soil" in result.content["body"].lower() or "food" in result.content["body"].lower()


def test_writer_cannot_run_on_wrong_object() -> None:
    ctx = WriterContext(
        planned=_block(
            id="b1",
            position=0,
            intent="compare",
            object="table",
            evidence="compare",
            brief="Compare lit and covered leaves.",
        )
    )
    with pytest.raises(WriterError, match="cannot run"):
        write_prose(ctx)


def test_questions_and_choices_have_no_writer_tier() -> None:
    assert tier_for_object_writer("questions") is None
    assert tier_for_object_writer("choices") is None
    assert tier_for_object_writer("aside") == "FAST"
    assert tier_for_object_writer("prose") == "STANDARD"


def test_unknown_object_has_no_stub_writer() -> None:
    # PlannedBlock forbids heading in first-slice rules; use a raw namespace.
    planned = PlannedBlock.model_construct(
        id="h1",
        position=0,
        intent="orient",
        object="heading",
        evidence="e",
        brief="Title",
        source_question_ids=[],
    )
    with pytest.raises(WriterError, match="no writer"):
        dispatch_writer(WriterContext(planned=planned))

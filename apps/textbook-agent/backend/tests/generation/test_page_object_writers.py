from generation.page_objects import (
    WriterContext,
    WriterError,
    WriterResult,
    assemble_questions,
    dispatch_writer,
)
from v3_blueprint.planning.models import PlannedBlock


def _block(**kwargs) -> PlannedBlock:
    return PlannedBlock.model_validate(kwargs)


def test_prose_writer_fills_fixed_plan() -> None:
    ctx = WriterContext(
        planned=_block(
            id="b1",
            position=0,
            intent="explain-cause",
            object="prose",
            evidence="cause needed",
            brief="Light is the differing condition.",
        )
    )
    result = dispatch_writer(ctx)
    assert result.object == "prose"
    assert result.intent == "explain-cause"
    assert result.content["paragraphs"]


def test_writer_cannot_change_object() -> None:
    ctx = WriterContext(
        planned=_block(
            id="b1",
            position=0,
            intent="compare",
            object="table",
            evidence="compare cases",
            brief="Compare lit and covered leaves.",
        )
    )
    # Calling prose writer directly must fail
    from generation.page_objects import write_prose

    try:
        write_prose(ctx)
        assert False, "expected WriterError"
    except WriterError as exc:
        assert "cannot run" in str(exc)


def test_questions_assembler_uses_item_ids_only() -> None:
    ctx = WriterContext(
        planned=_block(
            id="q1",
            position=0,
            intent="check-understanding",
            object="questions",
            evidence="check from card",
            brief="THIS BRIEF MUST NOT BECOME QUESTION TEXT",
            source_question_ids=["item-1"],
        ),
        item_records=({"id": "item-1", "prompt": "Why does the covered leaf fail?", "answer": "No light"},),
    )
    result = assemble_questions(ctx)
    assert result.content["items"][0]["prompt"] == "Why does the covered leaf fail?"
    assert "THIS BRIEF" not in result.content["items"][0]["prompt"]


def test_figure_pending_has_stable_request_id() -> None:
    ctx = WriterContext(
        planned=_block(
            id="f1",
            position=0,
            intent="show-structure",
            object="figure",
            evidence="spatial contrast",
            brief="Show lit vs covered leaf side by side.",
        )
    )
    result = dispatch_writer(ctx)
    assert result.status == "pending"
    assert result.request_id
    assert result.content["asset"]["status"] == "pending"
    assert result.content["asset"]["request_id"] == result.request_id


def test_dispatch_all_first_slice_objects() -> None:
    specs = [
        ("prose", "explain", {}),
        ("list", "name-parts", {}),
        ("table", "compare", {}),
        ("worked-example", "demonstrate", {}),
        ("figure", "show-structure", {}),
        ("questions", "check-understanding", {"source_question_ids": ["i1"]}),
    ]
    items = ({"id": "i1", "prompt": "Prompt", "answer": "A"},)
    for index, (obj, intent, extra) in enumerate(specs):
        planned = _block(
            id=f"b-{obj}",
            position=index,
            intent=intent,
            object=obj,
            evidence="e",
            brief="b",
            **extra,
        )
        ctx = WriterContext(planned=planned, item_records=items if obj == "questions" else ())
        result = dispatch_writer(ctx)
        assert result.object == obj

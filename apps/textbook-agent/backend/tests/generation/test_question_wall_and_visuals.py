"""RUN_07: question wall + stable figure completion."""

from __future__ import annotations

from generation.page_objects import WriterContext, assemble_questions, dispatch_writer
from generation.page_objects.visual_completion import apply_figure_asset_update
from v3_blueprint.planning.models import PlannedBlock


def test_item_generation_inputs_exclude_lesson_prose() -> None:
    """Assembler must not use brief/prose as question prompt text."""
    poisoned = "POISON_LESSON_PROSE_MUST_NOT_APPEAR"
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "q1",
                "position": 0,
                "intent": "check-understanding",
                "object": "questions",
                "evidence": "card only",
                "brief": poisoned,
                "source_question_ids": ["item-9"],
            }
        ),
        item_records=({"id": "item-9", "prompt": "Card-derived prompt only"},),
        neighbour_summaries=(poisoned,),
    )
    result = assemble_questions(ctx)
    blob = str(result.content)
    assert poisoned not in blob
    assert result.content["items"][0]["prompt"] == "Card-derived prompt only"


def test_figure_pending_to_ready_preserves_identity_and_order() -> None:
    figure = dispatch_writer(
        WriterContext(
            planned=PlannedBlock.model_validate(
                {
                    "id": "fig-1",
                    "position": 1,
                    "intent": "show-structure",
                    "object": "figure",
                    "evidence": "spatial",
                    "brief": "Lit vs covered leaf diagram",
                }
            )
        )
    )
    document = {
        "document_version": 2,
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "p1",
                        "object": "prose",
                        "intent": "explain",
                        "position": 0,
                        "content": {"paragraphs": ["Intro"]},
                    },
                    {
                        "id": "fig-1",
                        "object": "figure",
                        "intent": "show-structure",
                        "position": 1,
                        "content": figure.content,
                    },
                ],
            }
        ],
    }
    before_ids = [b["id"] for b in document["sections"][0]["blocks"]]
    updated = apply_figure_asset_update(
        document,
        block_id="fig-1",
        asset={"status": "ready", "kind": "image", "src": "https://example.test/fig.png", "request_id": figure.request_id},
    )
    after = updated["sections"][0]["blocks"]
    assert [b["id"] for b in after] == before_ids
    fig = after[1]
    assert fig["position"] == 1
    assert fig["intent"] == "show-structure"
    assert fig["object"] == "figure"
    assert fig["content"]["alt_text"] == figure.content["alt_text"]
    assert fig["content"]["caption"] == figure.content["caption"]
    assert fig["content"]["asset"]["status"] == "ready"

    failed = apply_figure_asset_update(
        document,
        block_id="fig-1",
        asset={"status": "failed", "request_id": figure.request_id},
    )
    assert failed["sections"][0]["blocks"][1]["content"]["asset"]["status"] == "failed"
    assert failed["sections"][0]["blocks"][1]["id"] == "fig-1"

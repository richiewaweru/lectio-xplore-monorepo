from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.models import (
    CalloutDisplay,
    CalloutNode,
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    HeadingDisplay,
    HeadingNode,
    ListDisplay,
    ListNode,
    NodeAccessibility,
    ParagraphDisplay,
    ParagraphNode,
    SharedLessonDocument,
    SharedProvenance,
    SharedSection,
    TableDisplay,
    TableNode,
    TaskAnchor,
    build_shared_lesson_document,
)
from document.shared_lesson.review_revision import (
    ReviewRevisionValidationError,
    prove_review_draft_revision,
)


def _task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-1",
        teaching_plan_id="plan-1",
        teaching_plan_revision=3,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="assessment",
        action="select-one",
        purpose="Check the learner's understanding",
        prompt="Which choice is supported?",
        difficulty="guided",
        expected_evidence="Select the supported choice",
        response={
            "type": "single_choice",
            "options": [{"id": "yes", "text": "Yes"}, {"id": "no", "text": "No"}],
        },
        evaluation={"type": "exact_match", "correct_option_id": "yes"},
    )


def _origin() -> SharedLessonDocument:
    task = _task()
    provenance = SharedProvenance(
        source_ids=("source-1",), source_hashes={"source-1": "c" * 64}
    )
    return build_shared_lesson_document(
        {
            "id": "shared-document:run-1:revision:1",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 3,
            "teaching_plan_hash": "b" * 64,
            "title": "An approved lesson",
            "provenance": provenance,
            "sections": [
                SharedSection(
                    id="section-1",
                    title="Learn",
                    position=0,
                    provenance=provenance,
                    nodes=(
                        ParagraphNode(
                            id="paragraph-1",
                            teaching_block_id="block-1",
                            display=ParagraphDisplay(text="Original paragraph."),
                            accessibility=NodeAccessibility(description="Original description"),
                        ),
                        HeadingNode(
                            id="heading-1",
                            teaching_block_id="block-1",
                            display=HeadingDisplay(text="Original heading"),
                        ),
                        CalloutNode(
                            id="callout-1",
                            teaching_block_id="block-1",
                            display=CalloutDisplay(title="Original title", body="Original body"),
                        ),
                        FigureNode(
                            id="figure-1",
                            teaching_block_id="block-1",
                            display=FigureDisplay(asset_id="asset-1", caption="Original caption"),
                            accessibility=FigureAccessibility(alt_text="Original alt text"),
                        ),
                        ListNode(
                            id="list-1",
                            teaching_block_id="block-1",
                            display=ListDisplay(items=("Original item", "Keep this item")),
                        ),
                        TableNode(
                            id="table-1",
                            teaching_block_id="block-1",
                            display=TableDisplay(
                                headers=("Example",),
                                rows=(("Original cell",),),
                            ),
                        ),
                        TaskAnchor(
                            id="anchor-1",
                            task_spec_id=task.id,
                            teaching_block_id=task.teaching_block_id,
                        ),
                    ),
                ),
                SharedSection(
                    id="section-2",
                    title="Practice",
                    position=1,
                    nodes=(
                        ParagraphNode(
                            id="paragraph-2",
                            display=ParagraphDisplay(text="Second section remains unchanged."),
                        ),
                    ),
                ),
            ],
            "tasks": [task.model_dump(mode="json")],
            "created_at": datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        }
    )


def _revise(origin: SharedLessonDocument, mutate) -> SharedLessonDocument:
    payload = origin.model_dump(mode="json")
    mutate(payload)
    payload["revision"] = origin.revision + 1
    payload.pop("content_hash", None)
    return build_shared_lesson_document(payload)


def _allowed_edits(payload: dict) -> None:
    nodes = payload["sections"][0]["nodes"]
    nodes[0]["display"]["text"] = "Corrected paragraph."
    nodes[0]["accessibility"]["description"] = "Corrected description"
    nodes[1]["display"]["text"] = "Corrected heading"
    nodes[2]["display"].update(title="Corrected title", body="Corrected body")
    nodes[2]["accessibility"]["description"] = "Corrected callout description"
    nodes[3]["display"]["caption"] = "Corrected caption"
    nodes[3]["accessibility"]["alt_text"] = "Corrected alt text"
    nodes[4]["display"]["items"][0] = "Corrected item"
    nodes[4]["accessibility"]["description"] = "Corrected list description"
    nodes[5]["display"]["rows"][0][0] = "Corrected cell"
    nodes[5]["accessibility"]["description"] = "Corrected table description"


def test_review_revision_allows_only_review_api_text_edits_and_reports_revalidation_targets() -> None:
    origin = _origin()
    revised = _revise(origin, _allowed_edits)

    proof = prove_review_draft_revision(origin, revised)

    assert proof.document_id == origin.id
    assert proof.origin_revision == origin.revision
    assert proof.origin_hash == origin.content_hash
    assert proof.revision == revised.revision
    assert proof.content_hash == revised.content_hash
    assert proof.changed_section_ids == ("section-1",)
    assert proof.figure_section_ids == ("section-1",)


@pytest.mark.parametrize(
    ("label", "mutate", "message"),
    [
        (
            "task answer key",
            lambda payload: payload["tasks"][0].update(
                evaluation={"type": "exact_match", "correct_option_id": "no"}
            ),
            "protected task fields",
        ),
        (
            "task option id",
            lambda payload: payload["tasks"][0]["response"]["options"][1].update(id="maybe"),
            "protected task fields",
        ),
        (
            "task action",
            lambda payload: payload["tasks"][0].update(difficulty="independent"),
            "protected task fields",
        ),
        (
            "provenance",
            lambda payload: payload["sections"][0]["provenance"].update(source_ids=[]),
            "section identity or provenance",
        ),
        (
            "node id",
            lambda payload: payload["sections"][0]["nodes"][0].update(id="forged-id"),
            "node identity, shape, or protected fields",
        ),
        (
            "node kind",
            lambda payload: payload["sections"][0]["nodes"][0].update(kind="heading"),
            "node identity, shape, or protected fields",
        ),
        (
            "figure asset",
            lambda payload: payload["sections"][0]["nodes"][3]["display"].update(asset_id="new-asset"),
            "node identity, shape, or protected fields",
        ),
        (
            "section identity",
            lambda payload: payload["sections"][0].update(id="forged-section"),
            "section identity or provenance",
        ),
        (
            "source lineage",
            lambda payload: (
                payload.update(teaching_plan_hash="d" * 64),
                payload["tasks"][0].update(teaching_plan_hash="d" * 64),
            ),
            "document or source lineage",
        ),
        (
            "table shape",
            lambda payload: payload["sections"][0]["nodes"][5]["display"]["rows"][0].append("extra"),
            "table shape",
        ),
        (
            "heading level forged alongside an allowed accessibility edit",
            lambda payload: (
                payload["sections"][0]["nodes"][1]["display"].update(level=3),
                payload["sections"][0]["nodes"][1].setdefault("accessibility", {}).update(
                    description="Sneaked-in description"
                ),
            ),
            "node identity, shape, or protected fields",
        ),
    ],
)
def test_review_revision_rejects_forged_or_structural_changes(label, mutate, message) -> None:
    origin = _origin()
    revised = _revise(origin, mutate)

    with pytest.raises(ReviewRevisionValidationError, match=message):
        prove_review_draft_revision(origin, revised)


def test_figure_accessibility_has_no_reviewer_editable_description_field() -> None:
    """FigureAccessibility only carries alt_text; a forged description is a schema error."""
    origin = _origin()
    payload = origin.model_dump(mode="json")
    payload["sections"][0]["nodes"][3]["accessibility"]["description"] = "Forged"
    payload["revision"] = origin.revision + 1
    payload.pop("content_hash", None)

    with pytest.raises(Exception, match="Extra inputs are not permitted|extra"):
        build_shared_lesson_document(payload)


def test_review_revision_rejects_nonsequential_and_unchanged_revisions() -> None:
    origin = _origin()
    skipped = _revise(origin, _allowed_edits).model_copy(update={"revision": origin.revision + 2})
    unchanged_payload = origin.model_dump(mode="json")
    unchanged_payload["revision"] = origin.revision + 1
    unchanged = build_shared_lesson_document(unchanged_payload)

    with pytest.raises(ReviewRevisionValidationError, match="not sequential"):
        prove_review_draft_revision(origin, skipped)
    with pytest.raises(ReviewRevisionValidationError, match="no content correction"):
        prove_review_draft_revision(origin, unchanged)


def test_review_revision_rejects_stale_canonical_hash() -> None:
    origin = _origin()
    revised = _revise(origin, _allowed_edits).model_copy(update={"content_hash": "0" * 64})

    with pytest.raises(ReviewRevisionValidationError, match="content hash is stale"):
        prove_review_draft_revision(origin, revised)


def test_review_revision_allows_task_wording_corrections_only() -> None:
    """Prompt, choice-option text and feedback wording are editable; the key is not."""
    origin = _origin()

    def mutate(payload: dict) -> None:
        task = payload["tasks"][0]
        task["prompt"] = "Which choice does the passage support?"
        task["response"]["options"][1]["text"] = "No, it does not"

    revised = _revise(origin, mutate)
    proof = prove_review_draft_revision(origin, revised)

    assert proof.changed_task_ids == ("task-1",)
    assert proof.changed_section_ids == ()
    assert revised.tasks[0].evaluation == origin.tasks[0].evaluation


def test_review_revision_rejects_blank_task_prompt() -> None:
    origin = _origin()
    payload = origin.model_dump(mode="json")
    payload["tasks"][0]["prompt"] = "   "
    payload["revision"] = origin.revision + 1
    payload.pop("content_hash", None)
    try:
        revised = build_shared_lesson_document(payload)
    except (TypeError, ValueError):
        return  # schema already refuses a blank prompt
    with pytest.raises(ReviewRevisionValidationError, match="protected task fields"):
        prove_review_draft_revision(origin, revised)


def test_review_revision_freezes_text_that_is_the_answer_key() -> None:
    """For matching/ordering responses the displayed text is the key: frozen."""
    from document.shared_lesson.review_revision import _task_matches_review_contract

    origin = {
        "id": "t",
        "prompt": "Put the stages in order.",
        "response": {"type": "ordered_items", "items": ["A", "B"], "correct_order": ["A", "B"]},
        "evaluation": {"type": "sequence", "order": ["A", "B"]},
        "feedback": {"correct": "Yes.", "incorrect": "Not quite."},
    }
    reworded_prompt = {**origin, "prompt": "Order the stages."}
    reworded_feedback = {**origin, "feedback": {"correct": "Well done.", "incorrect": "Try again."}}
    edited_item = {**origin, "response": {**origin["response"], "items": ["A!", "B"]}}
    new_feedback_key = {**origin, "feedback": {"correct": "Yes.", "partial": "Almost."}}

    assert _task_matches_review_contract(origin, reworded_prompt)
    assert _task_matches_review_contract(origin, reworded_feedback)
    assert not _task_matches_review_contract(origin, edited_item)
    assert not _task_matches_review_contract(origin, new_feedback_key)

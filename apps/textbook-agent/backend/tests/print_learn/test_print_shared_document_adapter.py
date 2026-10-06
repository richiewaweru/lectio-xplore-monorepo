from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.models import (
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    CompareDisplay,
    CompareItem,
    CompareNode,
    EquationDisplay,
    EquationNode,
    HeadingDisplay,
    HeadingNode,
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
    TaskAnchor,
    build_shared_lesson_document,
)
from document.shared_lesson.fixtures import load_shared_lesson_fixture
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentPrintMappingError,
    realize_shared_document_for_print,
)


def _task() -> SharedTaskSpec:
    return SharedTaskSpec(
        id="task-secret-123",
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="assessment",
        action="select-one",
        purpose="Check understanding",
        prompt="Which option is supported?",
        difficulty="guided",
        expected_evidence="Select the supported option",
        response={
            "type": "single_choice",
            "options": [{"id": "internal-a", "text": "First"}, {"id": "internal-b", "text": "Second"}],
        },
        evaluation={"type": "exact_match", "correct_option_id": "internal-b"},
    )


def _stored(*, include_figure: bool = False) -> StoredSharedLessonDocument:
    task = _task()
    nodes = [
        ParagraphNode(
            id="paragraph-1",
            teaching_block_id="block-1",
            display=ParagraphDisplay(text="Shared authored prose."),
        ),
        HeadingNode(
            id="heading-1",
            teaching_block_id="block-1",
            display=HeadingDisplay(text="Shared subsection", level=3),
        ),
        TaskAnchor(id="anchor-secret-456", task_spec_id=task.id, teaching_block_id="block-1"),
    ]
    if include_figure:
        nodes.append(
            FigureNode(
                id="figure-1",
                teaching_block_id="block-1",
                display=FigureDisplay(caption="A figure"),
                accessibility=FigureAccessibility(alt_text="A labeled diagram"),
            )
        )
    document = build_shared_lesson_document(
        {
            "id": "shared-1",
            "revision": 4,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 2,
            "teaching_plan_hash": "b" * 64,
            "title": "A shared lesson",
            "sections": [
                SharedSection(id="section-1", title="First section", position=0, nodes=tuple(nodes))
            ],
            "tasks": [task.model_dump(mode="json")],
            "created_at": datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        }
    )
    return StoredSharedLessonDocument(
        document=document,
        path_lesson_id="path-lesson-1",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )


def _identity(stored: StoredSharedLessonDocument) -> SharedDocumentIdentity:
    doc = stored.document
    return SharedDocumentIdentity(doc.id, doc.revision, doc.content_hash)


def test_print_adapter_verifies_source_and_maps_heading_hierarchy_and_task_labels() -> None:
    stored = _stored()

    result = realize_shared_document_for_print(stored, expected_identity=_identity(stored))

    section = result.document["sections"][0]
    assert section["title"] == "First section"
    assert [block["object"] for block in section["blocks"]] == ["prose", "heading", "choices"]
    assert section["blocks"][1]["content"] == {
        "text": [{"type": "text", "value": "Shared subsection"}],
        "level": 3,
    }
    choice = section["blocks"][2]
    assert choice["content"]["options"] == [
        {"letter": "A", "text": [{"type": "text", "value": "First"}]},
        {"letter": "B", "text": [{"type": "text", "value": "Second"}]},
    ]
    assert result.document["answer_key"]["content"]["groups"][0]["entries"] == [
        {"question_id": "Q1", "answer": [{"type": "text", "value": "B — Second"}]}
    ]
    metadata = result.document["metadata"]["shared_tasks"][0]
    assert metadata == {
        "label": "Q1",
        "anchor_id": "anchor-secret-456",
        "task_spec_id": "task-secret-123",
    }
    assert "task-secret-123" not in str(result.document["answer_key"])


def test_print_adapter_rejects_stale_recomputed_hash() -> None:
    stored = _stored()
    changed = stored.document.model_copy(update={"content_hash": "0" * 64})
    tampered = StoredSharedLessonDocument(
        document=changed,
        path_lesson_id=stored.path_lesson_id,
        status="ready",
        storage_hash=content_hash(changed.model_dump(mode="json")),
    )

    with pytest.raises(SharedDocumentPrintMappingError, match="content hash is stale"):
        realize_shared_document_for_print(tampered, expected_identity=_identity(stored))


def test_print_adapter_fails_when_required_figure_media_is_missing() -> None:
    stored = _stored(include_figure=True)

    with pytest.raises(SharedDocumentPrintMappingError, match="no document-bound Print media"):
        realize_shared_document_for_print(stored, expected_identity=_identity(stored))


def test_print_adapter_projects_doc36_blocks_and_shared_inline_markup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import print.generation.shared_document_adapter as adapter

    document = load_shared_lesson_fixture("golden")
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id="path-lesson-golden",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    media = SimpleNamespace(
        figure_node_id="observe-figure",
        status="ready",
        asset_url="https://cdn.example.test/seedlings.svg",
        alt_text="Two seedlings",
    )
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _doc: m)

    result = realize_shared_document_for_print(
        stored,
        expected_identity=_identity(stored),
        figure_media=[media],
    ).document
    blocks = [block for section in result["sections"] for block in section["blocks"]]
    assert {block["object"] for block in blocks} >= {
        "prose",
        "list",
        "aside",
        "equation",
        "quote",
        "compare",
        "table",
        "choices",
    }
    prose = next(block for block in blocks if block["id"] == "observe-question")
    assert len(prose["content"]["paragraphs"]) == 2
    assert prose["content"]["paragraphs"][1]["children"][0]["type"] == "strong"
    equation = next(block for block in blocks if block["object"] == "equation")
    assert equation["content"]["inputs"][1][0]["type"] == "text"
    assert equation["layout"] == {"placement": "spanning"}
    misconception = next(block for block in blocks if block["id"] == "contrast-belief")
    assert misconception["content"]["variant"] == "misconception"
    assert misconception["content"]["belief"]
    assert result["front_matter"]["contents"] is False
    assert "task-predict" not in str(result["answer_key"])
    # Teacher option notes are keyed by the displayed option letter, never the raw option id.
    notes = [
        entry["option_notes"]
        for group in result["answer_key"]["content"]["groups"]
        for entry in group["entries"]
        if entry.get("option_notes")
    ]
    assert notes
    for note in notes:
        assert all(len(key) == 1 and key.isupper() for key in note), note
    assert not any("soil" in note for note in notes)
    # The teacher answer shows the option letter and its text.
    entries = result["answer_key"]["content"]["groups"][0]["entries"]
    check = "".join(run.get("value", "") for run in entries[1]["answer"] if isinstance(run, dict))
    assert check.startswith("A — A watered plant kept in darkness")


def test_print_adapter_lowers_markup_in_new_block_labels() -> None:
    nodes = (
        EquationNode(
            id="equation-label",
            teaching_block_id="block-1",
            display=EquationDisplay(label="*Energy* input", inputs=("light",), outputs=("growth",)),
        ),
        CompareNode(
            id="compare-label",
            teaching_block_id="block-1",
            display=CompareDisplay(
                items=(
                    CompareItem(label="*A*", title="First", body="One"),
                    CompareItem(label="B", title="Second", body="Two"),
                )
            ),
        ),
    )
    document = build_shared_lesson_document(
        {
            "id": "shared-labels",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "c" * 64,
            "title": "Labels",
            "sections": [SharedSection(id="section-1", title="Labels", position=0, nodes=nodes)],
            "created_at": datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        }
    )
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id="path-labels",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    blocks = realize_shared_document_for_print(
        stored, expected_identity=_identity(stored)
    ).document["sections"][0]["blocks"]
    assert blocks[0]["content"]["label"][0]["type"] == "emphasis"
    assert blocks[1]["content"]["items"][0]["label"][0]["type"] == "emphasis"

@pytest.mark.parametrize(
    ("media_status", "accepted"),
    [("ready", True), ("ready_with_quality_warning", True), ("failed", False)],
)
def test_print_adapter_accepts_quality_warning_media_but_not_failed(
    monkeypatch: pytest.MonkeyPatch, media_status: str, accepted: bool
) -> None:
    """A produced image flagged by visual QC still prints (image quality is not a gate)."""
    from types import SimpleNamespace

    import print.generation.shared_document_adapter as adapter

    stored = _stored(include_figure=True)
    media = SimpleNamespace(
        figure_node_id="figure-1",
        status=media_status,
        asset_url="https://cdn.example.test/figure.png",
    )
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _doc: m)

    if accepted:
        result = realize_shared_document_for_print(
            stored, expected_identity=_identity(stored), figure_media=[media]
        )
        figures = [
            block
            for section in result.document["sections"]
            for block in section["blocks"]
            if block.get("object") == "figure"
        ]
        assert figures and figures[0]["content"]["asset"]["src"] == media.asset_url
    else:
        with pytest.raises(SharedDocumentPrintMappingError, match="media is not ready"):
            realize_shared_document_for_print(
                stored, expected_identity=_identity(stored), figure_media=[media]
            )


def test_print_adapter_ships_unavailable_figure_as_failed_asset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import print.generation.shared_document_adapter as adapter
    from document.shared_lesson.media import bind_durable_media_outcome, unavailable_figure_result
    from tests.document.test_shared_lesson_media import _document, _work

    outcome = bind_durable_media_outcome(
        unavailable_figure_result(
            _work(), error_code="provider_http_403", reason="Service unavailable.", attempts=3
        ).model_dump(mode="json"),
        _document(),
    ).model_copy(update={"figure_node_id": "figure-1"})
    monkeypatch.setattr(adapter, "verify_bound_media_outcome", lambda m, _doc: m)
    stored = _stored(include_figure=True)
    result = realize_shared_document_for_print(
        stored, expected_identity=_identity(stored), figure_media=[outcome]
    )
    figures = [
        block
        for section in result.document["sections"]
        for block in section["blocks"]
        if block.get("object") == "figure"
    ]
    assert figures
    content = figures[0]["content"]
    assert content["asset"] == {"kind": "image", "status": "failed"}
    assert content["alt_text"].strip()

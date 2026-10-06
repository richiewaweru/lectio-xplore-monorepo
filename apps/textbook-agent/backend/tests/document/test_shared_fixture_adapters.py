"""Focused adapter coverage for the Phase 0 presentation contract."""

from __future__ import annotations

import json
from pathlib import Path

from document.models import document_node_adapter
from document.shared_lesson.fixtures import load_shared_lesson_fixture
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    realize_shared_document_for_learn,
)


def _stored(name: str) -> StoredSharedLessonDocument:
    document = load_shared_lesson_fixture(name)
    return StoredSharedLessonDocument(
        document=document,
        path_lesson_id=f"dev-fixture:{name}",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )


def test_golden_learn_adapter_preserves_new_ordinary_fields() -> None:
    stored = _stored("golden")
    result = realize_shared_document_for_learn(
        stored,
        expected_identity=SharedDocumentIdentity(
            id=stored.document.id,
            revision=stored.document.revision,
            content_hash=shared_lesson_content_hash(stored.document),
        ),
        subject="Science",
    )

    by_kind = {node.kind: node for node in result.document.nodes if node.kind != "interaction"}
    assert by_kind["equation"].inputs == ["water", "carbon dioxide (CO~2~)"]
    assert by_kind["equation"].condition == "light energy"
    assert by_kind["equation"].outputs == ["sugar (the plant's food)"]
    assert by_kind["quote"].text.startswith("Plants get their food")
    assert [item.title for item in by_kind["compare"].items] == [
        "From the soil",
        "From the light",
    ]
    misconception = next(node for node in result.document.nodes if node.id == "contrast-belief")
    assert misconception.variant == "misconception"
    assert misconception.belief.startswith("*The soil feeds the plant")
    assert misconception.body is None

    prediction = next(node for node in result.document.nodes if node.kind == "interaction")
    assert prediction.role == "predict"
    assert prediction.display_prompt
    assert prediction.option_notes
    assert prediction.contract["shared_task"]["role"] == "predict"
    assert prediction.contract["shared_task"]["display_prompt"]
    assert prediction.contract["shared_task"]["option_notes"]
    assert prediction.feedback["saved"].startswith("Prediction saved")


def test_legacy_ordinary_nodes_do_not_gain_new_null_fields() -> None:
    payload = json.loads(
        (Path(__file__).parents[5] / "docs/doc36-presentation/evidence/legacy-learn-export.json").read_text(
            encoding="utf-8"
        )
    )
    for raw in payload["document"]["nodes"]:
        if raw.get("kind") == "interaction":
            continue
        node = document_node_adapter.validate_python(raw)
        serialized = node.model_dump(mode="json")
        assert "variant" not in serialized
        assert "equation" not in serialized.get("kind", "")

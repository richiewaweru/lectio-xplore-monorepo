from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from document.shared_lesson import (
    SharedLessonDocument,
    build_shared_lesson_document,
    shared_lesson_content_hash,
    verify_shared_lesson_source,
)

PLAN_HASH = "a" * 64


def _payload() -> dict[str, object]:
    return {
        "id": "lesson-1",
        "revision": 1,
        "teaching_plan_id": "plan-1",
        "teaching_plan_revision": 3,
        "teaching_plan_hash": PLAN_HASH,
        "title": "Photosynthesis",
        "sections": [
            {
                "id": "section-1",
                "title": "How plants make food",
                "position": 0,
                "nodes": [
                    {
                        "id": "paragraph-1",
                        "kind": "paragraph",
                        "display": {"text": "Plants use light."},
                    },
                    {
                        "id": "heading-1",
                        "kind": "heading",
                        "display": {"text": "Light", "level": 3},
                    },
                    {
                        "id": "list-1",
                        "kind": "list",
                        "display": {"items": ["Sunlight", "Water"]},
                    },
                    {
                        "id": "figure-1",
                        "kind": "figure",
                        "display": {"caption": "Leaf cross-section"},
                        "accessibility": {"alt_text": "Leaf showing chloroplasts"},
                    },
                    {
                        "id": "table-1",
                        "kind": "table",
                        "display": {"headers": ["Input", "Role"], "rows": [["Light", "Energy"]]},
                    },
                    {
                        "id": "callout-1",
                        "kind": "callout",
                        "display": {"tone": "tip", "body": "Remember the light."},
                    },
                    {
                        "id": "anchor-1",
                        "kind": "task_anchor",
                        "task_spec_id": "task-1",
                        "teaching_block_id": "block-1",
                    },
                ],
                "provenance": {"source_ids": ["source-1"]},
            }
        ],
        "tasks": [
            {
                "id": "task-1",
                "teaching_plan_id": "plan-1",
                "teaching_plan_revision": 3,
                "teaching_plan_hash": PLAN_HASH,
                "teaching_block_id": "block-1",
                "mode": "formative",
                "action": "select-one",
                "purpose": "Check understanding",
                "prompt": "What does a plant need?",
                "difficulty": "guided",
                "sourcebook_refs": [],
                "expected_evidence": "Select light",
                "response": {
                    "type": "single_choice",
                    "options": [
                        {"id": "light", "text": "Light"},
                        {"id": "sand", "text": "Sand"},
                    ],
                },
                "evaluation": {"type": "exact_match", "correct_option_id": "light"},
                "feedback": None,
                "approved_source_ids": [],
            }
        ],
        "provenance": {"source_ids": ["source-1"], "source_hashes": {"source-1": "b" * 64}},
        "created_at": "2026-09-24T09:00:00+03:00",
    }


def test_document_round_trips_closed_v1_contract_and_task_anchor() -> None:
    document = build_shared_lesson_document(_payload())

    restored = SharedLessonDocument.model_validate_json(document.model_dump_json())

    assert restored == document
    assert restored.content_hash == shared_lesson_content_hash(restored)
    assert [node.kind for node in restored.sections[0].nodes] == [
        "paragraph",
        "heading",
        "list",
        "figure",
        "table",
        "callout",
        "task_anchor",
    ]
    assert restored.sections[0].nodes[3].accessibility.alt_text == "Leaf showing chloroplasts"
    assert restored.tasks[0].response["options"][0]["id"] == "light"


def test_hash_tracks_task_meaning_and_excludes_artifact_metadata() -> None:
    payload = _payload()
    original = build_shared_lesson_document(payload)
    changed_metadata = deepcopy(payload)
    changed_metadata["created_at"] = "2026-09-25T09:00:00+03:00"
    changed_metadata["id"] = "regenerated-lesson"
    changed_metadata["revision"] = 2
    changed_metadata["diagnostics"] = ["retry count: 2"]
    changed = build_shared_lesson_document(changed_metadata)
    changed_task = deepcopy(payload)
    changed_task["tasks"][0]["prompt"] = "Name something a plant needs."

    assert changed.content_hash == original.content_hash
    assert build_shared_lesson_document(changed_task).content_hash != original.content_hash


def test_contract_rejects_path_specific_fields_and_unknown_node_kinds() -> None:
    path_specific = _payload()
    path_specific["print_pages"] = []
    with pytest.raises(ValidationError):
        build_shared_lesson_document(path_specific)

    unknown_node = _payload()
    unknown_node["sections"][0]["nodes"][0] = {"id": "x", "kind": "learn_widget"}
    with pytest.raises(ValidationError):
        build_shared_lesson_document(unknown_node)


@pytest.mark.parametrize("alt_text", [None, "", "   "])
def test_figure_requires_meaningful_alt_text(alt_text: str | None) -> None:
    payload = _payload()
    figure = payload["sections"][0]["nodes"][3]
    if alt_text is None:
        del figure["accessibility"]["alt_text"]
    else:
        figure["accessibility"]["alt_text"] = alt_text

    with pytest.raises(ValidationError, match="alt_text"):
        build_shared_lesson_document(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["sections"][0].update(position=1), "positions"),
        (lambda value: value["sections"][0]["nodes"][1].update(id="paragraph-1"), "IDs"),
        (lambda value: value["sections"][0]["nodes"].pop(), "TaskAnchor"),
        (lambda value: value["sections"][0]["nodes"][6].update(teaching_block_id="other"), "owner"),
        (lambda value: value["tasks"][0].update(teaching_plan_hash="c" * 64), "lineage"),
    ],
)
def test_rejects_incomplete_or_mismatched_contract(mutate, message: str) -> None:
    payload = _payload()
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        build_shared_lesson_document(payload)


def test_source_verification_and_ready_artifact_immutability() -> None:
    document = build_shared_lesson_document(_payload())
    verify_shared_lesson_source(
        document,
        teaching_plan_id="plan-1",
        teaching_plan_revision=3,
        teaching_plan_hash=PLAN_HASH,
    )
    with pytest.raises(ValueError, match="source identity mismatch"):
        verify_shared_lesson_source(
            document,
            teaching_plan_id="other-plan",
            teaching_plan_revision=3,
            teaching_plan_hash=PLAN_HASH,
        )
    with pytest.raises(ValidationError):
        document.title = "Mutated"
    with pytest.raises(TypeError, match="immutable"):
        document.tasks[0].response["type"] = "text"


def test_rejects_stale_canonical_hash() -> None:
    payload = _payload()
    payload["content_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="content_hash"):
        SharedLessonDocument.model_validate(payload)


@pytest.mark.parametrize(
    "response,evaluation",
    [
        ({"type": "single_choice", "options": []}, {"type": "exact_match"}),
        ({"type": "text"}, {"type": "exact_match", "correct_option_id": "light"}),
        (
            {
                "type": "single_choice",
                "options": [{"id": "light", "text": "Light"}, {"id": "sand", "text": "Sand"}],
            },
            {"type": "exact_match", "correct_option_id": "missing"},
        ),
    ],
)
def test_ready_document_rejects_incomplete_or_conflicting_task_meaning(
    response: dict[str, object], evaluation: dict[str, object]
) -> None:
    payload = _payload()
    payload["tasks"][0]["response"] = response
    payload["tasks"][0]["evaluation"] = evaluation

    with pytest.raises(ValidationError, match="invalid shared task response/evaluation"):
        build_shared_lesson_document(payload)

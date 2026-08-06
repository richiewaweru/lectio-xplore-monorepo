"""Answer-key integrity: orphan, missing, duplicate, invalid MCQ letter."""

from __future__ import annotations

import pytest

from generation.page_objects import (
    AnswerKeyIntegrityError,
    validate_answer_key_integrity,
)
from generation.page_objects.document_assembly import (
    DocumentAssemblyError,
    assemble_document_v2,
)


def _blocks() -> list[dict]:
    return [
        {
            "id": "s4-questions",
            "object": "questions",
            "intent": "check-understanding",
            "position": 0,
            "content": {
                "items": [
                    {"id": "q-open-1", "prompt": "Why cover the leaf?"},
                ]
            },
        },
        {
            "id": "q-mcq-1",
            "object": "choices",
            "intent": "diagnose-misconception",
            "position": 1,
            "content": {
                "stem": "Role of soil?",
                "options": [
                    {"letter": "A", "text": "Food"},
                    {"letter": "B", "text": "Minerals"},
                    {"letter": "C", "text": "Sunlight"},
                ],
            },
        },
    ]


def _valid_entries() -> list[dict]:
    return [
        {"question_id": "q-open-1", "answer": "Light is required."},
        {"question_id": "q-mcq-1", "answer": "B"},
    ]


def test_valid_integrity_passes() -> None:
    validate_answer_key_integrity(_blocks(), _valid_entries())


def test_orphan_answer_rejected() -> None:
    entries = _valid_entries() + [{"question_id": "unknown-q", "answer": "X"}]
    with pytest.raises(AnswerKeyIntegrityError, match="orphan"):
        validate_answer_key_integrity(_blocks(), entries)


def test_missing_answer_rejected() -> None:
    entries = [e for e in _valid_entries() if e["question_id"] != "q-open-1"]
    with pytest.raises(AnswerKeyIntegrityError, match="missing"):
        validate_answer_key_integrity(_blocks(), entries)


def test_duplicate_answer_rejected() -> None:
    entries = _valid_entries() + [{"question_id": "q-open-1", "answer": "Dup"}]
    with pytest.raises(AnswerKeyIntegrityError, match="duplicate"):
        validate_answer_key_integrity(_blocks(), entries)


def test_invalid_mcq_letter_rejected() -> None:
    entries = [
        {"question_id": "q-open-1", "answer": "Light is required."},
        {"question_id": "q-mcq-1", "answer": "D"},
    ]
    with pytest.raises(AnswerKeyIntegrityError, match="MCQ answer"):
        validate_answer_key_integrity(_blocks(), entries)


def test_assemble_document_attaches_answer_key() -> None:
    sections = [
        {
            "id": "section-4",
            "title": "Check",
            "blocks": _blocks(),
        }
    ]
    doc = assemble_document_v2(
        title="Light lesson",
        sections=sections,
        document_id="lesson-1",
        answer_entries=_valid_entries(),
    )
    assert doc["answer_key"]["object"] == "answer-key"
    assert doc["answer_key"]["content"]["groups"][0]["entries"][0]["question_id"] == "q-open-1"


def test_assemble_document_rejects_bad_answers() -> None:
    sections = [{"id": "section-4", "title": "Check", "blocks": _blocks()}]
    with pytest.raises(DocumentAssemblyError):
        assemble_document_v2(
            title="Light lesson",
            sections=sections,
            answer_entries=[{"question_id": "unknown", "answer": "x"}],
        )

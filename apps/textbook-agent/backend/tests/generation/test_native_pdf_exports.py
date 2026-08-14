"""Gate 9 — student/teacher PDF exports from native documents."""

from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from contracts.lectio_page import validate_document
from generation.page_objects.views import render_document_pdf, student_document, teacher_document

REPO_ROOT = Path(__file__).resolve().parents[5]
EXPECTED = (
    REPO_ROOT
    / "docs"
    / "packs"
    / "xplore_native_e2e_implementation_pack_v1"
    / "08_FIXTURES"
    / "expected_lectio_document_v2.json"
)

OPEN_ANSWER_SNIPPET = "the changed condition shows that light is required"


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def test_student_and_teacher_pdf_exports(tmp_path: Path) -> None:
    doc = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert validate_document(doc) == []

    student_path = tmp_path / "student.pdf"
    teacher_path = tmp_path / "teacher.pdf"
    render_document_pdf(doc, student_path, audience="student")
    render_document_pdf(doc, teacher_path, audience="teacher")

    assert student_path.exists()
    assert teacher_path.exists()
    assert student_path.read_bytes().startswith(b"%PDF")
    assert teacher_path.read_bytes().startswith(b"%PDF")

    teacher_text = _pdf_text(teacher_path)
    student_text = _pdf_text(student_path)
    assert teacher_text.count("Answer key") == 1
    assert OPEN_ANSWER_SNIPPET in teacher_text.replace("\n", " ")
    # Student must not include answer-key content (open-response phrase).
    assert "Answer key" not in student_text
    assert OPEN_ANSWER_SNIPPET not in student_text.replace("\n", " ")

    student_proj = student_document(doc)
    teacher_proj = teacher_document(doc)
    assert "answer_key" not in student_proj
    assert "answer_key" in teacher_proj

from pathlib import Path

from generation.pdf_export.components.answers_v3 import generate_v3_answer_key_pdf


def test_generate_v3_answer_key_pdf_none_when_missing(tmp_path: Path) -> None:
    out = tmp_path / "ak.pdf"
    assert generate_v3_answer_key_pdf(output_path=out, answer_key=None) is None
    assert not out.exists()


def test_generate_v3_answer_key_pdf_writes_entries(tmp_path: Path) -> None:
    out = tmp_path / "ak.pdf"
    path = generate_v3_answer_key_pdf(
        output_path=out,
        answer_key={
            "entries": [
                {"question_id": "q1", "student_answer": "42", "working": "Show steps"},
            ]
        },
    )
    assert path is not None
    assert out.exists()
    assert out.stat().st_size > 100

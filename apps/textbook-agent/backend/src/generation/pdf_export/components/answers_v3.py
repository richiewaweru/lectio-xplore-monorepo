from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_WRAP_WIDTH = 95


def build_diagnostic_answer_key_content(
    *,
    items: list[dict[str, Any]],
    misconception_labels: dict[tuple[str, str], str],
) -> dict[str, Any]:
    """Build Lectio's `answer-key` component payload for one shared pack quiz."""
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        options = [
            option for option in item.get("options", [])
            if isinstance(option, dict)
        ]
        correct_key = _safe_str(item.get("correct_key"))
        correct = next(
            (option for option in options if _safe_str(option.get("key")) == correct_key),
            None,
        )
        if correct is None:
            continue
        card_id = _safe_str(item.get("card_id"))
        diagnostics: list[dict[str, Any]] = []
        for option in options:
            misconception_id = _safe_str(option.get("diagnoses"))
            if not misconception_id:
                continue
            option_text = _safe_str(option.get("text"))
            misconception = misconception_labels.get(
                (card_id, misconception_id),
                misconception_id,
            )
            diagnostics.append(
                {
                    "option_key": _safe_str(option.get("key")) or None,
                    "option_text": option_text,
                    "misconception_id": misconception_id,
                    "misconception_label": (
                        f'Chose "{option_text}" → consistent with: {misconception}'
                    ),
                }
            )
        entries.append(
            {
                "question_number": float(index),
                "question": _safe_str(item.get("stem")),
                "correct_answer": _safe_str(correct.get("text")),
                "correct_key": correct_key or None,
                "diagnostics": diagnostics or None,
            }
        )
    return {
        "label": "Shared diagnostic answer key",
        "note": (
            "Diagnostic tags are hypotheses about what an option may indicate; "
            "confirm them against learner reasoning."
        ),
        "entries": entries,
    }


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _wrap_lines(text: str) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph.strip():
            lines.extend(textwrap.wrap(paragraph, width=_WRAP_WIDTH, break_long_words=True) or [""])
        else:
            lines.append("")
    return lines or [""]


def generate_v3_answer_key_pdf(
    *,
    output_path: Path,
    answer_key: dict[str, Any] | None,
) -> Path | None:
    """Render V3 `GeneratedAnswerKeyBlock` entries (from `document_json.answer_key`) to a PDF."""
    if not answer_key or not isinstance(answer_key, dict):
        return None
    entries = answer_key.get("entries")
    if not isinstance(entries, list) or not entries:
        return None

    rows: list[tuple[str, str, str]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        qid = (
            _safe_str(raw.get("question_id"))
            or _safe_str(raw.get("question_number"))
            or "question"
        )
        answer = (
            _safe_str(raw.get("student_answer"))
            or _safe_str(raw.get("answer"))
            or _safe_str(raw.get("correct_answer"))
        )
        if not answer:
            continue
        working = _safe_str(raw.get("working"))
        notes = _safe_str(raw.get("notes"))
        explanation = _safe_str(raw.get("explanation"))
        diagnostic_copy = "; ".join(
            _safe_str(diagnostic.get("misconception_label"))
            for diagnostic in raw.get("diagnostics", [])
            if isinstance(diagnostic, dict)
            and _safe_str(diagnostic.get("misconception_label"))
        )
        extra_parts = [p for p in (working, notes, explanation, diagnostic_copy) if p]
        detail = " — ".join(extra_parts) if extra_parts else ""
        rows.append((qid, answer, detail))

    if not rows:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - 28 * mm

    pdf.setTitle("Answer Key")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20 * mm, y, "Answer Key (V3)")
    y -= 12 * mm

    line_height = 4.2 * mm
    margin_x = 20 * mm

    pdf.setFont("Helvetica-Bold", 10)
    for qid, answer, detail in rows:
        if y < 25 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica-Bold", 10)

        pdf.drawString(margin_x, y, qid)
        y -= line_height
        pdf.setFont("Helvetica", 10)
        for line in _wrap_lines(answer):
            if y < 20 * mm:
                pdf.showPage()
                y = height - 20 * mm
                pdf.setFont("Helvetica", 10)
            pdf.drawString(margin_x + 2 * mm, y, line)
            y -= line_height * 0.85
        if detail:
            pdf.setFont("Helvetica-Oblique", 9)
            for line in _wrap_lines(detail):
                if y < 20 * mm:
                    pdf.showPage()
                    y = height - 20 * mm
                    pdf.setFont("Helvetica-Oblique", 9)
                pdf.drawString(margin_x + 4 * mm, y, line)
                y -= line_height * 0.8
        pdf.setFont("Helvetica-Bold", 10)
        y -= line_height * 0.5

    pdf.save()
    return output_path


__all__ = [
    "build_diagnostic_answer_key_content",
    "generate_v3_answer_key_pdf",
]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from contracts.section_content_helpers import practice_problems, section_title
from contracts.section_content import SectionContent


@dataclass(slots=True)
class AnswerEntry:
    section_title: str
    prompt: str
    answer: str
    explanation: str | None = None


def extract_answer_entries(sections: list[SectionContent]) -> list[AnswerEntry]:
    entries: list[AnswerEntry] = []
    for section in sections:
        title = section_title(section)

        if section.quiz is not None:
            for option in section.quiz.options:
                if option.correct:
                    entries.append(
                        AnswerEntry(
                            section_title=title,
                            prompt=section.quiz.question,
                            answer=option.text,
                            explanation=option.explanation,
                        )
                    )

        for index, problem in enumerate(practice_problems(section), start=1):
            if problem.solution is None:
                continue
            entries.append(
                AnswerEntry(
                    section_title=title,
                    prompt=f"Practice {index}: {problem.question}",
                    answer=problem.solution.answer,
                    explanation=problem.solution.approach,
                )
            )

        if section.worked_example is not None and section.worked_example.answer:
            entries.append(
                AnswerEntry(
                    section_title=title,
                    prompt=section.worked_example.title,
                    answer=section.worked_example.answer,
                    explanation=section.worked_example.conclusion,
                )
            )

    return entries


def generate_answer_key_pdf(
    *,
    output_path: Path,
    sections: list[SectionContent],
) -> Path | None:
    entries = extract_answer_entries(sections)
    if not entries:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - 28 * mm

    pdf.setTitle("Answer Key")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20 * mm, y, "Answer Key")
    y -= 14 * mm

    current_section: str | None = None
    for entry in entries:
        if y < 28 * mm:
            pdf.showPage()
            y = height - 24 * mm
            current_section = None

        if entry.section_title != current_section:
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(20 * mm, y, entry.section_title)
            y -= 8 * mm
            current_section = entry.section_title

        pdf.setFont("Helvetica-Bold", 11)
        for line in _wrap_text(entry.prompt, 88):
            pdf.drawString(24 * mm, y, line)
            y -= 6 * mm

        pdf.setFont("Helvetica", 11)
        for line in _wrap_text(f"Answer: {entry.answer}", 88):
            pdf.drawString(28 * mm, y, line)
            y -= 6 * mm

        if entry.explanation:
            pdf.setFont("Helvetica-Oblique", 10)
            for line in _wrap_text(f"Explanation: {entry.explanation}", 84):
                pdf.drawString(28 * mm, y, line)
                y -= 5 * mm

        y -= 5 * mm

    pdf.showPage()
    pdf.save()
    return output_path


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


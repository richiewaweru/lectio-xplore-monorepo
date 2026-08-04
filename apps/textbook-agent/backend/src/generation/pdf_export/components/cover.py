from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
}
_PROMPT_PREFIX_PATTERNS = (
    re.compile(r"^\s*i\s+want\s+to\s+teach\b.*?\babout\s+", re.IGNORECASE),
    re.compile(r"^\s*teach(?:ing)?\b.*?\babout\s+", re.IGNORECASE),
    re.compile(r"^\s*(?:a\s+)?(?:visually\s+enhanced\s+)?lesson\s+about\s+", re.IGNORECASE),
)
_PHRASES_TO_STRIP = (
    "the process of",
    "process of",
    "a lesson on",
    "lesson on",
    "a lesson about",
    "lesson about",
)


def generate_cover_pdf(
    *,
    output_path: Path,
    title: str,
    school_name: str,
    teacher_name: str,
    date_label: str | None,
) -> Path:
    cover_title = clean_cover_title(title)
    formatted_date = format_cover_date(date_label)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    pdf.setTitle(cover_title)
    pdf.setFont("Helvetica-Bold", _title_font_size(cover_title))
    title_text = pdf.beginText(25 * mm, height - 48 * mm)
    title_text.setLeading(18)
    for line in _wrap_text(cover_title, 36):
        title_text.textLine(line)
    pdf.drawText(title_text)

    card_left = 25 * mm
    card_width = width - 50 * mm
    card_top = height - 92 * mm
    card_height = 52 * mm
    pdf.roundRect(card_left, card_top - card_height, card_width, card_height, 8, stroke=1, fill=0)

    details = [
        ("School", school_name),
        ("Teacher", teacher_name),
        ("Date", formatted_date),
    ]
    y = card_top - 12 * mm
    for label, value in details:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(card_left + 8 * mm, y, f"{label}:")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(card_left + 34 * mm, y, value)
        y -= 12 * mm

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(25 * mm, 38 * mm, "Student Name:")
    pdf.line(58 * mm, 37 * mm, width - 25 * mm, 37 * mm)

    pdf.showPage()
    pdf.save()
    return output_path


def clean_cover_title(raw_title: str) -> str:
    title = (raw_title or "").strip()
    if not title:
        return "Lesson"

    title = title.splitlines()[0]
    title = re.split(r"\bAudience\s*:", title, maxsplit=1, flags=re.IGNORECASE)[0]
    title = re.split(r"[.;:!?]", title, maxsplit=1)[0]
    title = re.sub(r"\s+", " ", title).strip(" -")

    for pattern in _PROMPT_PREFIX_PATTERNS:
        title = pattern.sub("", title).strip(" -")
    lowered = title.lower()
    for phrase in _PHRASES_TO_STRIP:
        if lowered.startswith(phrase):
            title = title[len(phrase) :].strip(" -")
            lowered = title.lower()

    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", title)
    if not words:
        return "Lesson"

    trimmed = _trim_title_words(words)
    return " ".join(_title_case_word(word) for word in trimmed) or "Lesson"


def format_cover_date(date_label: str | None) -> str:
    if date_label:
        parsed = _parse_date_label(date_label.strip())
        if parsed is not None:
            return f"{parsed.day} {parsed.strftime('%B')} {parsed.year}"
        if date_label.strip():
            return date_label.strip()

    today = date.today()
    return f"{today.day} {today.strftime('%B')} {today.year}"


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


def _parse_date_label(value: str) -> date | None:
    if not value:
        return None
    for parser in (date.fromisoformat, _parse_datetime_date):
        try:
            return parser(value)
        except ValueError:
            continue
    return None


def _parse_datetime_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _title_font_size(title: str) -> int:
    if len(title) > 44:
        return 22
    if len(title) > 28:
        return 24
    return 28


def _trim_title_words(words: list[str]) -> list[str]:
    if len(words) <= 4:
        return words

    for index, word in enumerate(words):
        if word.lower() in _TITLE_STOPWORDS:
            continue
        return words[index : index + 4]
    return words[:4]


def _title_case_word(word: str) -> str:
    return "-".join(part[:1].upper() + part[1:].lower() for part in word.split("-"))

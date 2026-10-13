"""The FIGURE KINDS card is present, identical, and covers every render family.

Prompts are plain text (no include mechanism), so the card is copied into each
prompt that routes figures. These tests keep the copies identical and check the
card describes every code-rendered family.
"""

from __future__ import annotations

from pathlib import Path

from media.render.contracts import FAMILIES
from print.generation.whole_lesson.prompt_render import BACKBONE_TEACHING_GUIDANCE

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "resources" / "prompts"
BACKBONE_PROMPT = PROMPTS_DIR / "lesson-backbone-writer.md"
SECTION_PROMPT = PROMPTS_DIR / "teaching-section.md"

CARD = """FIGURE KINDS. Every figure has a `mode`:
- render: drawn exactly and to scale: tables of values, bar charts, graphs of a rule (y = 2x + 1), number lines, shapes with given side lengths, simple step flows, and cycles. It cannot draw real objects such as plants, apparatus or organs.
- diagram: a flat, labelled schematic of real things and their named parts. It may carry value labels as text (for example 'Height Day 28: 48 cm'), but it is not to scale: its numbers are words on the picture, not measurements to read off.
- image: a realistic scene or object where what it looks like is the point. Little or no text.
Choose in this order: if the learner must read exact values, lengths or positions from the figure, use render. If the learner must see real things and their named parts, use diagram. If only the look matters, use image. A figure whose data holds a series of values (a list of numbers) is always render.
Examples: a table of seedling heights at each weekly check is render; two labelled seedlings side by side, one green and tall in the sun, one pale and short in the dark, with their heights written as labels, is diagram."""

DECISION_SENTENCE = (
    "Choose in this order: if the learner must read exact values, lengths or "
    "positions from the figure, use render."
)

# Phrase the card uses for each render family. Keep in step with FAMILIES.
FAMILY_PHRASES = {
    "polygon_area": "shapes with given side lengths",
    "number_line": "number lines",
    "bar_chart": "bar charts",
    "function_graph": "graphs of a rule",
    "flow": "step flows",
    "cycle": "cycles",
    "table": "tables of values",
}

OLD_TWO_WAY_WORDING = '"diagram" for anything measured or structured'


def _normal(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").split())


def _backbone_text() -> str:
    return BACKBONE_PROMPT.read_text(encoding="utf-8")


def _section_text() -> str:
    return SECTION_PROMPT.read_text(encoding="utf-8")


def _print_text() -> str:
    return BACKBONE_TEACHING_GUIDANCE


def _render_clause() -> str:
    for line in CARD.splitlines():
        if line.startswith("- render:"):
            return line
    raise AssertionError("FIGURE KINDS card has no render line")


def test_every_render_family_is_described_by_the_card() -> None:
    missing_mapping = [f for f in FAMILIES if f not in FAMILY_PHRASES]
    assert not missing_mapping, (
        f"render families without a FIGURE KINDS phrase: {missing_mapping}. "
        "Add the family to FAMILY_PHRASES and describe it in the card."
    )
    render_clause = _render_clause()
    for family in FAMILIES:
        phrase = FAMILY_PHRASES[family]
        assert phrase in render_clause, (
            f"FIGURE KINDS render line does not describe family '{family}' "
            f"(expected phrase {phrase!r})."
        )


def test_card_copies_are_identical_to_the_canonical_card() -> None:
    expected = _normal(CARD)
    for label, text in (
        ("lesson-backbone-writer.md", _backbone_text()),
        ("teaching-section.md", _section_text()),
        ("BACKBONE_TEACHING_GUIDANCE (print)", _print_text()),
    ):
        assert expected in _normal(text), f"{label} does not contain the FIGURE KINDS card"


def test_backbone_section_and_print_prompts_state_render_and_the_decision() -> None:
    for label, text in (
        ("lesson-backbone-writer.md", _backbone_text()),
        ("teaching-section.md", _section_text()),
        ("BACKBONE_TEACHING_GUIDANCE (print)", _print_text()),
    ):
        assert "render" in text, f"{label} does not mention render"
        assert _normal(DECISION_SENTENCE) in _normal(text), (
            f"{label} does not contain the card's decision sentence"
        )


def test_old_two_way_mode_wording_is_gone() -> None:
    for label, text in (
        ("lesson-backbone-writer.md", _backbone_text()),
        ("teaching-section.md", _section_text()),
        ("BACKBONE_TEACHING_GUIDANCE (print)", _print_text()),
    ):
        assert _normal(OLD_TWO_WAY_WORDING) not in _normal(text), (
            f"{label} still has the old two-way mode wording"
        )

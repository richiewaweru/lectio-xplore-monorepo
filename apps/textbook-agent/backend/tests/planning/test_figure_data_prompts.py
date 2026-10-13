from __future__ import annotations

from core.prompts import effective_prompt_text


def _flat(prompt_id: str) -> str:
    return " ".join(effective_prompt_text(prompt_id).split())


def test_spine_prompt_drops_quantity_relationship_reason() -> None:
    prompt = _flat("teaching-spine")

    assert "a relationship between quantities" not in prompt


def test_spine_prompt_forbids_numeric_figures_without_backbone_id() -> None:
    prompt = _flat("teaching-spine")

    assert "Never plan a figure that shows numbers with `backbone_figure_id` null" in prompt


def test_section_prompt_keeps_data_copied_by_code() -> None:
    prompt = _flat("teaching-section")

    assert "do not write `data`" in prompt
    assert "no digits" in prompt


def test_backbone_prompt_makes_backbone_the_only_number_source() -> None:
    prompt = _flat("lesson-backbone-writer")

    assert "The backbone is the only place numbers are authored" in prompt


def test_shared_section_prompt_forbids_altering_numbers() -> None:
    prompt = _flat("shared-section-writer")

    assert "Never alter, round, or add a number" in prompt

"""Tests for schema shape injection into section writer component contracts."""

from __future__ import annotations

import pytest

from contracts.lectio import clear_cache, get_component_card, get_component_schema_shape
from v3_execution.prompts.section_writer import format_component_contract_for_writer


@pytest.fixture(autouse=True)
def _clear_contract_cache() -> None:
    clear_cache()


def test_explanation_block_surfaces_callout_enum_in_prompt() -> None:
    card = get_component_card("explanation-block")
    assert card is not None
    output = format_component_contract_for_writer(card, "teach photosynthesis")

    for value in ["remember", "insight", "sidenote", "warning", "exam-tip"]:
        assert value in output, f"Expected enum value '{value}' in writer prompt"


def test_explanation_block_labels_emphasis_as_required() -> None:
    card = get_component_card("explanation-block")
    assert card is not None
    output = format_component_contract_for_writer(card, "teach photosynthesis")

    assert "emphasis" in output
    emphasis_line = next(
        line for line in output.splitlines() if "emphasis [string[]" in line
    )
    assert "required" in emphasis_line


def test_no_raw_ref_strings_in_explanation_block_prompt() -> None:
    card = get_component_card("explanation-block")
    assert card is not None
    output = format_component_contract_for_writer(card, "teach photosynthesis")

    assert "$ref" not in output


def test_hook_hero_surfaces_type_enum() -> None:
    card = get_component_card("hook-hero")
    assert card is not None
    output = format_component_contract_for_writer(card, "hook for photosynthesis lesson")

    for value in ["prose", "quote", "question", "data-point"]:
        assert value in output, f"Expected hook type '{value}' in writer prompt"


def test_missing_schema_summary_returns_gracefully() -> None:
    card = {"component_id": "unknown-block", "section_field": "x"}
    output = format_component_contract_for_writer(card, "some intent")

    assert isinstance(output, str)
    assert "$ref" not in output


def test_get_component_schema_shape_explanation_block() -> None:
    shape = get_component_schema_shape("explanation-block")

    assert shape is not None
    assert shape["definition"] == "ExplanationContent"

    props = {p["name"]: p for p in shape["properties"]}

    assert props["body"]["required"] is True
    assert props["emphasis"]["required"] is True
    assert props["callouts"]["required"] is False

    callout_nested = {n["name"]: n for n in props["callouts"]["nested"]}
    assert set(callout_nested["type"]["enum"]) == {
        "remember",
        "insight",
        "sidenote",
        "warning",
        "exam-tip",
    }

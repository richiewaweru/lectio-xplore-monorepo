"""A00 regressions for Learn interaction writers that fabricate answer keys."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from learn.generation.interaction_writer import (
    InteractionWriterError,
    write_interaction_from_request,
)


def _request(capability_id: str, brief: str, **extra: object) -> dict[str, object]:
    return {
        "work_order_id": f"a00::{capability_id}",
        "block_id": f"b-{capability_id}",
        "capability_id": capability_id,
        "lane": "interaction",
        "brief": brief,
        "intent": "check-understanding",
        "action": None,
        "evidence": "A00 independently specified answer regression",
        "teaching_plan_hash": "a00-plan",
        "capability_contract_hash": "a00-capability",
        **extra,
    }


def test_a00_numeric_uses_independent_answer_not_first_number() -> None:
    """KNOWN_ANSWER_CASES numeric-distance: expected 50 m, not first number 5."""
    payload = write_interaction_from_request(
        _request(
            "numeric",
            "A cart moves at speed = 5 m/s for time = 10 s. Enter the distance in m.",
        )
    )

    assert payload["config"]["value"] == 50
    assert payload["config"].get("unit") == "m"


def test_a00_fill_blank_uses_supplied_answer_not_last_word() -> None:
    """KNOWN_ANSWER_CASES fill-pigment: accepted answer is chlorophyll."""
    payload = write_interaction_from_request(
        _request("fill-blank", "The green pigment is ___.")
    )

    assert payload["config"]["answers"] == ["chlorophyll"]


def test_a00_choice_rejects_invalid_correct_key_instead_of_first_option() -> None:
    """KNOWN_ANSWER_CASES choice-nonfirst: invalid key z must fail, never choose a."""
    approved = SimpleNamespace(
        id="choice-nonfirst",
        stem="What is evaporation?",
        options=(
            {"id": "a", "text": "liquid to solid"},
            {"id": "b", "text": "liquid to vapour"},
            {"id": "c", "text": "vapour to liquid"},
        ),
        correct_key="z",
    )

    with pytest.raises(InteractionWriterError, match="correct_option_id"):
        write_interaction_from_request(
            _request(
                "choice",
                "What is evaporation?",
                approved_items=[approved],
            )
        )

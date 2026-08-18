"""The structural planner's single targeted repair attempt.

The typed schema is the primary protection; this loop is the net beneath it. It
must repair once with the exact violations, never replay provider message
history, and fail clearly rather than looping.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from planning import agents
from planning.models import PathStructuralPagePlan, PathStructuralPlan
from planning.structural_validation import PathStructuralContextError

SLOTS = ["orient", "explain", "check"]


def _fixed_context(*, native: bool = True) -> dict[str, Any]:
    return {
        "concept_id": "concept-1",
        "objective": "Explain why plants need light.",
        "native_whole_lesson": native,
        # Slots carry both slot_id and a different role; only slot_id is canonical.
        "slots": [
            {"slot_id": slot, "role": "teaching", "purpose": f"{slot} purpose"}
            for slot in SLOTS
        ],
    }


def _legacy_plan(section_ids: list[str] | None = None, cards: list[dict] | None = None) -> PathStructuralPlan:
    ids = section_ids if section_ids is not None else SLOTS
    return PathStructuralPlan.model_validate(
        {
            "anchor": {"description": "basil", "source": "new"},
            "cards": [{"id": "concept-1", "title": "Light", "objective": "Explain why."}]
            if cards is None
            else cards,
            "sections": [
                {
                    "id": sid,
                    "role": sid,
                    "title": f"{sid} section",
                    "visual_required": False,
                    "transition_note": None if index == 0 else "follows",
                }
                for index, sid in enumerate(ids)
            ],
            "deviation_request": None,
            "objective_concern": None,
        }
    )


def _page_plan(section_count: int | None = None, cards: list[dict] | None = None) -> PathStructuralPagePlan:
    count = len(SLOTS) if section_count is None else section_count
    return PathStructuralPagePlan.model_validate(
        {
            "anchor": {"description": "basil", "source": "new"},
            "cards": [{"title": "Light"}] if cards is None else cards,
            "sections": [
                {
                    "title": f"{SLOTS[index]} section",
                    "transition_note": None if index == 0 else "follows",
                }
                for index in range(count)
            ],
            "deviation_request": None,
            "objective_concern": None,
        }
    )


async def test_valid_first_attempt_makes_exactly_one_call() -> None:
    stub = AsyncMock(return_value=_page_plan())
    with patch.object(agents, "_run_structured", new=stub) as run_structured:
        result = await agents.run_path_structural_planner(_fixed_context())

    assert isinstance(result, PathStructuralPagePlan)
    assert result.sections[0].title == "orient section"
    assert stub.await_count == 1
    assert run_structured.await_args_list[0].kwargs["output_type"] is PathStructuralPagePlan
    assert "repair" not in stub.await_args_list[0].kwargs["user_payload"]


async def test_repairs_once_with_previous_output_and_exact_errors() -> None:
    broken = _page_plan(section_count=2)
    stub = AsyncMock(side_effect=[broken, _page_plan()])
    with patch.object(agents, "_run_structured", new=stub):
        result = await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 2
    first, second = stub.await_args_list

    assert "repair" not in first.kwargs["user_payload"]

    repair = second.kwargs["user_payload"]["repair"]
    assert len(repair["previous_output"]["sections"]) == 2
    assert any("sections:" in err and "semantic section payloads" in err for err in repair["validation_errors"])
    assert "instruction" in repair
    assert "objective" in repair["instruction"]
    # The fixed context must still be present alongside the repair block.
    assert second.kwargs["user_payload"]["concept_id"] == "concept-1"
    # A fresh call, not a continuation: distinct trace ids, no message history.
    assert first.kwargs["trace_id"] != second.kwargs["trace_id"]
    assert "message_history" not in second.kwargs

    assert len(result.sections) == 3


async def test_second_invalid_attempt_fails_with_structured_errors() -> None:
    broken = _page_plan(section_count=2)
    stub = AsyncMock(side_effect=[broken, broken])
    with patch.object(agents, "_run_structured", new=stub):
        with pytest.raises(PathStructuralContextError) as excinfo:
            await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 2
    assert any("semantic section payloads" in err for err in excinfo.value.errors)


async def test_wrong_card_count_triggers_repair() -> None:
    """The 409 seen three times in the browser run."""
    stub = AsyncMock(side_effect=[_page_plan(cards=[]), _page_plan()])
    with patch.object(agents, "_run_structured", new=stub):
        result = await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 2
    repair = stub.await_args_list[1].kwargs["user_payload"]["repair"]
    assert any("concept card" in err for err in repair["validation_errors"])
    assert len(result.cards) == 1


async def test_schema_failure_extracts_pydantic_messages_and_sends_no_previous_output() -> None:
    """With in-library retry disabled, schema errors arrive wrapped, not bare.

    pydantic-ai raises UnexpectedModelBehavior whose __cause__ carries the
    pydantic error list. Raw model text never escapes, so previous_output is None.
    """

    class _RetryPrompt:
        content = [{"loc": ("sections", 0, "title"), "msg": "Field required"}]

    class _ToolRetryError(Exception):
        tool_retry = _RetryPrompt()

    wrapped = UnexpectedModelBehavior("Exceeded maximum output retries (0)")
    wrapped.__cause__ = _ToolRetryError()

    stub = AsyncMock(side_effect=[wrapped, _page_plan()])
    with patch.object(agents, "_run_structured", new=stub):
        result = await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 2
    repair = stub.await_args_list[1].kwargs["user_payload"]["repair"]
    assert repair["previous_output"] is None
    assert repair["validation_errors"] == ["sections.0.title: Field required"]
    assert result.sections[0].title == "orient section"


async def test_second_schema_failure_propagates_the_provider_error() -> None:
    boom = RuntimeError("deepseek 400")
    stub = AsyncMock(side_effect=[boom, boom])
    with patch.object(agents, "_run_structured", new=stub):
        with pytest.raises(RuntimeError, match="deepseek 400"):
            await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 2


async def test_expected_slots_come_from_slot_id_not_slot_role() -> None:
    """If this regressed, every section would be judged against 'teaching'."""
    good = _page_plan()
    stub = AsyncMock(return_value=good)
    with patch.object(agents, "_run_structured", new=stub):
        result = await agents.run_path_structural_planner(_fixed_context())

    assert stub.await_count == 1, "a slot_id/role mix-up would have forced a repair"
    assert [section.title for section in result.sections] == [
        "orient section",
        "explain section",
        "check section",
    ]


async def test_legacy_path_repairs_wrong_section_order() -> None:
    broken = _legacy_plan(section_ids=["explain", "orient", "check"])
    stub = AsyncMock(side_effect=[broken, _legacy_plan()])
    with patch.object(agents, "_run_structured", new=stub) as run_structured:
        result = await agents.run_path_structural_planner(_fixed_context(native=False))

    assert isinstance(result, PathStructuralPlan)
    assert run_structured.await_args_list[0].kwargs["output_type"] is PathStructuralPlan
    repair = stub.await_args_list[1].kwargs["user_payload"]["repair"]
    assert any("sections[].id" in err for err in repair["validation_errors"])
    assert result.sections[0].id == "orient"

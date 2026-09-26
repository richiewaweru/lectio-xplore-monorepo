from __future__ import annotations

from typing import Any

import pytest

from curriculum.lesson_sourcebook.models import LessonSourcebook, SourcebookEntry
from curriculum.shared_task_authoring import (
    ApprovedItemSnapshot,
    SharedTaskAuthoringError,
    author_shared_tasks,
)
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringProviderCall
from infra.authoring.models import AuthoringProviderTerminalError


class ScriptedProvider:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _plan(*, source_ref: str = "source-a", item_id: str = "item-a") -> TeachingPlan:
    block = TeachingPlanBlock(
        id="block-a",
        position=1,
        intent="practice",
        brief="Practice the idea",
        evidence="Learner demonstrates the idea.",
        task_mode="assessment",
        source_question_ids=[item_id],
        sourcebook_refs=[source_ref],
        learner_action=LearnerActionBrief(
            action="select-one",
            target="the idea",
            purpose="Check understanding",
            expected_evidence="Learner selects the correct idea.",
            difficulty="guided",
        ),
    )
    return TeachingPlan(
        contract_version=2,
        learner_title="A shared lesson",
        arc="Build and check the idea",
        starting_state=["Learner has a question"],
        target_state=["Learner can identify the idea"],
        teaching_plan_id="plan-a",
        revision=3,
        approval_status="approved",
        sections=[
            TeachingPlanSection(
                slot_id="slot-a",
                display_title="Practice",
                specific_purpose="Check the idea.",
                entry_state=["Learner has a question"],
                must_establish=["Learner can identify the idea"],
                avoid_repeating=[],
                bridge_from_previous=None,
                exit_state=["Learner can identify the idea"],
                blocks=[block],
            )
        ],
    )


def _sourcebook(plan: TeachingPlan, ref: str = "source-a") -> LessonSourcebook:
    from curriculum.teaching_plan.content_hash import teaching_plan_content_hash

    return LessonSourcebook(
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 0),
        teaching_plan_hash=teaching_plan_content_hash(plan),
        entries=[
            SourcebookEntry(
                id=ref,
                type="definition",
                purpose="Support the task.",
                content={"text": "The approved fact."},
                provenance_refs=["fact:1"],
            )
        ],
    )


def _task(*, prompt: str = "Choose the correct idea.") -> dict[str, Any]:
    return {
        "tasks": [
            {
                "prompt": prompt,
                "response": {
                    "type": "single_choice",
                    "options": [
                        {"id": "a", "text": "Correct"},
                        {"id": "b", "text": "Other"},
                    ],
                },
                "evaluation": {"type": "exact_match", "correct_option_id": "a"},
                "feedback": {"correct": "Good."},
                "expected_evidence": "Learner selects the correct idea.",
                "difficulty": "guided",
            }
        ]
    }


def _items_snapshot(plan: TeachingPlan) -> ApprovedItemSnapshot:
    from curriculum.teaching_plan.content_hash import teaching_plan_content_hash

    return ApprovedItemSnapshot(
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 0),
        teaching_plan_hash=teaching_plan_content_hash(plan),
        items={"item-a": {"id": "item-a", "prompt": "Approved question"}},
    )


@pytest.mark.asyncio
async def test_author_shared_tasks_binds_exact_lineage_and_ids() -> None:
    plan = _plan()
    provider = ScriptedProvider(_task())

    tasks = await author_shared_tasks(
        plan,
        _sourcebook(plan),
        approved_item_snapshot=_items_snapshot(plan),
        provider=provider,
    )

    assert [task.id for task in tasks] == ["task-block-a"]
    assert tasks[0].teaching_plan_id == "plan-a"
    assert tasks[0].teaching_plan_revision == 3
    assert tasks[0].sourcebook_refs == ["source-a"]
    assert tasks[0].approved_source_ids == ["item-a"]
    assert provider.calls[0].capability_id == "shared_task_authoring"
    assert provider.calls[0].is_repair is False
    instructions = provider.calls[0].prompt
    assert "Copy expected_evidence and difficulty byte-for-byte" in instructions
    assert "select-one" in instructions and "single_choice" in instructions
    assert "classify-items" in instructions and "correct_placements" in instructions
    assert "order-items and reconstruct-order" in instructions
    assert "enter-number" in instructions and "enter-text" in instructions


@pytest.mark.asyncio
async def test_malformed_count_gets_one_bounded_repair() -> None:
    plan = _plan()
    provider = ScriptedProvider({"tasks": []}, _task(prompt="Repaired task."))

    tasks = await author_shared_tasks(
        plan,
        _sourcebook(plan),
        approved_item_snapshot=_items_snapshot(plan),
        provider=provider,
    )

    assert tasks[0].prompt == "Repaired task."
    assert len(provider.calls) == 2
    assert provider.calls[1].is_repair is True


@pytest.mark.asyncio
async def test_unresolved_schema_repair_fails_closed_after_two_calls() -> None:
    plan = _plan()
    malformed = {"tasks": [{"prompt": "missing response"}]}
    provider = ScriptedProvider(malformed, malformed)

    with pytest.raises(RuntimeError, match="REPAIR_EXHAUSTED"):
        await author_shared_tasks(
            plan,
            _sourcebook(plan),
            approved_item_snapshot=_items_snapshot(plan),
            provider=provider,
        )
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_malformed_response_contract_gets_one_repair_then_fails_closed() -> None:
    plan = _plan()
    malformed = {
        "tasks": [
            {
                "prompt": "Choose the idea.",
                "response": {
                    "type": "single_choice",
                    "options": [{"id": "a", "text": "Only option"}],
                },
                "evaluation": {"type": "exact_match", "correct_option_id": "a"},
                "expected_evidence": "Learner selects the correct idea.",
                "difficulty": "guided",
            }
        ]
    }
    provider = ScriptedProvider(malformed, malformed)

    with pytest.raises(RuntimeError, match="REPAIR_EXHAUSTED"):
        await author_shared_tasks(
            plan,
            _sourcebook(plan),
            approved_item_snapshot=_items_snapshot(plan),
            provider=provider,
        )
    assert len(provider.calls) == 2
    assert provider.calls[1].is_repair is True


@pytest.mark.asyncio
async def test_arbitrary_legacy_item_map_is_not_rebound_to_plan() -> None:
    plan = _plan()
    provider = ScriptedProvider(_task())

    with pytest.raises(SharedTaskAuthoringError, match="revision-bound metadata"):
        await author_shared_tasks(
            plan,
            _sourcebook(plan),
            approved_items={"item-a": {"id": "item-a"}},
            provider=provider,
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_stale_sourcebook_and_unknown_item_are_rejected_before_dispatch() -> None:
    plan = _plan()
    provider = ScriptedProvider(_task())
    stale = _sourcebook(plan).model_copy(update={"teaching_plan_hash": "0" * 64})

    with pytest.raises(SharedTaskAuthoringError, match="LessonSourcebook"):
        await author_shared_tasks(
            plan,
            stale,
            approved_item_snapshot=_items_snapshot(plan),
            provider=provider,
        )
    assert provider.calls == []

    with pytest.raises(SharedTaskAuthoringError, match="missing source ids"):
        await author_shared_tasks(
            plan,
            _sourcebook(plan),
            approved_item_snapshot=_items_snapshot(plan).model_copy(
                update={"items": {"other-item": {"id": "other-item"}}}
            ),
            provider=provider,
        )
    assert provider.calls == []


@pytest.mark.asyncio
async def test_terminal_provider_error_is_not_semantically_repaired() -> None:
    plan = _plan()
    provider = ScriptedProvider(
        AuthoringProviderTerminalError("authentication", "API key rejected")
    )

    with pytest.raises(RuntimeError, match="PROVIDER_FAILURE"):
        await author_shared_tasks(
            plan,
            _sourcebook(plan),
            approved_item_snapshot=_items_snapshot(plan),
            provider=provider,
        )
    assert len(provider.calls) == 1

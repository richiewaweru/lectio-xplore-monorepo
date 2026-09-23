"""Targeted tests for shared task writer batch contract and repair."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from curriculum.agents import _SharedTaskDraftEnvelope, run_shared_task_writer
from curriculum.shared_tasks.models import SharedTaskDraft
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)


def _make_block(
    block_id: str,
    *,
    action: str | None = "select-one",
    task_mode: str = "formative",
    source_question_ids: list[str] | None = None,
) -> TeachingPlanBlock:
    learner_action = (
        LearnerActionBrief(
            action=action,  # type: ignore[arg-type]
            target=f"target for {block_id}",
            purpose=f"purpose for {block_id}",
            expected_evidence=f"evidence for {block_id}",
            difficulty="guided",
        )
        if action is not None
        else None
    )
    return TeachingPlanBlock(
        id=block_id,
        position=1,
        intent="test intent",
        brief="test brief",
        evidence="test evidence",
        task_mode=task_mode,  # type: ignore[arg-type]
        source_question_ids=source_question_ids or (["q-1"] if task_mode == "assessment" else []),
        learner_action=learner_action,
    )


def _make_plan(blocks: list[TeachingPlanBlock]) -> TeachingPlan:
    return TeachingPlan(
        arc="test arc",
        teaching_plan_id="plan-test-1",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="slot-1",
                specific_purpose="section purpose",
                blocks=blocks,
            )
        ],
    )


def _make_draft_task(label: str) -> SharedTaskDraft:
    return SharedTaskDraft(
        prompt=f"Task prompt for {label}",
        response={"type": "single_choice", "options": [{"id": "a", "text": "Option A"}]},
        evaluation={"type": "exact_match", "correct_option_id": "a"},
        expected_evidence=f"Evidence for {label}",
        difficulty="guided",
    )


@pytest.mark.asyncio
async def test_1_response_block_produces_1_task():
    """Requirement 1: 1 response block -> 1 task."""
    plan = _make_plan([_make_block("b1", action="select-one")])
    envelope = _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")])

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        tasks = await run_shared_task_writer(plan)

    assert len(tasks) == 1
    assert tasks[0].teaching_block_id == "b1"
    assert tasks[0].id == "task-b1"
    assert mock_llm.call_count == 1
    call_payload = mock_llm.call_args.kwargs["user_payload"]
    assert call_payload["expected_task_count"] == 1
    assert len(call_payload["response_blocks"]) == 1


@pytest.mark.asyncio
async def test_3_response_blocks_produce_3_tasks():
    """Requirement 2: 3 response blocks -> 3 tasks."""
    plan = _make_plan([
        _make_block("b1", action="select-one"),
        _make_block("b2", action="match-pairs"),
        _make_block("b3", action="enter-text"),
    ])
    envelope = _SharedTaskDraftEnvelope(
        tasks=[_make_draft_task("b1"), _make_draft_task("b2"), _make_draft_task("b3")]
    )

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        tasks = await run_shared_task_writer(plan)

    assert len(tasks) == 3
    assert [t.teaching_block_id for t in tasks] == ["b1", "b2", "b3"]
    assert mock_llm.call_count == 1
    call_payload = mock_llm.call_args.kwargs["user_payload"]
    assert call_payload["expected_task_count"] == 3


@pytest.mark.asyncio
async def test_passive_or_null_action_produces_0_tasks():
    """Requirement 3: passive/null action -> 0 tasks."""
    plan = _make_plan([
        _make_block("b1", action="read-explanation"),
        _make_block("b2", action="compare-without-response"),
        _make_block("b3", action=None),
    ])

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        tasks = await run_shared_task_writer(plan)

    assert len(tasks) == 0
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_mixed_passive_and_response_blocks():
    """Requirement 4: mixed passive/response -> tasks only for response blocks."""
    plan = _make_plan([
        _make_block("b1", action="read-explanation"),
        _make_block("b2", action="select-one"),
        _make_block("b3", action="compare-without-response"),
        _make_block("b4", action="enter-number"),
    ])
    envelope = _SharedTaskDraftEnvelope(
        tasks=[_make_draft_task("b2"), _make_draft_task("b4")]
    )

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        tasks = await run_shared_task_writer(plan)

    assert len(tasks) == 2
    assert [t.teaching_block_id for t in tasks] == ["b2", "b4"]
    call_payload = mock_llm.call_args.kwargs["user_payload"]
    assert call_payload["expected_task_count"] == 2
    assert [r["block_id"] for r in call_payload["response_blocks"]] == ["b2", "b4"]


@pytest.mark.asyncio
async def test_too_few_tasks_bounded_repair_and_failure():
    """Requirement 5: too few -> bounded repair attempt; hard failure if unresolved."""
    plan = _make_plan([
        _make_block("b1", action="select-one"),
        _make_block("b2", action="select-many"),
    ])

    # Case A: repair succeeds
    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")]),  # too few: 1 instead of 2
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1"), _make_draft_task("b2")]),  # repaired
        ]
        tasks = await run_shared_task_writer(plan)
        assert len(tasks) == 2
        assert mock_llm.call_count == 2
        repair_payload = mock_llm.call_args_list[1].kwargs["user_payload"]
        assert "repair_context" in repair_payload

    # Case B: repair fails -> hard failure
    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")]),
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")]),
        ]
        with pytest.raises(ValueError, match="shared task writer must return exactly one task per response-bearing block"):
            await run_shared_task_writer(plan)
        assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_too_many_tasks_bounded_repair_and_failure():
    """Requirement 6: too many -> bounded repair attempt; hard failure if unresolved."""
    plan = _make_plan([_make_block("b1", action="select-one")])

    # Case A: repair succeeds
    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1"), _make_draft_task("b1-extra")]),  # 2 instead of 1
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")]),  # repaired
        ]
        tasks = await run_shared_task_writer(plan)
        assert len(tasks) == 1
        assert mock_llm.call_count == 2

    # Case B: repair fails -> hard failure
    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1"), _make_draft_task("b1-extra")]),
            _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1"), _make_draft_task("b1-extra")]),
        ]
        with pytest.raises(ValueError, match="shared task writer must return exactly one task per response-bearing block"):
            await run_shared_task_writer(plan)
        assert mock_llm.call_count == 2


@pytest.mark.asyncio
async def test_assessment_without_approved_source_fails():
    """Requirement 7: assessment without approved source still fails."""
    block = _make_block("b1", action="select-one", task_mode="formative")
    plan = _make_plan([block])
    # Now set assessment mode with no sources on the block to test defense-in-depth in run_shared_task_writer
    object.__setattr__(block, "task_mode", "assessment")
    object.__setattr__(block, "source_question_ids", [])

    envelope = _SharedTaskDraftEnvelope(tasks=[_make_draft_task("b1")])
    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        with pytest.raises(ValueError, match="assessment block 'b1' has no approved source"):
            await run_shared_task_writer(plan)


@pytest.mark.asyncio
async def test_ordering_binds_deterministically():
    """Requirement 8: ordering binds deterministically."""
    plan = _make_plan([
        _make_block("block-alpha", action="select-one"),
        _make_block("block-beta", action="enter-text"),
        _make_block("block-gamma", action="match-pairs"),
    ])
    drafts = [
        _make_draft_task("alpha-task"),
        _make_draft_task("beta-task"),
        _make_draft_task("gamma-task"),
    ]
    envelope = _SharedTaskDraftEnvelope(tasks=drafts)

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        tasks = await run_shared_task_writer(plan)

    assert [t.teaching_block_id for t in tasks] == ["block-alpha", "block-beta", "block-gamma"]
    assert tasks[0].prompt == "Task prompt for alpha-task"
    assert tasks[1].prompt == "Task prompt for beta-task"
    assert tasks[2].prompt == "Task prompt for gamma-task"


@pytest.mark.asyncio
async def test_identity_remains_code_owned():
    """Requirement 9: identity remains code-owned."""
    plan = _make_plan([_make_block("block-xyz", action="select-one")])
    envelope = _SharedTaskDraftEnvelope(tasks=[_make_draft_task("xyz")])

    with patch("curriculum.agents._run_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = envelope
        tasks = await run_shared_task_writer(plan)

    task = tasks[0]
    assert task.id == "task-block-xyz"
    assert task.teaching_block_id == "block-xyz"
    assert task.teaching_plan_id == "plan-test-1"
    assert task.teaching_plan_revision == 1
    assert len(task.teaching_plan_hash) > 0
    assert task.mode == "formative"
    assert task.action == "select-one"

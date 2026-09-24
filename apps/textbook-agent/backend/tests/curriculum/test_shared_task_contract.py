from __future__ import annotations

import pytest

from curriculum.lesson_sourcebook.models import LessonSourcebook, TeachingContentBinding
from curriculum.shared_tasks.models import (
    ACTION_RESPONSE_TYPES,
    PASSIVE_ACTION_MEANINGS,
    SharedTaskSpec,
)
from curriculum.shared_tasks.service import learner_action_meaning, teaching_plan_hash
from curriculum.shared_tasks.validation import (
    assert_task_response_contract,
    finalize_shared_tasks,
    validate_shared_tasks,
    validate_task_response_contract,
)
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    LearnerActionId,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)


def _action_payload(action: LearnerActionId) -> tuple[dict, dict]:
    response_payloads = {
        "select-one": (
            {"type": "single_choice", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            {"type": "exact_match", "correct_option_id": "a"},
        ),
        "select-many": (
            {"type": "multiple_choice", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
            {"type": "choice_keys", "correct_option_ids": ["a"]},
        ),
        "complete-missing-values": (
            {"type": "missing_values", "values": ["42"]},
            {"type": "accepted_answers", "accepted_answers": ["42"]},
        ),
        "classify-items": (
            {"type": "classification", "items": ["a"], "categories": ["group"], "correct_placements": {"a": "group"}},
            {"type": "mapping", "correct_placements": {"a": "group"}},
        ),
        "match-pairs": (
            {"type": "matching", "pairs": [{"left": "a", "right": "b"}]},
            {"type": "mapping", "pairs": [{"left": "a", "right": "b"}]},
        ),
        "order-items": (
            {"type": "ordered_items", "items": ["a", "b"], "correct_order": ["b", "a"]},
            {"type": "ordered_match", "correct_order": ["b", "a"]},
        ),
        "reconstruct-order": (
            {"type": "ordered_items", "items": ["a", "b"], "correct_order": ["b", "a"]},
            {"type": "ordered_match", "correct_order": ["b", "a"]},
        ),
        "enter-number": (
            {"type": "number"},
            {"type": "numeric", "value": 42},
        ),
        "enter-text": (
            {"type": "text"},
            {"type": "teacher_review", "review_guidance": "Check the learner's reasoning."},
        ),
    }
    return response_payloads[action]


def _plan(actions: list[LearnerActionId]) -> TeachingPlan:
    blocks = [
        TeachingPlanBlock(
            id=f"b-{index}",
            position=index,
            intent="practice",
            brief="Show what you understand.",
            evidence="Evidence is available.",
            learner_action=LearnerActionBrief(
                action=action,
                target="the target",
                purpose="practice the target",
                expected_evidence="the expected evidence",
                difficulty="guided",
            ),
        )
        for index, action in enumerate(actions)
    ]
    return TeachingPlan(
        arc="Practice a target",
        teaching_plan_id="plan-contract",
        revision=3,
        sections=[TeachingPlanSection(slot_id="practice", blocks=blocks)],
    )


def _task(plan: TeachingPlan, block: TeachingPlanBlock, *, response: dict | None = None, evaluation: dict | None = None) -> SharedTaskSpec:
    default_response, default_evaluation = _action_payload(block.learner_action.action)
    return SharedTaskSpec(
        id=f"task-{block.id}",
        teaching_plan_id=plan.teaching_plan_id or "teaching-plan",
        teaching_plan_revision=plan.revision or 1,
        teaching_plan_hash=teaching_plan_hash(plan),
        teaching_block_id=block.id,
        mode="formative",
        action=block.learner_action.action,
        purpose=block.learner_action.purpose,
        prompt="Show what you understand.",
        difficulty=block.learner_action.difficulty,
        sourcebook_refs=list(block.sourcebook_refs),
        expected_evidence=block.learner_action.expected_evidence,
        response=response or default_response,
        evaluation=evaluation or default_evaluation,
    )


def test_every_learner_action_has_response_or_explicit_passive_meaning() -> None:
    actions = set(LearnerActionId.__args__)

    assert set(ACTION_RESPONSE_TYPES) | set(PASSIVE_ACTION_MEANINGS) == actions
    assert not (set(ACTION_RESPONSE_TYPES) & set(PASSIVE_ACTION_MEANINGS))
    for action, response_type in ACTION_RESPONSE_TYPES.items():
        assert learner_action_meaning(action) == ("response", response_type)
    for action, meaning in PASSIVE_ACTION_MEANINGS.items():
        assert learner_action_meaning(action) == ("passive", meaning)


def test_each_response_action_accepts_a_complete_path_neutral_task() -> None:
    plan = _plan(list(ACTION_RESPONSE_TYPES))
    tasks = [_task(plan, block) for block in plan.sections[0].blocks]

    assert all(validate_task_response_contract(task) == [] for task in tasks)
    assert finalize_shared_tasks(plan, tasks) == tasks


def test_shared_task_outer_serialization_fields_remain_stable() -> None:
    plan = _plan(["select-one"])
    task = _task(plan, plan.sections[0].blocks[0])

    assert set(task.model_dump(mode="json")) == {
        "id",
        "teaching_plan_id",
        "teaching_plan_revision",
        "teaching_plan_hash",
        "teaching_block_id",
        "mode",
        "action",
        "purpose",
        "prompt",
        "difficulty",
        "sourcebook_refs",
        "expected_evidence",
        "response",
        "evaluation",
        "feedback",
        "approved_source_ids",
    }


def test_response_type_must_match_learner_action() -> None:
    task = SharedTaskSpec(
        id="task-b1",
        teaching_block_id="b1",
        mode="formative",
        action="select-one",
        purpose="choose",
        prompt="Choose one.",
        difficulty="guided",
        expected_evidence="one choice",
        response={"type": "text"},
        evaluation={"type": "rubric", "criteria": ["one choice"]},
    )

    with pytest.raises(ValueError, match="requires response type 'single_choice'"):
        assert_task_response_contract(task)


def test_legacy_response_alias_remains_readable_but_cannot_be_finalized() -> None:
    plan = _plan(["select-one"])
    task = _task(plan, plan.sections[0].blocks[0], response={"type": "select-one"})

    assert task.response_type == "select-one"
    with pytest.raises(ValueError, match="requires response type 'single_choice'"):
        assert_task_response_contract(task)


def test_choice_options_and_evaluation_must_form_a_closed_contract() -> None:
    plan = _plan(["select-one"])
    task = _task(
        plan,
        plan.sections[0].blocks[0],
        response={"type": "single_choice", "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]},
        evaluation={"type": "exact_match", "correct_option_id": "missing"},
    )

    errors = validate_shared_tasks(plan, [task])

    assert any("unknown option ids" in error for error in errors)


def test_task_must_preserve_exact_block_action_evidence_and_mode() -> None:
    plan = _plan(["enter-text"])
    block = plan.sections[0].blocks[0]
    task = _task(plan, block).model_copy(
        update={
            "purpose": "different purpose",
            "expected_evidence": "different evidence",
            "difficulty": "independent",
            "mode": "assessment",
            "approved_source_ids": ["unbound-source"],
        }
    )

    errors = validate_shared_tasks(plan, [task])

    assert any("wrong purpose" in error for error in errors)
    assert any("wrong expected_evidence" in error for error in errors)
    assert any("wrong difficulty" in error for error in errors)
    assert any("wrong mode" in error for error in errors)
    assert any("wrong approved_source_ids" in error for error in errors)


def test_sourcebook_and_content_binding_must_match_the_approved_plan_identity() -> None:
    plan = _plan(["enter-number"])
    block = plan.sections[0].blocks[0]
    task = _task(plan, block)
    sourcebook = LessonSourcebook(
        teaching_plan_id=plan.teaching_plan_id or "",
        teaching_plan_revision=plan.revision or 1,
        teaching_plan_hash="stale-hash",
        entries=[],
    )
    binding = TeachingContentBinding(
        teaching_plan_id=plan.teaching_plan_id or "",
        teaching_plan_revision=plan.revision or 1,
        teaching_plan_hash="stale-hash",
        teaching_block_id=block.id,
        sourcebook_refs=[],
        shared_task_id=task.id,
    )

    errors = validate_shared_tasks(plan, [task], sourcebook=sourcebook, bindings=[binding])

    assert "sourcebook has the wrong teaching_plan_hash" in errors
    assert any("binding 'b-0' has the wrong teaching_plan_hash" in error for error in errors)


def test_passive_actions_have_meaning_and_never_get_shared_tasks() -> None:
    plan = _plan(["compare-without-response", "read-explanation"])

    assert all(learner_action_meaning(block.learner_action.action)[0] == "passive" for block in plan.sections[0].blocks)
    assert finalize_shared_tasks(plan, []) == []

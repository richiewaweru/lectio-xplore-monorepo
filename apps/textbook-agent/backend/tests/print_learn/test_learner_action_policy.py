from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.planning.test_prompt_no_object_leak import _packet as _prompt_packet

from print.generation.catalogue_projections import project_teaching_guidance
from print.generation.whole_lesson.prompt_render import render_teaching_prompt
from print.generation.whole_lesson.teaching_agent import (
    _missing_check_practice_action_errors,
    _task_source_contract_errors,
    _unknown_learner_action_errors,
)
from print.generation.whole_lesson.teaching_plan import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)


def _block(**kwargs: object) -> TeachingPlanBlock:
    payload = {
        "id": "b1",
        "position": 0,
        "intent": "check-understanding",
        "brief": "Ask the learner to choose the cause.",
        "evidence": "Learner selects the correct cause",
        "source_question_ids": [],
        "learner_action": None,
    }
    payload.update(kwargs)
    return TeachingPlanBlock(**payload)  # type: ignore[arg-type]


def _plan(*blocks: TeachingPlanBlock) -> TeachingPlan:
    return TeachingPlan(
        arc="Closeout B",
        teaching_plan_id="tp-b",
        revision=1,
        sections=[TeachingPlanSection(slot_id="check", blocks=list(blocks))],
    )


def test_teaching_prompt_includes_closed_learner_action_policy() -> None:
    guidance = project_teaching_guidance(
        permitted_intent_ids={"orient", "explain", "check-understanding"}
    )
    rendered = render_teaching_prompt(_prompt_packet(), guidance)
    assert "## LEARNER ACTION POLICY" in rendered
    assert "closed task contract" in rendered
    assert "Never construct an evidence ref" in rendered
    assert "required_assessment_slots" in rendered
    assert "allowed_actions" in rendered
    assert "describe-in-own-words" in rendered
    assert "enter-text" in rendered


def test_check_practice_without_action_legacy_diagnostic_still_flags() -> None:
    plan = _plan(_block())
    errors = _missing_check_practice_action_errors(plan)
    assert errors
    assert all("TEACHING_MISSING_LEARNER_ACTION" in err for err in errors)


def test_passive_check_block_may_omit_action() -> None:
    plan = _plan(
        _block(
            brief="Learners observe the demonstration.",
            evidence="Learners observe the worked example without a response.",
        )
    )
    assert _missing_check_practice_action_errors(plan) == []


def test_check_with_declared_bound_action_passes_shared_task_contract() -> None:
    plan = _plan(
        _block(
            source_question_ids=["mc-1"],
            learner_action=LearnerActionBrief(
                action="select-one",
                target="cause of the result",
                purpose="Check understanding",
                expected_evidence="Learner chooses the taught cause",
                difficulty="guided",
            ),
        )
    )
    assert _unknown_learner_action_errors(plan) == []
    assert _task_source_contract_errors(plan) == []


def test_unbound_response_action_is_rejected_before_fork() -> None:
    plan = _plan(
        _block(
            learner_action=LearnerActionBrief(
                action="enter-text",
                target="explanation",
                purpose="articulate reasoning",
                expected_evidence="short explanation",
                difficulty="guided",
            )
        )
    )
    errors = _task_source_contract_errors(plan)
    assert len(errors) == 1
    assert "TEACHING_UNBOUND_RESPONSE_ACTION" in errors[0]


def test_bound_source_without_action_is_rejected_before_fork() -> None:
    plan = _plan(_block(source_question_ids=["mc-1"]))
    errors = _task_source_contract_errors(plan)
    assert len(errors) == 1
    assert "TEACHING_SOURCE_MISSING_ACTION" in errors[0]


def test_unknown_learner_action_is_rejected_by_structured_schema() -> None:
    with pytest.raises(ValidationError):
        LearnerActionBrief(
            action="invented-action",  # type: ignore[arg-type]
            target="something",
            purpose="test",
            expected_evidence="none",
            difficulty="guided",
        )


def test_describe_in_own_words_is_rejected_by_structured_schema() -> None:
    with pytest.raises(ValidationError):
        LearnerActionBrief(
            action="describe-in-own-words",  # type: ignore[arg-type]
            target="the ratio idea",
            purpose="surface current language",
            expected_evidence="Learner describes the idea in own words",
            difficulty="guided",
        )


def test_alias_and_passive_actions_are_known() -> None:
    alias_plan = _plan(
        _block(
            source_question_ids=["open-1"],
            learner_action=LearnerActionBrief(
                action="reconstruct-order",
                target="stages",
                purpose="rebuild sequence",
                expected_evidence="correct order",
                difficulty="guided",
            ),
        )
    )
    passive_plan = _plan(
        _block(
            learner_action=LearnerActionBrief(
                action="read-explanation",
                target="worked example",
                purpose="follow silently",
                expected_evidence="learner follows without response",
                difficulty="guided",
            )
        )
    )
    assert _unknown_learner_action_errors(alias_plan) == []
    assert _unknown_learner_action_errors(passive_plan) == []
    assert _task_source_contract_errors(alias_plan) == []
    assert _task_source_contract_errors(passive_plan) == []

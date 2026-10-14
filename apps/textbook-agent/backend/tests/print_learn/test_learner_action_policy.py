from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.planning.test_prompt_no_object_leak import _packet as _prompt_packet

from print.generation.catalogue_projections import project_teaching_guidance
from application.unit_lesson.staged_teaching_planner import render_staged_prompt

from application.unit_lesson.teaching_planner import (
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


def render_teaching_prompt(packet, guidance, **_kwargs):
    """The teaching prompt a section call runs under (the only teaching prompt)."""
    return render_staged_prompt(packet, guidance, kind="section")


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


def test_unbound_response_action_is_legal_when_declared_formative() -> None:
    plan = _plan(
        _block(
            task_mode="formative",
            learner_action=LearnerActionBrief(
                action="enter-text",
                target="explanation",
                purpose="articulate reasoning",
                expected_evidence="short explanation",
                difficulty="guided",
            ),
        )
    )
    assert _task_source_contract_errors(plan) == []


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


def _role_action(action: str = "select-one", **kwargs: object) -> LearnerActionBrief:
    return LearnerActionBrief(
        action=action,  # type: ignore[arg-type]
        target="the idea",
        purpose="elicit a guess",
        expected_evidence="learner commits to a guess",
        difficulty="guided",
        **kwargs,  # type: ignore[arg-type]
    )


def test_learner_action_role_is_omitted_when_none_and_hash_is_unchanged() -> None:
    from curriculum.teaching_plan.content_hash import teaching_plan_content_hash

    plain = _plan(_block(learner_action=_role_action(), task_mode="formative"))
    assert "role" not in plain.sections[0].blocks[0].learner_action.model_dump(mode="json")
    assert "role" not in plain.model_dump_json()
    with_role = _plan(
        _block(learner_action=_role_action(role="practice"), task_mode="formative")
    )
    assert teaching_plan_content_hash(plain) != teaching_plan_content_hash(with_role)
    assert teaching_plan_content_hash(plain) == teaching_plan_content_hash(
        TeachingPlan.model_validate_json(plain.model_dump_json())
    )


def test_learner_action_role_round_trips_and_rejects_unknown() -> None:
    brief = _role_action(role="predict")
    assert LearnerActionBrief.model_validate(brief.model_dump(mode="json")).role == "predict"
    with pytest.raises(ValidationError):
        _role_action(role="quiz")


def test_role_validation_rejects_predict_on_assessment_and_role_on_passive() -> None:
    from application.unit_lesson.teaching_planner import _learner_role_errors

    bad_predict = _plan(
        _block(learner_action=_role_action(role="predict"), task_mode="assessment", source_question_ids=["q1"])
    )
    errors = _learner_role_errors(bad_predict)
    assert len(errors) == 1 and "TEACHING_LEARNER_ROLE_INVALID" in errors[0]

    passive = _plan(
        _block(learner_action=_role_action("read-explanation", role="practice"))
    )
    errors = _learner_role_errors(passive)
    assert len(errors) == 1 and "must be omitted" in errors[0]

    ok = _plan(
        _block(learner_action=_role_action(role="check"), task_mode="assessment", source_question_ids=["q2"]),
        _block(id="b2", learner_action=_role_action(role="predict"), task_mode="formative"),
        _block(id="b3", learner_action=_role_action()),
    )
    assert _learner_role_errors(ok) == []

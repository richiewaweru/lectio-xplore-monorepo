from __future__ import annotations

from print.generation.whole_lesson.prompt_render import render_teaching_prompt
from print.generation.whole_lesson.teaching_agent import _missing_check_practice_action_errors
from print.generation.whole_lesson.teaching_plan import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from tests.planning.test_prompt_no_object_leak import _packet as _prompt_packet
from print.generation.catalogue_projections import project_teaching_guidance


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


def test_teaching_prompt_includes_learner_action_policy() -> None:
    guidance = project_teaching_guidance(
        permitted_intent_ids={"orient", "explain", "check-understanding"}
    )
    rendered = render_teaching_prompt(_prompt_packet(), guidance)
    assert "## LEARNER ACTION POLICY" in rendered
    assert "A learner action is not limited to tests" in rendered
    assert "Never name Learn interaction types" in rendered


def test_check_practice_without_action_is_pathological() -> None:
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


def test_explain_block_may_omit_action() -> None:
    plan = _plan(
        _block(
            intent="explain",
            brief="Explain mechanical advantage.",
            evidence="The cause is named.",
        )
    )
    assert _missing_check_practice_action_errors(plan) == []


def test_check_with_declared_action_passes() -> None:
    plan = _plan(
        _block(
            learner_action=LearnerActionBrief(
                action="select-one",
                target="cause of the result",
                purpose="Check understanding",
                expected_evidence="Learner chooses the taught cause",
                difficulty="guided",
            )
        )
    )
    assert _missing_check_practice_action_errors(plan) == []

import pytest

from curriculum.flow_validation import validate_flow_choice
from curriculum.lesson_review import (
    build_coherence_report,
    compare_path_task_semantics,
    invalidate_stale_smart_artifacts,
)
from curriculum.lesson_sourcebook import LessonSourcebook, SourcebookEntry, build_content_bindings
from curriculum.models import FlowChoice
from curriculum.shared_tasks import build_shared_task_registry, validate_shared_tasks
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan


def _plan(*, task_mode: str = "formative", source_ids: list[str] | None = None) -> TeachingPlan:
    return TeachingPlan.model_validate(
        {
            "arc": "Use canonical slope points",
            "teaching_plan_id": "plan-1",
            "revision": 2,
            "preparation_hash": "hash-2",
            "sections": [
                {
                    "slot_id": "model",
                    "blocks": [
                        {
                            "id": "model-b1",
                            "position": 0,
                            "intent": "practice",
                            "brief": "Find the slope from (1,4) and (3,12).",
                            "evidence": "The learner gives slope 4.",
                            "task_mode": task_mode,
                            "source_question_ids": source_ids or [],
                            "learner_action": {
                                "action": "enter-number",
                                "target": "slope",
                                "purpose": "practice slope",
                                "expected_evidence": "4",
                                "difficulty": "guided",
                            },
                        }
                    ],
                }
            ],
        }
    )


def test_flow_choice_is_closed_and_keeps_final_check() -> None:
    choice = FlowChoice(
        recommended_slots=["orient", "model", "check"],
        selected_slots=["orient", "model", "check"],
    )
    assert not validate_flow_choice(
        choice,
        recommended_slots=["orient", "model", "check"],
        legal_slots={slot: {} for slot in ["orient", "model", "check"]},
        max_slots=6,
    )
    choice = choice.model_copy(update={"selected_slots": ["check", "model"]})
    assert any(
        "last" in error
        for error in validate_flow_choice(
        choice,
        recommended_slots=["orient", "model", "check"],
        legal_slots={slot: {} for slot in ["orient", "model", "check"]},
        max_slots=6,
        )
    )


def test_formative_task_needs_no_approved_source_and_binds_once() -> None:
    plan = _plan()
    tasks = build_shared_task_registry(plan)
    assert validate_shared_tasks(plan, tasks) == []
    sourcebook = LessonSourcebook(
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash=teaching_plan_content_hash(plan),
        entries=[
            SourcebookEntry(
                id="slope",
                type="quantitative_example",
                purpose="points",
                content={"points": [[1, 4], [3, 12]]},
                provenance_refs=["canonical"],
            )
        ],
    )
    assert build_content_bindings(plan, sourcebook, tasks=tasks)[0].shared_task_id == tasks[0].id


def test_incomplete_choice_contract_is_not_reusable() -> None:
    plan = _plan()
    task = build_shared_task_registry(plan)[0].model_copy(
        update={"response": {"type": "select-one"}}
    )
    errors = validate_shared_tasks(plan, [task])
    assert any("at least two options" in error for error in errors)


def test_assessment_task_requires_source() -> None:
    with pytest.raises(ValueError, match="assessment tasks require"):
        _plan(task_mode="assessment")


def test_coherence_report_detects_slope_drift_and_parity() -> None:
    plan = _plan()
    task = build_shared_task_registry(plan)[0]
    report = build_coherence_report(
        path="learn",
        plan=plan,
        tasks=[task],
        output={"document": {"nodes": [{"id": "n1", "text": "(1,4), (3,12), slope 5"}]}},
    )
    assert any(issue.code == "SLOPE_DRIFT" for issue in report.issues)
    altered = task.model_copy(update={"prompt": "different"})
    assert compare_path_task_semantics([task], [altered])[0].code == "TASK_PARITY_DRIFT"


def test_stale_smart_artifacts_are_invalidated() -> None:
    state = {
        "other": 1,
        "smart_lesson": {
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "old",
        },
    }
    updated = invalidate_stale_smart_artifacts(
        state, teaching_plan_id="plan-1", teaching_plan_revision=2, teaching_plan_hash="new"
    )
    assert updated == {"other": 1}

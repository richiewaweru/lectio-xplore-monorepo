from __future__ import annotations

from learning.models import LearningJob, PackLearningPlan
from learning.pack_planner import plan_pack


def _job(job_type: str = "reteach") -> LearningJob:
    return LearningJob(
        job=job_type,
        subject="Mathematics",
        topic="Slope",
        grade_level="grade_7",
        grade_band="middle_school",
        objective="Students can calculate slope.",
        class_signals=[],
        assumptions=[],
        warnings=[],
        recommended_depth="standard",
        inferred_supports=[],
        inferred_class_profile={},
    )


def _plan() -> PackLearningPlan:
    return PackLearningPlan(
        objective="Students can calculate slope.",
        success_criteria=["Identifies rise and run"],
        prerequisite_skills=[],
        likely_misconceptions=["Confuses rise over run"],
        shared_vocabulary=["slope", "rise", "run"],
        shared_examples=["A ramp rising 3 over 4"],
    )


def test_plan_pack_respects_max_resources() -> None:
    pack = plan_pack(_job("reteach"), _plan(), max_resources=2)
    assert len(pack.resources) == 2


def test_plan_pack_uses_pack_spec_order() -> None:
    pack = plan_pack(_job("reteach"), _plan())
    assert [resource.resource_type for resource in pack.resources] == [
        "quick_explainer",
        "worksheet",
        "exit_ticket",
    ]

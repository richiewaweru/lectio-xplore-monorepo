from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUTPUT_DIR = BACKEND_ROOT / "outputs"
DATABASE_PATH = OUTPUT_DIR / "v2-shadow-real-gate.sqlite"
RECORDS_PATH = OUTPUT_DIR / "v2-shadow-real-records.json"


def _configure_isolated_runtime() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing shadow gate database: {DATABASE_PATH}"
        )
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DATABASE_PATH.as_posix()}"
    os.environ["APP_ENV"] = "development"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
    os.environ["V2_SKELETON_SHADOW_ENABLED"] = "true"
    os.environ["LECTIO_CONTRACTS_DIR"] = str(BACKEND_ROOT / "contracts")
    load_dotenv(REPO_ROOT / ".env", override=False)


def _lesson_cases() -> list[dict[str, object]]:
    return [
        {
            "generation_id": "v2-shadow-real-001",
            "grade_level": "Grade 4",
            "subject": "Biology",
            "topic": "Photosynthesis",
            "subtopics": ["light"],
            "outcome": "Explain why light is required for photosynthesis.",
            "struggle": "Learners think plants obtain food directly from soil.",
            "prior_knowledge": "Plants need water and light to grow.",
            "lesson_mode": "first_exposure",
        },
        {
            "generation_id": "v2-shadow-real-002",
            "grade_level": "Grade 8",
            "subject": "Mathematics",
            "topic": "Percentage change",
            "subtopics": ["percentage increase", "percentage decrease"],
            "outcome": "Calculate percentage change from an original value to a new value.",
            "struggle": "Learners divide by the new value instead of the original value.",
            "prior_knowledge": "Find a percentage of a quantity and subtract decimal values.",
            "lesson_mode": "first_exposure",
        },
        {
            "generation_id": "v2-shadow-real-003",
            "grade_level": "Grade 11",
            "subject": "Geography",
            "topic": "Renewable energy siting",
            "subtopics": ["environmental impact", "grid access", "community needs"],
            "outcome": "Assess which of two proposed wind-farm sites is more suitable and defend the choice against stated criteria.",
            "struggle": "Learners state preferences without applying consistent criteria.",
            "prior_knowledge": "Interpret maps and distinguish renewable from non-renewable energy.",
            "lesson_mode": "first_exposure",
        },
    ]


async def main() -> None:
    _configure_isolated_runtime()

    from sqlalchemy import select

    from contracts.lectio import get_template_contract
    from core.database.models import Base, GenerationModel, SkeletonShadowRecordModel, UserModel
    from core.database.session import async_session_factory, engine
    from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
    from v3_blueprint.planning.retry import run_stage1_with_retry

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    teacher_id = "v2-shadow-gate-teacher"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=teacher_id,
                email="v2-shadow-gate@example.invalid",
                name="V2 Shadow Gate",
            )
        )
        for case in _lesson_cases():
            session.add(
                GenerationModel(
                    id=str(case["generation_id"]),
                    user_id=teacher_id,
                    subject=str(case["subject"]),
                    status="planning",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="default",
                )
            )
        await session.commit()

    resource_spec = {
        "resource_type": "lesson",
        "spec": get_template_contract("guided-concept-path") or {},
    }
    for case in _lesson_cases():
        form = V3InputForm(
            grade_level=str(case["grade_level"]),
            subject=str(case["subject"]),
            duration_minutes=45,
            resource_type="lesson",
            topic=str(case["topic"]),
            subtopics=list(case["subtopics"]),
            prior_knowledge=str(case["prior_knowledge"]),
            outcome=str(case["outcome"]),
            struggle=str(case["struggle"]),
            learner_level="on_grade",
            reading_level="on_grade",
            language_support="none",
            prior_knowledge_level="some_background",
            free_text="V2 Phase 4 real shadow gate.",
        )
        signals = V3SignalSummary(
            topic=str(case["topic"]),
            subtopic=None,
            prior_knowledge=[str(case["prior_knowledge"])],
            learner_needs=[],
            teacher_goal=str(case["outcome"]),
            inferred_lesson_mode=str(case["lesson_mode"]),
            lesson_mode_confidence="high",
        )
        plan = await run_stage1_with_retry(
            signals,
            form,
            resource_spec,
            generation_id=str(case["generation_id"]),
            trace_id=str(case["generation_id"]),
        )
        print(
            f"REAL_GENERATION_COMPLETE generation_id={case['generation_id']} "
            f"sections={len(plan.sections)} cards={len(plan.cards)}",
            flush=True,
        )

    async with async_session_factory() as session:
        result = await session.execute(
            select(SkeletonShadowRecordModel).order_by(
                SkeletonShadowRecordModel.generation_id
            )
        )
        records = [
            {
                "generation_id": row.generation_id,
                "subject": row.subject,
                "grade": row.grade,
                "objective": row.objective,
                "current_roles": row.current_roles,
                "classifier_type": row.classifier_type,
                "classifier_confidence": row.classifier_confidence,
                "classifier_success_test": row.classifier_success_test,
                "classifier_note": row.classifier_note,
                "skeleton_id": row.skeleton_id,
                "skeleton_version": row.skeleton_version,
                "expanded_slots": row.expanded_slots,
                "toggles_applied": row.toggles_applied,
                "expansion_warnings": row.expansion_warnings,
                "structural_match_score": row.structural_match_score,
                "reviewer_preference": row.reviewer_preference,
                "wrong_classification": row.wrong_classification,
                "deviation_required": row.deviation_required,
                "severity": row.severity,
                "notes": row.notes,
            }
            for row in result.scalars()
        ]

    if len(records) != 3:
        raise RuntimeError(f"Expected 3 real shadow records, found {len(records)}")
    RECORDS_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(json.dumps(records, indent=2), flush=True)
    print(f"REAL_SHADOW_RECORDS_PATH={RECORDS_PATH}", flush=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

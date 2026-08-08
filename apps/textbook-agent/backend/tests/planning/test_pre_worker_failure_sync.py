"""Pre-worker native failure must sync generation status, chunked stage, error, and events."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.v3_studio.router import _run_chunked_stage2_pipeline
from planning.whole_lesson.native_status import project_native_status
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
)


def _sample_plan() -> StructuralPlan:
    return StructuralPlan(
        document_contract_version=2,
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="By the end students can explain why plants need light.",
            structure_rationale="Concrete-first structure for novice learners.",
        ),
        anchor=AnchorSpec(
            example="two plants on a windowsill",
            reuse_scope="intro then explain then check",
        ),
        prior_knowledge=["plants grow"],
        sections=[
            SectionPlan(
                id="orient",
                title="Orient",
                role="orient",
                visual_required=False,
                transition_note=None,
                components=[ComponentSlot(slug="hook-hero", purpose="surface anchor")],
            )
        ],
        question_plan=[
            QPlanItem(
                question_id="q1",
                section_id="orient",
                temperature="warm",
                diagram_required=False,
            )
        ],
        answer_key_style="brief_explanations",
    )


async def _seed_native_pre_worker() -> tuple[str, str]:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    plan = _sample_plan()
    signals = {
        "topic": "Plants",
        "subtopic": "Light",
        "prior_knowledge": ["plants grow"],
        "learner_needs": [],
        "teacher_goal": "Explain light",
        "inferred_lesson_mode": "first_exposure",
        "lesson_mode_confidence": "high",
    }
    form = {
        "grade_level": "Grade 4",
        "subject": "Science",
        "duration_minutes": 45,
        "resource_type": "lesson",
        "topic": "plants and light",
        "subtopics": ["windowsill plants"],
        "prior_knowledge": "plants grow",
        "outcome": "Students can explain why plants need light.",
        "struggle": "",
        "learner_level": "on_grade",
        "reading_level": "on_grade",
        "language_support": "none",
        "prior_knowledge_level": "some_background",
        "free_text": "",
    }
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="pending",
                chunked_state_json={
                    "stage": "stage2_running",
                    "native_whole_lesson": True,
                    "skip_item_generation": True,
                    "context": {
                        "native_whole_lesson": True,
                        "signals": signals,
                        "form": form,
                        "resource_spec": {
                            "resource_type": "lesson",
                            "depth": "standard",
                            "spec": {},
                            "rendered": "x",
                        },
                    },
                    "structural_plan": plan.model_dump(mode="json"),
                    "variant_spec": {
                        "label": "everyone",
                        "group_description": "whole class",
                        "voice": {
                            "register_name": "balanced",
                            "tone": "encouraging",
                            "notation": None,
                        },
                    },
                },
            )
        )
        await session.commit()
    return gid, user_id


@pytest.mark.asyncio
async def test_teaching_planner_failure_syncs_all_status_sources() -> None:
    gid, user_id = await _seed_native_pre_worker()

    with (
        patch(
            "planning.whole_lesson.service.run_and_persist_teaching_plan",
            new=AsyncMock(side_effect=RuntimeError("teaching planner boom")),
        ),
        patch(
            "generation.v3_studio.router._chunked_emit_event",
            new=AsyncMock(),
        ),
    ):
        await _run_chunked_stage2_pipeline(generation_id=gid, user_id=user_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "failed_terminal"
        chunked = dict(generation.chunked_state_json or {})
        assert chunked.get("stage") == "failed_terminal"
        assert chunked.get("stage") != "stage2_error"
        page = dict(chunked.get("page_document_v2") or {})
        execution = dict(page.get("execution") or {})
        last_error = dict(execution.get("last_error") or {})
        assert last_error.get("stage") == "planning_teaching"
        assert "teaching planner boom" in str(last_error.get("message") or "")
        assert "retryable" in last_error
        events = list(page.get("events") or [])
        assert any(
            str(event.get("type") or "") == "pre_worker_failure"
            and str(event.get("status") or "") == "failed_terminal"
            for event in events
        )
        projected = project_native_status(
            gid,
            chunked,
            generation.document_json,
            generation_status=generation.status,
        )
        assert projected is not None
        assert projected["stage"] == "failed_terminal"
        assert projected.get("error_detail")
        assert "teaching planner boom" in str(projected["error_detail"].get("message") or "")

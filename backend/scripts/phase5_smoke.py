from __future__ import annotations

# ruff: noqa: E402

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

_SMOKE_DB_PATH = Path(tempfile.gettempdir()) / "textbook-agent-phase5-smoke.db"
if _SMOKE_DB_PATH.exists():
    _SMOKE_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_SMOKE_DB_PATH.as_posix()}"
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app import create_app
from core.auth.middleware import get_current_user
from core.database.migrations import upgrade_database
from core.database.models import GenerationModel, LLMCallModel, StudentProfileModel, UserModel
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler
from core.entities.user import User
from core.events import LLMCallStartedEvent, LLMCallSucceededEvent, event_bus
from generation import routes as generation_routes
from pipeline.api import PipelineDocument, PipelineResult
from pipeline.events import CompleteEvent, SectionReadyEvent, SectionStartedEvent
from planning.llm_config import (
    PLANNING_SECTION_COMPOSER_CALLER,
)
from planning.models import CompositionResult, PlanningSectionPlan

USER_ID = "phase5-smoke-user"
EMAIL = "phase5-smoke@example.com"
SMOKE_USER = User(
    id=USER_ID,
    email=EMAIL,
    name="Phase 5 Smoke",
    picture_url=None,
    has_profile=True,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)


async def seed_db() -> None:
    async with async_session_factory() as session:
        await session.execute(delete(LLMCallModel).where(LLMCallModel.user_id == USER_ID))
        await session.execute(delete(GenerationModel).where(GenerationModel.user_id == USER_ID))
        await session.execute(
            delete(StudentProfileModel).where(StudentProfileModel.user_id == USER_ID)
        )
        await session.execute(delete(UserModel).where(UserModel.id == USER_ID))
        session.add(UserModel(id=USER_ID, email=EMAIL, name="Phase 5 Smoke"))
        session.add(
            StudentProfileModel(
                id="phase5-smoke-profile",
                user_id=USER_ID,
                age=16,
                education_level="high_school",
                interests=json.dumps(["math"]),
                learning_style="visual",
                preferred_notation="plain",
                prior_knowledge="basic algebra",
                goals="understand limits",
                preferred_depth="standard",
                learner_description="Curious and steady",
            )
        )
        await session.commit()


async def cleanup_db() -> None:
    async with async_session_factory() as session:
        await session.execute(delete(LLMCallModel).where(LLMCallModel.user_id == USER_ID))
        await session.execute(delete(GenerationModel).where(GenerationModel.user_id == USER_ID))
        await session.execute(
            delete(StudentProfileModel).where(StudentProfileModel.user_id == USER_ID)
        )
        await session.execute(delete(UserModel).where(UserModel.id == USER_ID))
        await session.commit()


async def override_current_user():
    return SMOKE_USER


def _section_content(subject: str, grade_band: str) -> dict:
    return {
        "section_id": "s-01",
        "template_id": "guided-concept-path",
        "header": {
            "title": "Limits first look",
            "subject": subject,
            "grade_band": grade_band,
        },
        "explanation": {
            "body": "Limits describe the value a function approaches.",
            "emphasis": ["approaches", "nearby values"],
        },
    }


async def fake_run_pipeline(command, on_event=None):
    generation_id = command.generation_id
    section = _section_content(command.subject, command.grade_band)

    await on_event(
        SectionStartedEvent(
            generation_id=generation_id,
            section_id="s-01",
            title="Limits first look",
            position=1,
        )
    )
    await on_event(
        LLMCallStartedEvent(
            trace_id=generation_id,
            generation_id=generation_id,
            node="curriculum_planner",
            slot="standard",
            family="anthropic",
            model_name="claude-sonnet-4-6",
            attempt=1,
        )
    )
    await on_event(
        LLMCallSucceededEvent(
            trace_id=generation_id,
            generation_id=generation_id,
            node="curriculum_planner",
            slot="standard",
            family="anthropic",
            model_name="claude-sonnet-4-6",
            attempt=1,
            latency_ms=1234.0,
            tokens_in=111,
            tokens_out=222,
            cost_usd=0.003,
        )
    )
    await on_event(
        SectionReadyEvent(
            generation_id=generation_id,
            section_id="s-01",
            section=section,
            completed_sections=1,
            total_sections=1,
        )
    )
    await on_event(
        CompleteEvent(
            generation_id=generation_id,
            final_status="completed",
            quality_passed=True,
            completed_sections=1,
            total_sections=1,
        )
    )

    return PipelineResult(
        document=PipelineDocument(
            generation_id=generation_id,
            subject=command.subject,
            context=command.context,
            mode=command.mode,
            template_id=command.template_id,
            preset_id=command.preset_id,
            status="completed",
            section_manifest=[{"section_id": "s-01", "title": "Limits first look", "position": 1}],
            sections=[section],
            failed_sections=[],
            qc_reports=[],
            quality_passed=True,
        ),
        completed_nodes=["curriculum_planner"],
        generation_time_seconds=0.01,
    )


async def fake_planning_run_llm(
    *,
    trace_id=None,
    caller=None,
    slot=None,
    **kwargs,
):
    _ = kwargs
    event_bus.publish(
        trace_id,
        LLMCallStartedEvent(
            trace_id=trace_id,
            caller=caller,
            slot=slot or "standard",
            family="anthropic",
            model_name="claude-sonnet-4-6",
            attempt=1,
        ),
    )
    event_bus.publish(
        trace_id,
        LLMCallSucceededEvent(
            trace_id=trace_id,
            caller=caller,
            slot=slot or "standard",
            family="anthropic",
            model_name="claude-sonnet-4-6",
            attempt=1,
            latency_ms=456.0,
            tokens_in=50,
            tokens_out=75,
            cost_usd=0.001,
        ),
    )

    if caller == PLANNING_SECTION_COMPOSER_CALLER:
        return SimpleNamespace(
            output=CompositionResult(
                lesson_rationale="Refined for smoke test.",
                warning=None,
                sections=[
                    PlanningSectionPlan(
                        id="section-1",
                        order=1,
                        role="intro",
                        title="Limits first look",
                        objective="Introduce the idea of approaching a value.",
                        focus_note="Start with the idea of nearby values on a graph.",
                        selected_components=["explanation-block"],
                        rationale="Open with a graph-based explanation.",
                    )
                ],
            )
        )

    return SimpleNamespace(output=None)


async def fake_export_generation_pdf(**kwargs):
    generation = kwargs["generation"]
    pdf_path = Path(tempfile.gettempdir()) / f"{generation.id}-smoke.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
    return SimpleNamespace(
        pdf_path=pdf_path,
        filename=f"{generation.id}.pdf",
        file_size_bytes=pdf_path.stat().st_size,
        page_count=1,
        generation_time_ms=50,
        cleanup_paths=[pdf_path],
    )


async def main() -> None:
    await asyncio.to_thread(upgrade_database)
    await seed_db()
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    token = get_jwt_handler().create_access_token(USER_ID, EMAIL)

    try:
        with patch(
            "pipeline.adapter.run_pipeline_streaming",
            side_effect=fake_run_pipeline,
        ), patch(
            "planning.routes.run_llm",
            side_effect=fake_planning_run_llm,
        ), patch(
            "planning.routes.build_model",
            return_value=object(),
        ), patch.object(
            generation_routes,
            "export_generation_pdf",
            side_effect=fake_export_generation_pdf,
        ):
            async with app.router.lifespan_context(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as client:
                    brief_payload = {
                        "subject": "Mathematics",
                        "topic": "Limits",
                        "subtopics": ["Understanding limits"],
                        "grade_level": "grade_11",
                        "grade_band": "adult",
                        "class_profile": {
                            "reading_level": "on_grade",
                            "language_support": "none",
                            "confidence": "mixed",
                            "prior_knowledge": "some_background",
                            "pacing": "normal",
                            "learning_preferences": ["visual"],
                        },
                        "learner_context": "High school calculus students",
                        "intended_outcome": "understand",
                        "resource_type": "worksheet",
                        "supports": ["visuals"],
                        "depth": "standard",
                        "teacher_notes": "Keep it concise.",
                    }

                    plan_response = await client.post("/api/v1/brief/plan", json=brief_payload)
                    plan_payload = plan_response.json()

                    commit_response = await client.post(
                        "/api/v1/brief/commit",
                        json=plan_payload,
                    )
                    commit_payload = commit_response.json()
                    generation_id = commit_payload.get("generation_id", "")

                    await asyncio.sleep(0.2)

                    detail_response = await client.get(f"/api/v1/generations/{generation_id}")
                    document_response = await client.get(commit_payload["document_url"])
                    events_response = await client.get(
                        commit_payload["events_url"] + f"?token={token}"
                    )
                    report_response = await client.get(commit_payload["report_url"])
                    export_response = await client.post(
                        f"/api/v1/generations/{generation_id}/export/pdf",
                        json={
                            "school_name": "Smoke Test High",
                            "teacher_name": "Phase 5 Smoke",
                            "include_toc": True,
                            "include_answers": False,
                        },
                    )
                    usage_response = await client.get("/api/v1/telemetry/llm-usage")

        print(
            {
                "plan_status": plan_response.status_code,
                "plan_has_sections": len(plan_payload.get("sections", [])) > 0,
                "commit_status": commit_response.status_code,
                "accepted_section_count": commit_payload.get("section_count"),
                "detail_status": detail_response.status_code,
                "detail_generation_status": detail_response.json().get("status"),
                "document_status": document_response.status_code,
                "document_has_sections": len(document_response.json().get("sections", [])) > 0,
                "events_status": events_response.status_code,
                "events_has_complete": "event: complete" in events_response.text,
                "report_status": report_response.status_code,
                "report_has_completed": report_response.json().get("status") == "completed",
                "pdf_status": export_response.status_code,
                "pdf_content_type": export_response.headers.get("content-type"),
                "usage_status": usage_response.status_code,
                "usage_total_calls": usage_response.json().get("total_calls"),
            }
        )
    finally:
        app.dependency_overrides.clear()
        await cleanup_db()


if __name__ == "__main__":
    asyncio.run(main())

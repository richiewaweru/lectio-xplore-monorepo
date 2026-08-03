from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import delete, select

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.v3_studio.dtos import V3InputForm
from generation.v3_studio.generation_writer import V3GenerationWriter
from generation.v3_studio.router import _persist_regenerated_visual
from generation.v3_studio.planning_artifact import (
    SCHEMA_VERSION,
    build_planning_artifact,
    parse_planning_artifact,
)
from v3_blueprint.models import ProductionBlueprint
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state


async def _cleanup_generation(generation_id: str) -> None:
    async with async_session_factory() as session:
        await session.execute(delete(GenerationModel).where(GenerationModel.id == generation_id))
        await session.commit()


async def _load_generation(generation_id: str) -> GenerationModel:
    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one_or_none()
        assert model is not None
        return model


async def test_v3_generation_writer_persists_flat_document_json_and_report_snapshot() -> None:
    generation_id = "v3-writer-draft"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject="Science",
            context="Plants",
            template_id="guided-concept-path",
            section_count=3,
            planned_visuals=2,
            planned_questions=4,
            component_count=9,
        )
        await writer.write_draft(
            generation_id,
            {
                "booklet_status": "draft_ready",
                "pack": {
                    "generation_id": generation_id,
                    "blueprint_id": "bp-1",
                    "template_id": "guided-concept-path",
                    "subject": "Science",
                    "status": "draft_ready",
                    "sections": [{"section_id": "intro", "header": {"title": "Intro"}}],
                    "warnings": [],
                    "section_diagnostics": [],
                    "booklet_issues": [],
                },
            },
        )
        model = await _load_generation(generation_id)
        assert model.status == "running"
        assert model.mode == "v3"
        assert isinstance(model.document_json, dict)
        assert model.document_json["kind"] == "v3_booklet_pack"
        assert model.document_json["status"] == "draft_ready"
        assert isinstance(model.report_json, dict)
        assert model.report_json["pipeline_version"] == "v3"
        assert model.report_json["report_schema"] == "v3_generation_report_v1"
        assert model.report_json["booklet_status"] == "draft_ready"
        assert model.report_json["summary"]["planned_sections"] == 3
        assert model.report_json["summary"]["ready_sections"] == 1
        assert model.report_json["summary"]["missing_sections"] == 2
        assert model.report_json["summary"]["planned_visuals"] == 2
        assert model.report_json["summary"]["planned_questions"] == 4
        assert model.report_json["summary"]["assembled_sections"] == 1
    finally:
        await _cleanup_generation(generation_id)


async def test_manual_document_write_bumps_progress_version() -> None:
    generation_id = "v3-writer-manual-version"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject="Science",
            context="Plants",
            template_id="guided-concept-path",
            section_count=1,
        )
        document = {
            "kind": "v3_booklet_pack",
            "sections": [{"section_id": "intro"}],
            "progress": {
                "stage": "completed",
                "sections": {"intro": "ready"},
                "updated_at": "2026-07-17T09:00:00+00:00",
            },
        }

        await _persist_regenerated_visual(
            generation_id=generation_id,
            user_id="writer-user",
            document_json=document,
        )

        model = await _load_generation(generation_id)
        assert model.document_json["progress"]["updated_at"] != "2026-07-17T09:00:00+00:00"
        assert model.document_json["progress"]["stage"] == "completed"
    finally:
        await _cleanup_generation(generation_id)


async def test_consecutive_snapshot_writes_produce_distinct_versions() -> None:
    generation_id = "v3-writer-snapshot-versions"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject="Science",
            context="Plants",
            template_id="guided-concept-path",
            section_count=1,
        )
        payload = {
            "pack": {
                "generation_id": generation_id,
                "status": "streaming_preview",
                "sections": [{"section_id": "intro"}],
                "progress": {"stage": "writing", "sections": {"intro": "ready"}},
            }
        }

        await writer.write_draft(generation_id, payload)
        first = (await _load_generation(generation_id)).document_json["progress"]["updated_at"]
        await writer.write_draft(generation_id, payload)
        second = (await _load_generation(generation_id)).document_json["progress"]["updated_at"]

        assert first != second
    finally:
        await _cleanup_generation(generation_id)


async def test_v3_generation_writer_handles_resource_finalised_and_pdf_status() -> None:
    generation_id = "v3-writer-final"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject="Math",
            context="Triangles",
            template_id="guided-concept-path",
            section_count=2,
            planned_visuals=1,
            planned_questions=2,
            component_count=4,
        )
        await writer.write_draft(
            generation_id,
            {
                "booklet_status": "draft_needs_review",
                "pack": {
                    "generation_id": generation_id,
                    "blueprint_id": "bp-2",
                    "template_id": "guided-concept-path",
                    "subject": "Math",
                    "status": "draft_needs_review",
                    "sections": [
                        {
                            "section_id": "s1",
                            "diagram": {"image_url": "https://cdn.example/one.png"},
                            "practice": {"items": [{"prompt": "1"}]},
                        }
                    ],
                    "warnings": [],
                    "section_diagnostics": [],
                    "booklet_issues": [],
                },
            },
        )
        await writer.write_resource_finalised(
            generation_id,
            {
                "status": "failed",
                "booklet_status": "draft_needs_review",
            },
        )
        await writer.write_pdf_status(
            generation_id,
            status="failed",
            error="Playwright timeout",
            debug={"page_url": "https://example/print"},
        )
        model = await _load_generation(generation_id)
        assert model.status == "partial"
        assert model.quality_passed is False
        assert model.completed_at is not None
        assert isinstance(model.report_json, dict)
        assert model.report_json["process_status"] == "failed_finalisation"
        assert model.report_json["summary"]["assembled_sections"] == 1
        assert model.report_json["summary"]["ready_sections"] == 1
        assert model.report_json["summary"]["missing_sections"] == 1
        assert model.report_json["summary"]["delivered_visuals"] == 1
        assert model.report_json["summary"]["delivered_questions"] == 1
        assert model.report_json["pdf"]["last_export_status"] == "failed"
        assert model.report_json["pdf"]["last_error"] == "Playwright timeout"
        assert model.report_json["pdf"]["last_debug"] == {"page_url": "https://example/print"}
    finally:
        await _cleanup_generation(generation_id)


def _example_bp(name: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / name
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


async def test_v3_generation_writer_write_planning_artifact_persists_json_and_report_summary() -> None:
    generation_id = "v3-writer-planning-artifact"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    blueprint = _example_bp("amara_compound_area.json")
    form = V3InputForm(
        grade_level="Grade 8",
        subject="Mathematics",
        duration_minutes=50,
        resource_type="lesson",
        topic="Compound area",
        outcome="Students can find the area of compound shapes.",
    )
    artifact = build_planning_artifact(
        generation_id=generation_id,
        blueprint_id="bp-planning",
        template_id="guided-concept-path",
        blueprint=blueprint,
        form=form,
    )
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject=blueprint.metadata.subject,
            context=blueprint.metadata.title,
            template_id="guided-concept-path",
            section_count=len(blueprint.sections),
        )
        await writer.write_planning_artifact(
            generation_id=generation_id,
            user_id="writer-user",
            artifact=artifact,
        )
        model = await _load_generation(generation_id)
        assert model.planning_spec_json is not None
        parsed = parse_planning_artifact(model.planning_spec_json)
        assert parsed is not None
        assert parsed["schema_version"] == SCHEMA_VERSION
        assert parsed["blueprint_id"] == "bp-planning"
        assert isinstance(parsed["blueprint"], dict)
        assert parsed["form"]["topic"] == "Compound area"
        assert isinstance(model.report_json, dict)
        planning = model.report_json.get("planning")
        assert isinstance(planning, dict)
        assert planning["blueprint_id"] == "bp-planning"
        assert planning["has_full_planning_artifact"] is True
        assert "blueprint" not in planning
        summary = model.report_json["summary"]
        assert summary["planned_components"] == sum(
            len(section.components) for section in blueprint.sections
        )
        assert summary["planned_questions"] == len(blueprint.question_plan)
        assert summary["planned_visuals"] == sum(
            1 for section in blueprint.sections if section.visual_required
        )

        read_back = await writer.read_planning_artifact(generation_id, "writer-user")
        assert read_back is not None
        assert read_back["blueprint_id"] == "bp-planning"

        wrong_user = await writer.read_planning_artifact(generation_id, "other-user")
        assert wrong_user is None
    finally:
        await _cleanup_generation(generation_id)


async def test_v3_generation_writer_persists_full_coherence_report() -> None:
    generation_id = "v3-writer-coherence"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await writer.upsert_started(
            generation_id=generation_id,
            user_id="writer-user",
            subject="Science",
            context="Cells",
            template_id="guided-concept-path",
            section_count=1,
        )
        coherence = {
            "status": "failed",
            "blocking_count": 3,
            "major_count": 1,
            "minor_count": 0,
            "issues": [{"issue_id": "i-1", "severity": "blocking"}],
        }
        await writer.write_coherence_result(generation_id, coherence)
        await writer.write_generation_complete(
            generation_id,
            {
                "booklet_status": "final_ready",
                "coherence_review": {
                    "status": "failed",
                    "blocking_count": 3,
                    "major_count": 1,
                    "minor_count": 0,
                }
            },
        )
        model = await _load_generation(generation_id)
        assert isinstance(model.report_json, dict)
        assert model.quality_passed is True
        assert model.report_json["coherence"]["issues"][0]["issue_id"] == "i-1"
        assert model.report_json["summary"]["blocking_issues"] == 3
        assert model.report_json["summary"]["major_issues"] == 1
        assert model.report_json["summary"]["minor_issues"] == 0
    finally:
        await _cleanup_generation(generation_id)


def _skeleton_document(generation_id: str) -> dict:
    return {
        "kind": "v3_booklet_pack",
        "generation_id": generation_id,
        "template_id": "guided-concept-path",
        "status": "streaming_preview",
        "sections": [
            {
                "section_id": "intro",
                "template_id": "guided-concept-path",
                "title": "Intro",
                "components": [{"component_id": "explanation-card", "intent": "Explain"}],
                "header": {"title": "Intro"},
            }
        ],
        "progress": {"stage": "writing", "sections": {"intro": "pending"}},
    }


async def _seed_snapshot(writer: V3GenerationWriter, generation_id: str) -> None:
    await writer.upsert_started(
        generation_id=generation_id,
        user_id="writer-user",
        subject="Science",
        context="Plants",
        template_id="guided-concept-path",
        section_count=1,
    )
    async with async_session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.id == generation_id)
        )
        model = result.scalar_one()
        model.document_json = _skeleton_document(generation_id)
        await session.commit()


async def test_merge_stream_event_component_ready_populates_section_body() -> None:
    generation_id = "v3-writer-merge-component"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        await writer.merge_stream_event(
            generation_id,
            "component_ready",
            {
                "generation_id": generation_id,
                "component_id": "explanation-card",
                "section_id": "intro",
                "position": 0,
                "section_field": "explanation",
                "data": {"body": "Photosynthesis turns light into food."},
            },
        )
        model = await _load_generation(generation_id)
        section = model.document_json["sections"][0]
        assert section["explanation"] == {"body": "Photosynthesis turns light into food."}
        progress = model.document_json["progress"]
        assert progress["stage"] == "writing"
        assert progress["sections"]["intro"] == "writing"
    finally:
        await _cleanup_generation(generation_id)


async def test_merge_stream_event_question_and_visual_ready() -> None:
    generation_id = "v3-writer-merge-qv"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        await writer.merge_stream_event(
            generation_id,
            "question_ready",
            {
                "generation_id": generation_id,
                "question_id": "q-1",
                "section_id": "intro",
                "difficulty": "medium",
                "data": {"question": "What does a leaf do?", "hints": ["Think light"]},
            },
        )
        await writer.merge_stream_event(
            generation_id,
            "visual_ready",
            {
                "generation_id": generation_id,
                "visual_id": "vis-1",
                "attaches_to": "intro",
                "frame_index": None,
                "image_url": "https://cdn.example/leaf.png",
                "status": "completed",
            },
        )
        model = await _load_generation(generation_id)
        section = model.document_json["sections"][0]
        problems = section["practice"]["problems"]
        assert problems[0]["_qid"] == "q-1"
        assert problems[0]["question"] == "What does a leaf do?"
        assert section["diagram"]["image_url"] == "https://cdn.example/leaf.png"
    finally:
        await _cleanup_generation(generation_id)


async def test_merge_stream_event_ignores_unknown_section_and_failed_visual() -> None:
    generation_id = "v3-writer-merge-noop"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        await writer.merge_stream_event(
            generation_id,
            "component_ready",
            {"section_id": "missing", "section_field": "explanation", "data": {"body": "x"}},
        )
        await writer.merge_stream_event(
            generation_id,
            "visual_ready",
            {"attaches_to": "intro", "image_url": "https://cdn.example/bad.png", "status": "failed"},
        )
        model = await _load_generation(generation_id)
        section = model.document_json["sections"][0]
        assert "explanation" not in section
        assert "diagram" not in section
    finally:
        await _cleanup_generation(generation_id)


async def test_fail_stale_running_marks_terminal_failure() -> None:
    generation_id = "v3-writer-stale-running"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        swept = await writer.fail_stale_running()
        assert swept >= 1
        model = await _load_generation(generation_id)
        assert model.status == "failed"
        assert model.error_type == "server_restart"
        assert model.document_json["progress"]["stage"] == "failed"
        assert model.document_json["progress"]["sections"]["intro"] == "failed"
        assert (await load_chunked_state(generation_id))["stage"] == "stage2_error"
    finally:
        await _cleanup_generation(generation_id)


async def test_fail_stale_running_reconciles_fully_written_generation() -> None:
    generation_id = "v3-writer-stale-complete"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        async with async_session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            assert model is not None
            model.document_json = {
                "kind": "v3_booklet_pack",
                "generation_id": generation_id,
                "blueprint_id": "bp-complete",
                "status": "draft_ready",
                "sections": [{"section_id": "intro", "header": {"title": "Intro"}}],
                "progress": {"stage": "writing", "sections": {"intro": "ready"}},
            }
            await session.commit()
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage2_running",
                "blueprint_id": "bp-complete",
                "structural_plan": {"sections": [{"id": "intro"}]},
            },
        )

        await writer.fail_stale_running()

        model = await _load_generation(generation_id)
        assert model.status == "failed_finalisation"
        assert model.error_type is None
        assert model.document_json["status"] == "draft_ready"
        assert model.document_json["progress"]["stage"] == "completed"
        state = await load_chunked_state(generation_id)
        assert state["stage"] == "complete"
        assert state["execution_started"] is False
    finally:
        await _cleanup_generation(generation_id)


async def test_fail_stale_running_marks_partial_generation_resumable() -> None:
    generation_id = "v3-writer-stale-partial"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        async with async_session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            assert model is not None
            model.document_json = {
                "kind": "v3_booklet_pack",
                "generation_id": generation_id,
                "blueprint_id": "bp-partial",
                "status": "streaming_preview",
                "sections": [{"section_id": "intro", "header": {"title": "Intro"}}],
                "progress": {
                    "stage": "writing",
                    "sections": {"intro": "ready", "model": "writing"},
                },
            }
            await session.commit()
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage2_running",
                "blueprint_id": "bp-partial",
                "structural_plan": {"sections": [{"id": "intro"}, {"id": "model"}]},
            },
        )

        await writer.fail_stale_running()

        model = await _load_generation(generation_id)
        assert model.status == "failed"
        assert model.error_code == "v3_interrupted_by_restart"
        assert model.document_json["progress"]["stage"] == "interrupted"
        state = await load_chunked_state(generation_id)
        assert state["stage"] == "assembly_blocked"
        assert state["failed_sections"] == ["model"]
    finally:
        await _cleanup_generation(generation_id)


async def test_claim_resume_attempt_terminalizes_after_cap() -> None:
    generation_id = "v3-writer-resume-exhausted"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)
        async with async_session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            assert model is not None
            report = dict(model.report_json)
            report["resume_attempts"] = 3
            model.report_json = report
            await session.commit()
        await persist_chunked_state(
            generation_id,
            {"stage": "stage2_error", "execution_started": False},
        )

        claimed = await writer.claim_resume_attempt(generation_id)

        assert claimed is False
        model = await _load_generation(generation_id)
        assert model.status == "failed"
        assert model.error_code == "v3_resume_exhausted"
        assert model.document_json["progress"]["stage"] == "failed"
        state = await load_chunked_state(generation_id)
        assert state["stage"] == "failed"
        assert state["execution_started"] is False
    finally:
        await _cleanup_generation(generation_id)


async def test_claim_resume_attempt_increments_counter() -> None:
    generation_id = "v3-writer-resume-claimed"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)

        claimed = await writer.claim_resume_attempt(generation_id)

        assert claimed is True
        model = await _load_generation(generation_id)
        assert model.status == "running"
        assert model.report_json["resume_attempts"] == 1
    finally:
        await _cleanup_generation(generation_id)


async def test_default_report_includes_empty_prompt_hashes() -> None:
    generation_id = "v3-writer-prompt-hashes-default"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)

        model = await _load_generation(generation_id)
        assert model.report_json["prompt_hashes"] == {}
    finally:
        await _cleanup_generation(generation_id)


async def test_record_prompt_hashes_merges_into_report_json() -> None:
    generation_id = "v3-writer-prompt-hashes-record"
    await _cleanup_generation(generation_id)
    writer = V3GenerationWriter(async_session_factory)
    try:
        await _seed_snapshot(writer, generation_id)

        from core.prompts.loader import hash_prompt

        section_writer_hash = hash_prompt("section writer prompt text")
        await writer.record_prompt_hashes(
            generation_id, {"section-writer": section_writer_hash}
        )
        model = await _load_generation(generation_id)
        assert model.report_json["prompt_hashes"] == {"section-writer": section_writer_hash}

        question_writer_hash = hash_prompt("question writer prompt text")
        await writer.record_prompt_hashes(
            generation_id, {"question-writer": question_writer_hash}
        )
        model = await _load_generation(generation_id)
        assert model.report_json["prompt_hashes"] == {
            "section-writer": section_writer_hash,
            "question-writer": question_writer_hash,
        }
    finally:
        await _cleanup_generation(generation_id)

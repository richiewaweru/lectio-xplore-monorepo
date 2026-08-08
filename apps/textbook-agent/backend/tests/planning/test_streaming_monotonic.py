"""Monotonic streaming snapshots: stale partial cannot replace newer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects.document_assembly import (
    canonical_document_sha256,
    reload_document,
)
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    empty_page_document_state,
)
from planning.whole_lesson.states import execution_key
from tests.planning.contract_fixtures import teaching_and_form


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-stream",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light", "plant"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain"]),
        ],
        limits=LessonLimits(),
    )


def _section_doc(section_ids: list[str]) -> dict[str, Any]:
    sections = []
    for sid in section_ids:
        sections.append(
            {
                "id": sid,
                "title": sid.title(),
                "blocks": [
                    {
                        "id": f"{sid}-b1",
                        "object": "prose",
                        "intent": "orient" if sid == "orient" else "explain",
                        "position": 0,
                        "content": {"paragraphs": [f"Body {sid}"]},
                        "layout": {"placement": "main"},
                    }
                ],
            }
        )
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-stream",
        "title": "Stream",
        "language": "en",
        "metadata": {
            "catalogue_version": "1.1.0",
            "resource_type": "lesson",
            "streaming_partial": True,
            "native_whole_lesson": True,
        },
        "sections": sections,
    }


async def _seed() -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    teaching, plan = teaching_and_form(
        sections=[
            ("orient", [("orient-b1", "orient", "prose")]),
            ("explain", [("explain-b1", "explain", "prose")]),
        ]
    )
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
    state["block_execution"] = {
        execution_key("orient", "orient-b1"): {
            "status": "ready",
            "block_id": "orient-b1",
            "section_id": "orient",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "orient",
            "content": {"paragraphs": ["Body orient"]},
            "attempts": 1,
        },
        execution_key("explain", "explain-b1"): {
            "status": "ready",
            "block_id": "explain-b1",
            "section_id": "explain",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "explain",
            "content": {"paragraphs": ["Body explain"]},
            "attempts": 1,
        },
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
                status="writing_sections",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "writing_sections",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


@pytest.mark.asyncio
async def test_stale_one_section_snapshot_cannot_replace_newer_two() -> None:
    gid = await _seed()
    newer = _section_doc(["orient", "explain"])
    newer_sha = canonical_document_sha256(newer)
    stale = _section_doc(["orient"])
    stale_sha = canonical_document_sha256(stale)

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        first = await repo.persist_streaming_snapshot(
            newer,
            document_sha256=newer_sha,
            section_ids=["orient", "explain"],
        )
        assert first["changed"] is True
        rev_after_newer = int(first["document_revision"])

        rejected = await repo.persist_streaming_snapshot(
            stale,
            document_sha256=stale_sha,
            section_ids=["orient"],
        )
        assert rejected["changed"] is False
        assert rejected.get("rejected") == "non_monotonic_section_set"
        assert int(rejected["document_revision"]) == rev_after_newer

        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        doc = reload_document(generation.document_json or {})
        section_ids = [str(s.get("id")) for s in (doc.get("sections") or [])]
        assert section_ids == ["orient", "explain"]

        state = await repo.load_page_generation_state()
        assert int(state["document_revision"]) == rev_after_newer
        assert set(state["execution"]["streaming_section_ids"]) == {
            "orient",
            "explain",
        }
        assert state["execution"]["streaming_document_sha256"] == newer_sha

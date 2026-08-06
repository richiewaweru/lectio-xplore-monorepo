"""Patch 02.1A: lease-fenced document candidate + finalization."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects.document_assembly import (
    canonical_document_sha256,
    persist_document_json,
)
from planning.whole_lesson.executor import AssemblyError, assemble_from_db
from planning.whole_lesson.form_plan import FormPlan, FormPlanBlock, FormPlanSection
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import (
    DocumentFenceError,
    PageDocumentRepository,
    empty_page_document_state,
)
from planning.whole_lesson.states import ExecutionLease, LeaseLostError, execution_key


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-fence",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light", "plant"]),
        anchor=AnchorRecord(id="anchor-1", description="Two plants."),
        slots=[SlotRecord(slot_id="orient", typical_intents=["orient"])],
        limits=LessonLimits(),
    )


def _form_plan() -> FormPlan:
    return FormPlan(
        sections=[
            FormPlanSection(
                slot_id="orient",
                blocks=[
                    FormPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="orient",
                        brief="Open with the two plants.",
                        object="prose",
                    )
                ],
            )
        ]
    )


def _tiny_document() -> dict[str, Any]:
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-fence",
        "title": "Fence",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "orient",
                "title": "Orient",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "object": "prose",
                        "intent": "orient",
                        "position": 0,
                        "content": {"paragraphs": ["Hello"]},
                        "layout": {"placement": "main"},
                    }
                ],
            }
        ],
    }


async def _seed(*, status: str = "assembling") -> str:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    plan = _form_plan()
    state = empty_page_document_state()
    state["lesson_packet"] = _packet().model_dump(mode="json")
    state["teaching_plan"] = {"arc": "test", "sections": []}
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    state["block_execution"] = {
        execution_key("orient", "orient-b1"): {
            "status": "ready",
            "block_id": "orient-b1",
            "section_id": "orient",
            "variant_id": "everyone",
            "object": "prose",
            "intent": "orient",
            "content": {"paragraphs": ["Hello"]},
            "attempts": 1,
        }
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
                status=status,
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": status,
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()
    return gid


async def _claim(gid: str, worker_id: str = "fence-w") -> ExecutionLease:
    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id=worker_id
        )
        assert lease is not None
        return lease


@pytest.mark.asyncio
async def test_stale_worker_candidate_write_rejected() -> None:
    gid = await _seed()
    lease = await _claim(gid, worker_id="owner")
    doc = _tiny_document()
    sha = canonical_document_sha256(doc)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(LeaseLostError):
            await repo.persist_document_candidate(
                doc,
                document_sha256=sha,
                worker_id="stale-worker",
                lease_token=lease.lease_token,
            )


@pytest.mark.asyncio
async def test_wrong_token_candidate_write_rejected() -> None:
    gid = await _seed()
    lease = await _claim(gid, worker_id="owner")
    doc = _tiny_document()
    sha = canonical_document_sha256(doc)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        with pytest.raises(LeaseLostError):
            await repo.persist_document_candidate(
                doc,
                document_sha256=sha,
                worker_id=lease.worker_id,
                lease_token=lease.lease_token + 99,
            )


@pytest.mark.asyncio
async def test_finalize_rejects_candidate_token_mismatch() -> None:
    gid = await _seed()
    lease = await _claim(gid)
    doc = _tiny_document()
    sha = canonical_document_sha256(doc)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        await repo.persist_document_candidate(
            doc,
            document_sha256=sha,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )

        def _tamper_token(_gen, state):
            state["execution"]["candidate_lease_token"] = int(lease.lease_token) + 1

        await repo.mutate_state(
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            mutation=_tamper_token,
        )
        with pytest.raises(DocumentFenceError, match="candidate lease token"):
            await repo.finalize_verified_document(
                expected_document_sha256=sha,
                reloaded_sha256=sha,
                pending_visuals=False,
                worker_id=lease.worker_id,
                lease_token=lease.lease_token,
            )


@pytest.mark.asyncio
async def test_finalize_rejects_tampered_document() -> None:
    gid = await _seed()
    lease = await _claim(gid)
    doc = _tiny_document()
    sha = canonical_document_sha256(doc)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, gid)
        await repo.persist_document_candidate(
            doc,
            document_sha256=sha,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        tampered = _tiny_document()
        tampered["sections"][0]["blocks"][0]["content"] = {
            "paragraphs": ["TAMPERED"]
        }
        generation.document_json = persist_document_json(None, tampered)
        await session.commit()

        with pytest.raises(DocumentFenceError, match="tamper"):
            await repo.finalize_verified_document(
                expected_document_sha256=sha,
                reloaded_sha256=sha,
                pending_visuals=False,
                worker_id=lease.worker_id,
                lease_token=lease.lease_token,
            )


@pytest.mark.asyncio
async def test_atomic_finalize_fields() -> None:
    gid = await _seed()
    lease = await _claim(gid)
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.status = "assembling"
        await session.commit()
        assembled = await assemble_from_db(
            session=session,
            generation_id=gid,
            packet=_packet(),
            form_plan=_form_plan(),
            lease=lease,
        )
        assert assembled["terminal"] == "ready"
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        execution = state["execution"]
        assert execution["document_sha256"] == assembled["document_sha256"]
        assert execution["reloaded_sha256"] == assembled["reloaded_sha256"]
        assert execution["reload_verified"] is True
        assert execution["candidate_document_sha256"] == assembled["document_sha256"]
        assert int(state["document_revision"]) >= 1
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "ready"
        events = state.get("events") or []
        assert any(e.get("type") == "document_ready" for e in events)


@pytest.mark.asyncio
async def test_assemble_requires_lease() -> None:
    gid = await _seed()
    async with async_session_factory() as session:
        with pytest.raises(AssemblyError, match="ExecutionLease"):
            await assemble_from_db(
                session=session,
                generation_id=gid,
                packet=_packet(),
                form_plan=_form_plan(),
                lease=None,
            )

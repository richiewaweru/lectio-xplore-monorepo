from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_lesson_approved_source import _prepared

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from document.shared_lesson import media_dispatcher
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.http import get_shared_document_preview
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from document.shared_lesson.run_admission import admit_shared_document_run
from document.shared_lesson.worker import SharedDocumentWorker
from infra.database.models import (
    GenerationRunModel,
    GenerationWorkItemModel,
    SharedLessonDocumentModel,
)
from infra.execution.checkpoints import content_hash


class _StructuredProvider:
    """Small deterministic structured provider used by semantic stages."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def invoke(self, call):
        self.calls.append(call)
        return self.responses.pop(0)


def _composer_provider(calls: list[dict]):
    async def provide(payload):
        calls.append(payload)
        block = payload["section"]["blocks"][0]
        return {
            "items": [
                {
                    "teaching_block_id": block["id"],
                    "kind": "paragraph",
                    "semantic_role": "explanation",
                }
            ]
        }

    return provide


def _writer_provider(calls: list[dict]):
    async def provide(payload):
        calls.append(payload)
        item = payload["composition_plan"][0]
        return {
            "nodes": [
                {
                    "id": item["id"],
                    "kind": "paragraph",
                    "teaching_block_id": item["teaching_block_id"],
                    "display": {
                        "text": (
                            "Learner can name a root. Roots take in water. "
                            "Learner can describe root uptake."
                        )
                    },
                }
            ]
        }

    return provide


async def _admit(db_session, *, generation, lesson):
    result = await admit_shared_document_run(
        db_session,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        request_key="full-run",
    )
    await db_session.commit()
    return result


async def _advance_semantic_worker(
    db_session,
    db_session_factory,
    *,
    generation,
    lesson,
    monkeypatch,
):
    sourcebook_provider = _StructuredProvider({"entries": []})
    composer_calls: list[dict] = []
    writer_calls: list[dict] = []
    worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="full-run-worker",
        provider=sourcebook_provider,
        composer_provider=_composer_provider(composer_calls),
        writer_provider=_writer_provider(writer_calls),
    )
    # Admission and each worker step use independent durable sessions in the
    # same isolated database, matching the application worker boundary.
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await worker.run_one(session)
            await session.commit()
        if not progressed:
            break
    return sourcebook_provider, composer_calls, writer_calls


@pytest.mark.asyncio
async def test_full_run_admission_to_ready_is_atomic_and_immutable(
    db_session, db_session_factory, monkeypatch
):
    generation, lesson, _provenance, source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)

    sourcebook_provider, composer_calls, writer_calls = await _advance_semantic_worker(
        db_session,
        db_session_factory,
        generation=generation,
        lesson=lesson,
        monkeypatch=monkeypatch,
    )

    qa_calls = 0

    async def qa_provider(_request):
        nonlocal qa_calls
        qa_calls += 1
        return DocumentSemanticVerdict(status="pass")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=qa_provider,
        worker_id="full-run-post-section",
    )
    assert outcome.state == "ready", outcome.error
    assert outcome.document_id
    assert len(sourcebook_provider.calls) == 0  # no response-bearing blocks need task authoring
    assert len(composer_calls) == 1
    assert len(writer_calls) == 1
    assert qa_calls == 1

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "ready"
        assert run.output_artifact_type == "shared_lesson_document"
        assert run.output_artifact_id == outcome.document_id
        assert run.output_hash

        items = list(
            (
                await verify.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == admission.run.id
                    )
                )
            ).all()
        )
        assert items
        assert all(item.status == "ready" for item in items)
        assert {item.run_id for item in items} == {admission.run.id}

        stored = await verify.scalar(
            select(SharedLessonDocumentModel).where(
                SharedLessonDocumentModel.id == outcome.document_id
            )
        )
        assert stored is not None
        assert stored.content_hash == stored.document_json["content_hash"]
        assert stored.document_json["content_hash"] == stored.content_hash

        preview = await get_shared_document_preview(
            outcome.document_id,
            stored.revision,
            current_user=SimpleNamespace(id="source-owner"),
            session=verify,
        )
        assert preview["status"] == "ready"
        assert preview["output"]["id"] == outcome.document_id
        assert preview["document"]["content_hash"] == stored.content_hash
        assert preview["output"]["hash"] == content_hash(stored.document_json)
        assert content_hash(preview["document"]) == run.output_hash
        assert teaching_plan_content_hash(source.plan) == run.source_hash


@pytest.mark.asyncio
async def test_required_media_failure_blocks_ready_and_preserves_siblings(
    db_session, db_session_factory, monkeypatch
):
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session,
        db_session_factory,
        generation=generation,
        lesson=lesson,
        monkeypatch=monkeypatch,
    )

    async def blocked_media(self, **_kwargs):
        return SimpleNamespace(
            readiness=media_dispatcher.MediaReadiness(
                ready=False,
                required_count=2,
                ready_count=1,
                failed_required_work_item_ids=("media:figure-a",),
            ),
            results=("healthy-sibling",),
        )

    monkeypatch.setattr(media_dispatcher.SharedMediaDispatcher, "run_one", blocked_media)

    async def qa_provider(_request):
        raise AssertionError("required media failure must stop before QA")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=qa_provider,
        worker_id="full-run-media-failure",
    )
    assert outcome.state == "blocked"
    assert outcome.stage == "media"

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status != "ready"
        assert run.output_artifact_id is None
        items = list(
            (
                await verify.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == admission.run.id
                    )
                )
            ).all()
        )
        assert all(item.run_id == admission.run.id for item in items)
        assert all(item.status == "ready" for item in items)

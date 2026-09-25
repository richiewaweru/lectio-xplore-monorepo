from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from document.shared_lesson.finalizer import (
    SharedLessonFinalizationError,
    SharedLessonFinalizationRequest,
    VerifiedWorkItemOutput,
    _verify_durable_inputs_match_handoff,
    _verify_media_matches_work_items,
)
from document.shared_lesson.handoff import SharedLessonHandoffEvidence
from document.shared_lesson.media import ReadyFigureMediaResult
from document.shared_lesson.models import build_shared_lesson_document
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.writer import SectionSource
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash

from test_shared_lesson_repository import (
    _approved_source_and_document,
    _bound_media,
    _expected_shapes,
    _ready_assembly,
    _semantic_pass,
)


def _handoff(source, document, *, expected_shapes=None):
    return SharedLessonHandoffEvidence(
        status="ready",
        document=document,
        deterministic_qa=_ready_assembly(document).qa,
        semantic_qa=_semantic_pass(document),
        expected_shapes=expected_shapes or _expected_shapes(),
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
    )


def _request(source, document, *, tasks=(), sources=()):
    return SharedLessonFinalizationRequest(
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        source=source,
        handoff=_handoff(source, document),
        tasks=tasks,
        sources=sources,
        approved_source_ids=(),
        source_facts_by_section=None,
        required_media_by_section=None,
        media_results=(),
    )


def _verified_inputs(document):
    return SimpleNamespace(
        sections=document.sections,
        compositions=(
            SectionCompositionPlan(
                section_slot_id="section-1",
                items=(
                    CompositionItem(
                        id="paragraph-1",
                        kind="paragraph",
                        teaching_block_id="block-1",
                        semantic_role="explanation",
                    ),
                ),
            ),
        ),
    )


def test_finalization_request_requires_explicit_semantic_inputs() -> None:
    source, document = _approved_source_and_document()

    with pytest.raises(ValidationError, match="tasks|sources"):
        SharedLessonFinalizationRequest.model_validate(
            {
                "run_id": "run-1",
                "owner_user_id": "owner-1",
                "path_lesson_id": "path-lesson-1",
                "source": source,
                "handoff": _handoff(source, document),
                "approved_source_ids": (),
                "source_facts_by_section": None,
                "required_media_by_section": None,
                "media_results": (),
            }
        )


def test_finalization_request_rejects_task_from_a_different_plan_revision() -> None:
    source, document = _approved_source_and_document()
    with pytest.raises(ValueError, match="approved Teaching Plan revision"):
        _request(
            source,
            document,
            tasks=(
                {
                    "id": "task-1",
                    "teaching_plan_id": source.id,
                    "teaching_plan_revision": source.revision + 1,
                    "teaching_plan_hash": source.content_hash,
                    "teaching_block_id": "block-1",
                    "mode": "formative",
                    "action": "read-explanation",
                    "purpose": "Understand",
                    "prompt": "Read",
                    "difficulty": "guided",
                    "expected_evidence": "understand",
                    "response": {"type": "text"},
                    "evaluation": {"type": "teacher_review"},
                },
            ),
            sources=(SectionSource(id="source-1", kind="approved_fact", text="Fact"),),
        )


def test_forged_handoff_sections_are_rejected_against_durable_writer_outputs() -> None:
    source, document = _approved_source_and_document()
    forged_payload = document.model_dump(mode="json")
    forged_payload["sections"][0]["nodes"][0]["display"]["text"] = "Forged output"
    forged = build_shared_lesson_document(forged_payload)
    verified_inputs = _verified_inputs(document)

    with pytest.raises(SharedLessonFinalizationError, match="durable writer outputs"):
        _verify_durable_inputs_match_handoff(
            document=forged,
            tasks=(),
            verified_inputs=verified_inputs,
            handoff_expected_shapes=_expected_shapes(),
        )


def test_forged_handoff_shapes_are_rejected_against_durable_compositions() -> None:
    _source, document = _approved_source_and_document()
    verified_inputs = _verified_inputs(document)
    forged_shapes = {
        "section-1": (
            ExpectedNodeShape(
                id="forged-node",
                kind="paragraph",
                teaching_block_id="block-1",
                semantic_role="explanation",
            ),
        )
    }

    with pytest.raises(SharedLessonFinalizationError, match="expected node shapes"):
        _verify_durable_inputs_match_handoff(
            document=document,
            tasks=(),
            verified_inputs=verified_inputs,
            handoff_expected_shapes=forged_shapes,
        )


def test_media_evidence_must_match_ready_media_work_item() -> None:
    source, document = _approved_source_and_document(include_figure=True)
    media = _bound_media(source, document)
    ready_payload = media.model_dump(mode="json")
    ready_payload.pop("source_document_id")
    ready_payload.pop("source_document_revision")
    ready_payload.pop("source_document_hash")
    ready = ReadyFigureMediaResult.model_validate(ready_payload)
    item = GenerationWorkItemModel(
        id="media-item-1",
        run_id="run-1",
        item_key=f"media:{ready.work_order_id}",
        stage="media_generation",
        status="ready",
        input_hash="input",
        definition_hash="definition",
        output_json=ready.model_dump(mode="json"),
        output_hash=content_hash(ready.model_dump(mode="json")),
    )
    output = VerifiedWorkItemOutput(
        work_item_id=item.id,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )
    forged = media.model_copy(update={"asset_id": "different-asset"})

    with pytest.raises(SharedLessonFinalizationError, match="durable work-item output"):
        _verify_media_matches_work_items(
            document=document,
            media_results=(forged,),
            active_items=(item,),
            loaded_outputs=(output,),
        )


def test_verified_work_item_output_rejects_tampered_hash() -> None:
    with pytest.raises(ValueError, match="hash"):
        VerifiedWorkItemOutput(
            work_item_id="item-1",
            output_json={"section": "accepted"},
            output_hash="0" * 64,
        )


class _TransactionProbe:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class _SessionProbe:
    def __init__(self, transaction: _TransactionProbe) -> None:
        self.transaction = transaction

    def in_transaction(self) -> bool:
        return False

    def begin(self) -> _TransactionProbe:
        return self.transaction


@pytest.mark.asyncio
async def test_finalizer_rolls_back_document_write_when_run_commit_fails(monkeypatch) -> None:
    import document.shared_lesson.finalizer as finalizer

    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(
        id="writer-item-1",
        run_id=request.run_id,
        item_key="write:section-1",
        stage="section_writing",
        status="ready",
        input_hash="input",
        definition_hash="definition",
        output_json={"accepted": True},
        output_hash=content_hash({"accepted": True}),
    )
    run = SimpleNamespace(
        id=request.run_id,
        owner_user_id=request.owner_user_id,
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
    )
    probe = _TransactionProbe()
    session = _SessionProbe(probe)
    writes: list[str] = []

    async def source_verifier(_session, identity):
        return identity

    async def work_loader(_session, _run_id):
        return (
            {
                "work_item_id": item.id,
                "output_json": item.output_json,
                "output_hash": item.output_hash,
            },
        )

    async def fake_inputs(*_args, **_kwargs):
        return _verified_inputs(document)

    async def fake_save(*_args, **_kwargs):
        writes.append("draft")

    async def fake_promote(*_args, **_kwargs):
        writes.append("ready")
        raise RuntimeError("simulated finalization conflict")

    monkeypatch.setattr(finalizer, "_load_and_lock_run", lambda *a, **k: _locked(run, item))
    monkeypatch.setattr(finalizer, "load_verified_shared_lesson_inputs", fake_inputs)
    monkeypatch.setattr(finalizer, "save_shared_lesson_document", fake_save)
    monkeypatch.setattr(finalizer, "promote_shared_lesson_document", fake_promote)

    with pytest.raises(RuntimeError, match="simulated finalization conflict"):
        await finalizer.finalize_shared_lesson_document(
            session,
            request=request,
            source_verifier=source_verifier,
            work_item_loader=work_loader,
        )

    assert writes == ["draft", "ready"]
    assert probe.committed is False
    assert probe.rolled_back is True


@pytest.mark.asyncio
async def test_finalizer_commits_document_and_run_together(monkeypatch) -> None:
    import document.shared_lesson.finalizer as finalizer

    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(
        id="writer-item-2",
        run_id=request.run_id,
        item_key="write:section-1",
        stage="section_writing",
        status="ready",
        input_hash="input",
        definition_hash="definition",
        output_json={"accepted": True},
        output_hash=content_hash({"accepted": True}),
    )
    run = SimpleNamespace(
        id=request.run_id,
        owner_user_id=request.owner_user_id,
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
    )
    probe = _TransactionProbe()
    session = _SessionProbe(probe)

    async def source_verifier(_session, identity):
        return identity

    async def work_loader(_session, _run_id):
        return (
            {
                "work_item_id": item.id,
                "output_json": item.output_json,
                "output_hash": item.output_hash,
            },
        )

    async def fake_inputs(*_args, **_kwargs):
        return _verified_inputs(document)

    async def fake_save(*_args, **_kwargs):
        return SimpleNamespace(status="draft")

    async def fake_promote(*_args, **_kwargs):
        return SimpleNamespace(status="ready")

    async def fake_finalize(*_args, **_kwargs):
        return run

    monkeypatch.setattr(finalizer, "_load_and_lock_run", lambda *a, **k: _locked(run, item))
    monkeypatch.setattr(finalizer, "load_verified_shared_lesson_inputs", fake_inputs)
    monkeypatch.setattr(finalizer, "save_shared_lesson_document", fake_save)
    monkeypatch.setattr(finalizer, "promote_shared_lesson_document", fake_promote)
    monkeypatch.setattr(finalizer, "finalize_run", fake_finalize)

    result = await finalizer.finalize_shared_lesson_document(
        session,
        request=request,
        source_verifier=source_verifier,
        work_item_loader=work_loader,
    )

    assert result.run is run
    assert result.document.status == "ready"
    assert probe.committed is True
    assert probe.rolled_back is False


async def _locked(run, item):
    return run, (item,)

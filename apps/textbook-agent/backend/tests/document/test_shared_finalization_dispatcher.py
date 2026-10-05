from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_shared_lesson_finalizer import (
    _approved_source_and_document,
    _bound_media,
    _deferred_binding,
    _expected_shapes,
    _handoff,
    _source_with_frozen_items,
    _verified_semantic_inputs,
)

from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.finalization_dispatcher import (
    finalize_shared_lesson_document_for_run,
)
from document.shared_lesson.media import DeferredFigureMediaResult, ReadyFigureMediaResult
from document.shared_lesson.qa_runtime import DOCUMENT_QA_STAGE, VerifiedDocumentQA
from infra.config import settings
from infra.execution.checkpoints import content_hash


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def scalars(self, _statement):
        return _Rows(self.rows)


def _accepted_inputs(document):
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
                    CompositionItem(
                        id="figure-1",
                        kind="figure",
                        teaching_block_id="block-1",
                        semantic_role="explanation",
                    ),
                ),
            ),
        ),
    )


def _qa_item():
    return SimpleNamespace(
        id="document-qa-item",
        stage=DOCUMENT_QA_STAGE,
        status="ready",
        item_key="document_qa",
        replaces_work_item_id=None,
    )


def _ready_media_item(source, document, *, tamper=False):
    bound = _bound_media(source, document)
    ready = ReadyFigureMediaResult(
        source_plan_id=bound.source_plan_id,
        source_plan_revision=bound.source_plan_revision,
        source_plan_hash=bound.source_plan_hash,
        section_id=bound.section_id,
        section_output_hash=bound.section_output_hash,
        figure_node_id=bound.figure_node_id,
        figure_semantic_hash=bound.figure_semantic_hash,
        work_order_id=bound.work_order_id,
        visual_id=bound.visual_id,
        asset_id=bound.asset_id,
        asset_url=bound.asset_url,
        mode=bound.mode,
        alt_text=bound.alt_text,
        source_facts=bound.source_facts,
        required=bound.required,
        status=bound.status,
    )
    payload = ready.model_dump(mode="json")
    if tamper:
        payload["figure_semantic_hash"] = "f" * 64
    return SimpleNamespace(
        id="media-item",
        stage="media_generation",
        status="ready",
        item_key=f"media:{ready.work_order_id}",
        replaces_work_item_id=None,
        output_json=payload,
        output_hash=content_hash(payload),
    )


def _deferred_media_item(source, document):
    bound = _deferred_binding(source, document)
    unbound_payload = bound.model_dump(mode="json")
    for key in ("source_document_id", "source_document_revision", "source_document_hash"):
        unbound_payload.pop(key)
    unbound = DeferredFigureMediaResult.model_validate(unbound_payload)
    payload = unbound.model_dump(mode="json")
    return SimpleNamespace(
        id="media-item",
        stage="media_generation",
        status="ready",
        item_key=f"media:{unbound.work_order_id}",
        replaces_work_item_id=None,
        output_json=payload,
        output_hash=content_hash(payload),
    )


@pytest.mark.asyncio
async def test_finalization_dispatcher_admits_deferred_required_figure_when_media_optional_is_on(
    monkeypatch,
):
    monkeypatch.setattr(settings, "shared_document_media_optional", True)
    source, document = _approved_source_and_document(include_figure=True)
    source = _source_with_frozen_items(source)
    handoff = _handoff(
        source,
        document,
        expected_shapes=_expected_shapes(include_figure=True),
    )
    semantic = _verified_semantic_inputs(source)
    accepted = _accepted_inputs(document)
    rows = [_qa_item(), _deferred_media_item(source, document)]
    captured = {}

    async def load_source(**_kwargs):
        return source

    async def load_semantic(*_args, **_kwargs):
        return semantic

    async def load_accepted(*_args, **_kwargs):
        return accepted

    async def load_qa(*_args, **_kwargs):
        return VerifiedDocumentQA(
            work_item_id="document-qa-item",
            output_hash="0" * 64,
            semantic_qa=handoff.semantic_qa,
        )

    async def finalize(_session, *, request, **_kwargs):
        captured["request"] = request
        return "finalized"

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        load_source,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_semantic_inputs",
        load_semantic,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_shared_lesson_inputs",
        load_accepted,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_document_qa",
        load_qa,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.finalize_shared_lesson_document",
        finalize,
    )

    outcome = await finalize_shared_lesson_document_for_run(
        _Session(rows),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )

    assert outcome.ready
    assert outcome.result == "finalized"
    request = captured["request"]
    assert request.required_media_by_section == {"section-1": ("figure-1",)}
    assert request.media_results[0].figure_node_id == "figure-1"
    assert request.media_results[0].status == "deferred"


@pytest.mark.asyncio
async def test_finalization_dispatcher_rejects_deferred_media_when_media_optional_is_off(
    monkeypatch,
):
    assert settings.shared_document_media_optional is False
    source, document = _approved_source_and_document(include_figure=True)
    source = _source_with_frozen_items(source)
    handoff = _handoff(
        source,
        document,
        expected_shapes=_expected_shapes(include_figure=True),
    )
    semantic = _verified_semantic_inputs(source)
    accepted = _accepted_inputs(document)
    rows = [_qa_item(), _deferred_media_item(source, document)]

    async def load_source(**_kwargs):
        return source

    async def load_semantic(*_args, **_kwargs):
        return semantic

    async def load_accepted(*_args, **_kwargs):
        return accepted

    async def load_qa(*_args, **_kwargs):
        return VerifiedDocumentQA(
            work_item_id="document-qa-item",
            output_hash="0" * 64,
            semantic_qa=handoff.semantic_qa,
        )

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        load_source,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_semantic_inputs",
        load_semantic,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_shared_lesson_inputs",
        load_accepted,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_document_qa",
        load_qa,
    )

    outcome = await finalize_shared_lesson_document_for_run(
        _Session(rows),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )

    assert outcome.status == "blocked"
    assert "media" in (outcome.error or "")


@pytest.mark.asyncio
async def test_finalization_dispatcher_derives_durable_inputs_and_calls_atomic_finalizer(
    monkeypatch,
):
    source, document = _approved_source_and_document(include_figure=True)
    source = _source_with_frozen_items(source)
    handoff = _handoff(
        source,
        document,
        expected_shapes=_expected_shapes(include_figure=True),
    )
    semantic = _verified_semantic_inputs(source)
    accepted = _accepted_inputs(document)
    rows = [_qa_item(), _ready_media_item(source, document)]
    captured = {}

    async def load_source(**_kwargs):
        return source

    async def load_semantic(*_args, **_kwargs):
        return semantic

    async def load_accepted(*_args, **_kwargs):
        return accepted

    async def load_qa(*_args, **_kwargs):
        return VerifiedDocumentQA(
            work_item_id="document-qa-item",
            output_hash="0" * 64,
            semantic_qa=handoff.semantic_qa,
        )

    async def finalize(_session, *, request, **_kwargs):
        captured["request"] = request
        return "finalized"

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        load_source,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_semantic_inputs",
        load_semantic,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_shared_lesson_inputs",
        load_accepted,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_document_qa",
        load_qa,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.finalize_shared_lesson_document",
        finalize,
    )

    outcome = await finalize_shared_lesson_document_for_run(
        _Session(rows),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )

    assert outcome.ready
    assert outcome.result == "finalized"
    request = captured["request"]
    assert request.tasks == ()
    assert tuple(source.id for source in request.sources) == request.approved_source_ids
    assert request.required_media_by_section == {"section-1": ("figure-1",)}
    assert request.source_facts_by_section is None
    assert request.media_results[0].figure_node_id == "figure-1"


@pytest.mark.asyncio
async def test_finalization_dispatcher_blocks_stale_handoff_before_finalizer(monkeypatch):
    source, document = _approved_source_and_document()
    source = _source_with_frozen_items(source)
    handoff = _handoff(source, document).model_copy(update={"teaching_plan_hash": "f" * 64})

    async def load_source(**_kwargs):
        return source

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        load_source,
    )
    outcome = await finalize_shared_lesson_document_for_run(
        _Session([]),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )

    assert outcome.status == "blocked"
    assert "stale" in (outcome.error or "")


@pytest.mark.asyncio
async def test_finalization_dispatcher_propagates_unexpected_programming_error(monkeypatch):
    async def broken_source_loader(**_kwargs):
        raise ValueError("programming bug")

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        broken_source_loader,
    )
    source, document = _approved_source_and_document()
    source = _source_with_frozen_items(source)

    with pytest.raises(ValueError, match="programming bug"):
        await finalize_shared_lesson_document_for_run(
            _Session([]),
            run_id="run-1",
            owner_user_id="owner-1",
            path_lesson_id="path-lesson-1",
            preparation_generation_id="generation-1",
            handoff=_handoff(source, document),
        )


@pytest.mark.asyncio
async def test_finalization_dispatcher_blocks_missing_or_forged_media(monkeypatch):
    source, document = _approved_source_and_document(include_figure=True)
    source = _source_with_frozen_items(source)
    handoff = _handoff(
        source,
        document,
        expected_shapes=_expected_shapes(include_figure=True),
    )
    semantic = _verified_semantic_inputs(source)
    accepted = _accepted_inputs(document)

    async def load_source(**_kwargs):
        return source

    async def load_semantic(*_args, **_kwargs):
        return semantic

    async def load_accepted(*_args, **_kwargs):
        return accepted

    async def load_qa(*_args, **_kwargs):
        return VerifiedDocumentQA(
            work_item_id="document-qa-item",
            output_hash="0" * 64,
            semantic_qa=handoff.semantic_qa,
        )

    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_current_approved_teaching_plan_source",
        load_source,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_semantic_inputs",
        load_semantic,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_shared_lesson_inputs",
        load_accepted,
    )
    monkeypatch.setattr(
        "document.shared_lesson.finalization_dispatcher.load_verified_document_qa",
        load_qa,
    )

    missing = await finalize_shared_lesson_document_for_run(
        _Session([_qa_item()]),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )
    assert missing.status == "blocked"
    assert "media" in (missing.error or "")

    forged = await finalize_shared_lesson_document_for_run(
        _Session([_qa_item(), _ready_media_item(source, document, tamper=True)]),
        run_id="run-1",
        owner_user_id="owner-1",
        path_lesson_id="path-lesson-1",
        preparation_generation_id="generation-1",
        handoff=handoff,
    )
    assert forged.status == "blocked"
    assert "media" in (forged.error or "")

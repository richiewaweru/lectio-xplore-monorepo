from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from test_shared_boundary_runtime import _section as _boundary_section
from test_shared_boundary_runtime import _source as _boundary_source
from test_shared_lesson_repository import (
    _approved_source_and_document,
    _bound_media,
    _expected_shapes,
    _ready_assembly,
    _semantic_pass,
)

from curriculum.lesson_sourcebook import LessonSourcebook, SourcebookEntry
from curriculum.teaching_plan.revisions import approved_item_snapshot_hash
from document.shared_lesson.boundary_runtime import (
    BOUNDARY_DEFINITION,
    BOUNDARY_STAGE,
    BoundaryWorkOrder,
)
from document.shared_lesson.boundary_runtime import (
    accepted_section_output_hash as _accepted_section_output_hash,
)
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.finalizer import (
    SharedLessonFinalizationError,
    SharedLessonFinalizationRequest,
    VerifiedWorkItemOutput,
    _boundary_item_composition_identity,
    _verify_boundary_coverage,
    _verify_document_qa_matches_handoff,
    _verify_durable_inputs_match_handoff,
    _verify_media_matches_work_items,
    _verify_semantic_inputs_match_request,
)
from document.shared_lesson.handoff import SharedLessonHandoffEvidence
from document.shared_lesson.media import (
    DeferredFigureMediaResult,
    ReadyFigureMediaResult,
    bind_deferred_figure_media,
    bind_deferred_figure_media_to_document,
    build_figure_work_order,
)
from document.shared_lesson.models import build_shared_lesson_document
from document.shared_lesson.qa_runtime import VerifiedDocumentQA
from document.shared_lesson.runtime import _stable_hash
from document.shared_lesson.semantic_inputs import VerifiedSemanticInputs
from document.shared_lesson.writer import SectionSource, SectionWriteResult
from infra.config import settings
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash


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
    source = _source_with_frozen_items(source)
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


def _source_with_frozen_items(source):
    """Give legacy test sources the revision-bound snapshot required by semantic inputs."""
    snapshot = {
        "schema_version": 1,
        "teaching_plan_id": source.id,
        "teaching_plan_revision": source.revision,
        "teaching_plan_hash": source.content_hash,
        "items": {},
    }
    record = source.revision_record.model_copy(
        update={
            "approved_item_snapshot": snapshot,
            "approved_item_snapshot_hash": approved_item_snapshot_hash(snapshot),
        }
    )
    return source.model_copy(update={"revision_record": record})


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


def _verified_semantic_inputs(source, *, tasks=(), sourcebook=None):
    source = _source_with_frozen_items(source)
    sourcebook = sourcebook or LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=[],
    )
    return VerifiedSemanticInputs(
        run_id="run-1",
        owner_user_id="owner-1",
        source=source,
        sourcebook=sourcebook,
        tasks=tasks,
        approved_item_snapshot=source.revision_record.approved_item_snapshot,
        approved_item_snapshot_hash=source.revision_record.approved_item_snapshot_hash,
        sourcebook_output_hash=content_hash(sourcebook.model_dump(mode="json")),
        task_output_hash="0" * 64,
        work_item_ids={"sourcebook": "sourcebook-item", "shared_tasks": "task-item"},
    )


def _verified_qa(request, work_item_id):
    return VerifiedDocumentQA(
        work_item_id=work_item_id,
        output_hash="0" * 64,
        semantic_qa=request.handoff.semantic_qa,
    )


def _boundary_fixture(*, previous_warnings=()):
    source = _boundary_source()
    previous = _boundary_section("s1", 0, "The first idea.")
    next_ = _boundary_section("s2", 1, "The second idea.")
    document = build_shared_lesson_document(
        {
            "id": "boundary-lesson",
            "revision": 1,
            "teaching_plan_id": source.id,
            "teaching_plan_revision": source.revision,
            "teaching_plan_hash": source.content_hash,
            "title": "Two ideas",
            "sections": [previous.model_dump(mode="json"), next_.model_dump(mode="json")],
            "created_at": "2026-09-25T00:00:00Z",
        }
    )
    previous_composition = SectionCompositionPlan(
        section_slot_id="s1",
        items=(
            CompositionItem(
                id="s1-node",
                kind="paragraph",
                teaching_block_id="s1-block",
                semantic_role="explanation",
            ),
        ),
    )
    next_composition = SectionCompositionPlan(
        section_slot_id="s2",
        items=(
            CompositionItem(
                id="s2-node",
                kind="paragraph",
                teaching_block_id="s2-block",
                semantic_role="explanation",
            ),
        ),
    )
    verified_inputs = SimpleNamespace(
        source=source,
        sections=(previous, next_),
        compositions=(previous_composition, next_composition),
        composition_hashes={
            "s1": content_hash(previous_composition.model_dump(mode="json")),
            "s2": content_hash(next_composition.model_dump(mode="json")),
        },
        section_hashes={
            "s1": content_hash(
                SectionWriteResult(
                    section_slot_id="s1",
                    title=previous.title,
                    nodes=previous.nodes,
                    warnings=previous_warnings,
                ).model_dump(mode="json")
            ),
            "s2": content_hash(
                SectionWriteResult(
                    section_slot_id="s2", title=next_.title, nodes=next_.nodes
                ).model_dump(mode="json")
            ),
        },
        section_warnings={"s1": tuple(previous_warnings)} if previous_warnings else {},
    )
    previous_identity = _stable_hash(previous_composition.model_dump(mode="json"))
    next_identity = _stable_hash(next_composition.model_dump(mode="json"))
    work = BoundaryWorkOrder(
        source_plan_id=source.id,
        source_plan_revision=source.revision,
        source_plan_hash=source.content_hash,
        previous_section_id=previous.id,
        previous_section_output_hash=_accepted_section_output_hash(previous),
        previous_composition_identity=previous_identity,
        next_section_id=next_.id,
        next_section_output_hash=_accepted_section_output_hash(next_),
        next_composition_identity=next_identity,
    )
    output = {
        "kind": "shared_lesson_boundary_result",
        "status": "pass",
        "work": work.model_dump(mode="json"),
        "previous_section": previous.model_dump(mode="json"),
        "next_section": next_.model_dump(mode="json"),
        "semantic_calls": 0,
    }
    item = GenerationWorkItemModel(
        id="boundary-item",
        run_id="run-1",
        item_key="boundary:s1->s2",
        stage=BOUNDARY_STAGE,
        status="ready",
        input_hash=content_hash(work.model_dump(mode="json")),
        definition_hash=hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest(),
        composition_identity=_boundary_item_composition_identity(previous_identity, next_identity),
        output_json=output,
        output_hash=content_hash(output),
    )
    return source, document, verified_inputs, item


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
    _, document = _approved_source_and_document()
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


def _edited_revision(document, *, text: str) -> object:
    payload = document.model_dump(mode="json")
    payload["revision"] = document.revision + 1
    payload["sections"][0]["nodes"][0]["display"]["text"] = text
    payload.pop("content_hash", None)
    return build_shared_lesson_document(payload)


@pytest.mark.asyncio
async def test_review_structural_document_accepts_figure_section_edit_with_regenerated_media(
    monkeypatch,
) -> None:
    from document.shared_lesson import finalizer

    source, origin = _approved_source_and_document(include_figure=True)
    edited = _edited_revision(origin, text="Plants use light to make food, roots and all.")

    async def fake_load(_session, *, document_id, revision, path_lesson_id):
        assert document_id == origin.id
        assert path_lesson_id == "path-lesson-1"
        return SimpleNamespace(document=origin if revision == 1 else edited)

    monkeypatch.setattr(finalizer, "load_shared_lesson_document", fake_load)
    regenerated_media = _bound_media(source, edited)

    resolved = await finalizer.resolve_review_structural_document(
        object(),
        path_lesson_id="path-lesson-1",
        document=edited,
        media_results=(regenerated_media,),
    )
    assert resolved == origin


@pytest.mark.asyncio
async def test_review_structural_document_rejects_figure_section_edit_without_regenerated_media(
    monkeypatch,
) -> None:
    from document.shared_lesson import finalizer

    _source, origin = _approved_source_and_document(include_figure=True)
    edited = _edited_revision(origin, text="Plants use light to make food, roots and all.")

    async def fake_load(_session, *, document_id, revision, path_lesson_id):
        return SimpleNamespace(document=origin if revision == 1 else edited)

    monkeypatch.setattr(finalizer, "load_shared_lesson_document", fake_load)

    with pytest.raises(SharedLessonFinalizationError, match="without regenerated"):
        await finalizer.resolve_review_structural_document(
            object(),
            path_lesson_id="path-lesson-1",
            document=edited,
            media_results=(),
        )


@pytest.mark.asyncio
async def test_review_structural_document_rejects_stale_media_bound_to_prior_revision(
    monkeypatch,
) -> None:
    from document.shared_lesson import finalizer

    source, origin = _approved_source_and_document(include_figure=True)
    edited = _edited_revision(origin, text="Plants use light to make food, roots and all.")

    async def fake_load(_session, *, document_id, revision, path_lesson_id):
        return SimpleNamespace(document=origin if revision == 1 else edited)

    monkeypatch.setattr(finalizer, "load_shared_lesson_document", fake_load)
    # Media frozen against the ORIGIN's section output hash, never regenerated
    # against the edited revision, must never be accepted as evidence.
    stale_media = _bound_media(source, origin)

    with pytest.raises(SharedLessonFinalizationError, match="figure media"):
        await finalizer.resolve_review_structural_document(
            object(),
            path_lesson_id="path-lesson-1",
            document=edited,
            media_results=(stale_media,),
        )


@pytest.mark.asyncio
async def test_review_structural_document_unchanged_for_non_figure_edit(monkeypatch) -> None:
    from document.shared_lesson import finalizer

    _source, origin = _approved_source_and_document()
    edited = _edited_revision(origin, text="A different but still allowlisted paragraph edit.")

    async def fake_load(_session, *, document_id, revision, path_lesson_id):
        return SimpleNamespace(document=origin if revision == 1 else edited)

    monkeypatch.setattr(finalizer, "load_shared_lesson_document", fake_load)

    resolved = await finalizer.resolve_review_structural_document(
        object(),
        path_lesson_id="path-lesson-1",
        document=edited,
        media_results=(),
    )
    assert resolved == origin


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


def _deferred_binding(source, document, *, reason_code: str = "media_provider_failed"):
    work = build_figure_work_order(
        source,
        document.sections[0],
        figure_node_id="figure-1",
        expected_shape=_expected_shapes(include_figure=True)["section-1"],
    )
    deferred = bind_deferred_figure_media(work, reason_code=reason_code)
    return bind_deferred_figure_media_to_document(deferred, document)


def _work_item_for(deferred_output: dict) -> GenerationWorkItemModel:
    return GenerationWorkItemModel(
        id="media-item-1",
        run_id="run-1",
        item_key=f"media:{deferred_output['work_order_id']}",
        stage="media_generation",
        status="ready",
        input_hash="input",
        definition_hash="definition",
        output_json=deferred_output,
        output_hash=content_hash(deferred_output),
    )


def test_media_evidence_accepts_deferred_output_when_media_optional_is_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "shared_document_media_optional", True)
    source, document = _approved_source_and_document(include_figure=True)
    bound = _deferred_binding(source, document)
    unbound_payload = bound.model_dump(mode="json")
    for key in ("source_document_id", "source_document_revision", "source_document_hash"):
        unbound_payload.pop(key)
    unbound = DeferredFigureMediaResult.model_validate(unbound_payload)
    item = _work_item_for(unbound.model_dump(mode="json"))
    output = VerifiedWorkItemOutput(
        work_item_id=item.id,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )

    _verify_media_matches_work_items(
        document=document,
        media_results=(bound,),
        active_items=(item,),
        loaded_outputs=(output,),
    )


def test_media_evidence_rejects_deferred_output_when_media_optional_is_off() -> None:
    assert settings.shared_document_media_optional is False
    source, document = _approved_source_and_document(include_figure=True)
    bound = _deferred_binding(source, document)
    unbound_payload = bound.model_dump(mode="json")
    for key in ("source_document_id", "source_document_revision", "source_document_hash"):
        unbound_payload.pop(key)
    unbound = DeferredFigureMediaResult.model_validate(unbound_payload)
    item = _work_item_for(unbound.model_dump(mode="json"))
    output = VerifiedWorkItemOutput(
        work_item_id=item.id,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )

    with pytest.raises(SharedLessonFinalizationError, match="SHARED_DOCUMENT_MEDIA_OPTIONAL"):
        _verify_media_matches_work_items(
            document=document,
            media_results=(bound,),
            active_items=(item,),
            loaded_outputs=(output,),
        )


def test_media_evidence_rejects_deferred_identity_mismatch_even_when_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "shared_document_media_optional", True)
    source, document = _approved_source_and_document(include_figure=True)
    bound = _deferred_binding(source, document)
    unbound_payload = bound.model_dump(mode="json")
    for key in ("source_document_id", "source_document_revision", "source_document_hash"):
        unbound_payload.pop(key)
    unbound = DeferredFigureMediaResult.model_validate(unbound_payload)
    item = _work_item_for(unbound.model_dump(mode="json"))
    output = VerifiedWorkItemOutput(
        work_item_id=item.id,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )
    forged = bound.model_copy(update={"reason_code": "media_invalid_output"})

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


def test_semantic_gate_rejects_forged_task_snapshot() -> None:
    source, document = _approved_source_and_document()
    forged_task = {
        "id": "task-1",
        "teaching_plan_id": source.id,
        "teaching_plan_revision": source.revision,
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
    }
    verified = _verified_semantic_inputs(source, tasks=(forged_task,))

    with pytest.raises(SharedLessonFinalizationError, match="verified durable semantic task"):
        _verify_semantic_inputs_match_request(
            request=_request(source, document),
            verified_inputs=verified,
        )


def test_semantic_gate_rejects_forged_source_projection() -> None:
    source, document = _approved_source_and_document()
    forged = SectionSource(id="forged-source", kind="approved_fact", text="Forged")

    with pytest.raises(SharedLessonFinalizationError, match="verified durable sourcebook"):
        _verify_semantic_inputs_match_request(
            request=_request(source, document, sources=(forged,)),
            verified_inputs=_verified_semantic_inputs(source),
        )


def test_semantic_gate_rejects_stale_sourcebook_output() -> None:
    source, document = _approved_source_and_document()
    verified = _verified_semantic_inputs(source)
    verified.sourcebook.entries.append(
        SourcebookEntry(
            id="forged-source",
            type="definition",
            purpose="Forged",
            content={"text": "Forged"},
        )
    )

    with pytest.raises(SharedLessonFinalizationError, match="verified sourcebook"):
        _verify_semantic_inputs_match_request(
            request=_request(source, document),
            verified_inputs=verified,
        )


def test_document_qa_gate_rejects_unlocked_work_item() -> None:
    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(id="writer-item", run_id="run-1")

    with pytest.raises(SharedLessonFinalizationError, match="locked active work items"):
        _verify_document_qa_matches_handoff(
            document=document,
            semantic_qa=request.handoff.semantic_qa,
            verified_qa=_verified_qa(request, "qa-item"),
            active_items=(item,),
        )


def test_document_qa_gate_rejects_missing_or_forged_evidence() -> None:
    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(id="qa-item", run_id="run-1")

    with pytest.raises(SharedLessonFinalizationError, match="invalid evidence"):
        _verify_document_qa_matches_handoff(
            document=document,
            semantic_qa=request.handoff.semantic_qa,
            verified_qa=None,
            active_items=(item,),
        )


def test_document_qa_gate_rejects_stale_result() -> None:
    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(id="qa-item", run_id="run-1")
    stale = request.handoff.semantic_qa.model_copy(update={"document_hash": "0" * 64})

    with pytest.raises(SharedLessonFinalizationError, match="stale"):
        _verify_document_qa_matches_handoff(
            document=document,
            semantic_qa=request.handoff.semantic_qa,
            verified_qa=VerifiedDocumentQA(
                work_item_id=item.id,
                output_hash="0" * 64,
                semantic_qa=stale,
            ),
            active_items=(item,),
        )


def test_document_qa_gate_rejects_non_pass_result() -> None:
    source, document = _approved_source_and_document()
    request = _request(source, document)
    item = GenerationWorkItemModel(id="qa-item", run_id="run-1")
    issue = request.handoff.semantic_qa.model_copy(update={"passed": False, "status": "issue"})

    with pytest.raises(SharedLessonFinalizationError, match="PASS verdict"):
        _verify_document_qa_matches_handoff(
            document=document,
            semantic_qa=request.handoff.semantic_qa,
            verified_qa=VerifiedDocumentQA(
                work_item_id=item.id,
                output_hash="0" * 64,
                semantic_qa=issue,
            ),
            active_items=(item,),
        )


def test_boundary_gate_accepts_current_passing_adjacent_boundary() -> None:
    source, document, verified_inputs, item = _boundary_fixture()

    _verify_boundary_coverage(
        source=source,
        document=document,
        verified_inputs=verified_inputs,
        active_items=(item,),
    )


def test_boundary_gate_accepts_section_with_advisory_writer_warnings() -> None:
    # Advisory shape warnings are part of the accepted writer output hash; the
    # finalizer must reproduce that hash from the persisted warnings.
    source, document, verified_inputs, item = _boundary_fixture(
        previous_warnings=(("length_over_target", "nodes[0].text/115/60"),)
    )

    _verify_boundary_coverage(
        source=source,
        document=document,
        verified_inputs=verified_inputs,
        active_items=(item,),
    )


def test_boundary_gate_rejects_missing_adjacent_boundary() -> None:
    source, document, verified_inputs, _item = _boundary_fixture()

    with pytest.raises(SharedLessonFinalizationError, match="missing"):
        _verify_boundary_coverage(
            source=source,
            document=document,
            verified_inputs=verified_inputs,
            active_items=(),
        )


def test_boundary_gate_rejects_stale_boundary_work_binding() -> None:
    source, document, verified_inputs, item = _boundary_fixture()
    forged_output = dict(item.output_json)
    forged_work = dict(forged_output["work"])
    forged_work["next_section_output_hash"] = "f" * 64
    forged_output["work"] = forged_work
    forged = GenerationWorkItemModel(
        id=item.id,
        run_id=item.run_id,
        item_key=item.item_key,
        stage=item.stage,
        status=item.status,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
        output_json=forged_output,
        output_hash=content_hash(forged_output),
    )

    with pytest.raises(SharedLessonFinalizationError, match="stale work identity"):
        _verify_boundary_coverage(
            source=source,
            document=document,
            verified_inputs=verified_inputs,
            active_items=(forged,),
        )


def test_boundary_gate_rejects_stale_current_section_hash() -> None:
    source, document, verified_inputs, item = _boundary_fixture()
    verified_inputs.section_hashes["s1"] = "f" * 64

    with pytest.raises(SharedLessonFinalizationError, match="stale hashes"):
        _verify_boundary_coverage(
            source=source,
            document=document,
            verified_inputs=verified_inputs,
            active_items=(item,),
        )


def test_boundary_gate_follows_replacement_chain_to_current_leaf() -> None:
    source, document, verified_inputs, item = _boundary_fixture()
    predecessor = GenerationWorkItemModel(
        id=item.id,
        run_id=item.run_id,
        item_key=item.item_key,
        stage=item.stage,
        status="failed",
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )
    replacement = GenerationWorkItemModel(
        id="boundary-replacement",
        run_id=item.run_id,
        item_key="boundary:s1->s2:replacement",
        stage=item.stage,
        status=item.status,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
        replaces_work_item_id=predecessor.id,
        output_json=item.output_json,
        output_hash=item.output_hash,
    )

    _verify_boundary_coverage(
        source=source,
        document=document,
        verified_inputs=verified_inputs,
        active_items=(replacement,),
        all_items=(predecessor, replacement),
    )


def test_boundary_gate_rejects_extra_active_boundary_pair() -> None:
    source, document = _approved_source_and_document()
    verified_inputs = _verified_inputs(document)
    extra = GenerationWorkItemModel(
        id="extra-boundary",
        run_id="run-1",
        item_key="boundary:section-1->section-2",
        stage=BOUNDARY_STAGE,
        status="ready",
        output_json={},
        output_hash=content_hash({}),
    )

    with pytest.raises(SharedLessonFinalizationError, match="extra"):
        _verify_boundary_coverage(
            source=source,
            document=document,
            verified_inputs=verified_inputs,
            active_items=(extra,),
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
    from document.shared_lesson import finalizer

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

    async def fake_semantic_inputs(*_args, **_kwargs):
        return _verified_semantic_inputs(source)

    async def fake_document_qa(*_args, **_kwargs):
        return _verified_qa(request, item.id)

    async def fake_save(*_args, **_kwargs):
        writes.append("draft")

    async def fake_promote(*_args, **_kwargs):
        writes.append("ready")
        raise RuntimeError("simulated finalization conflict")

    monkeypatch.setattr(finalizer, "_load_and_lock_run", lambda *a, **k: _locked(run, item))
    monkeypatch.setattr(finalizer, "load_verified_semantic_inputs", fake_semantic_inputs)
    monkeypatch.setattr(finalizer, "load_verified_shared_lesson_inputs", fake_inputs)
    monkeypatch.setattr(finalizer, "load_verified_document_qa", fake_document_qa)
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
    from document.shared_lesson import finalizer

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

    async def fake_semantic_inputs(*_args, **_kwargs):
        return _verified_semantic_inputs(source)

    async def fake_document_qa(*_args, **_kwargs):
        return _verified_qa(request, item.id)

    async def fake_save(*_args, **_kwargs):
        return SimpleNamespace(status="draft")

    async def fake_promote(*_args, **_kwargs):
        return SimpleNamespace(status="ready")

    async def fake_finalize(*_args, **_kwargs):
        return run

    monkeypatch.setattr(finalizer, "_load_and_lock_run", lambda *a, **k: _locked(run, item))
    monkeypatch.setattr(finalizer, "load_verified_semantic_inputs", fake_semantic_inputs)
    monkeypatch.setattr(finalizer, "load_verified_shared_lesson_inputs", fake_inputs)
    monkeypatch.setattr(finalizer, "load_verified_document_qa", fake_document_qa)
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

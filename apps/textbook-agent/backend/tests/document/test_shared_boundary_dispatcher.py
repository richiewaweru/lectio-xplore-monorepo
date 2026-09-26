from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_composer_admission import _verifier
from test_shared_writer_admission import _seed_ready_composer_run

from document.shared_lesson import boundary_dispatcher
from document.shared_lesson.boundary import BoundarySemanticVerdict, ContinuityIssue
from document.shared_lesson.writer import validate_and_build_section
from document.shared_lesson.writer_admission import admit_writer_work_items
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash


async def _ready_writers(db_session, owner, run_id, source):
    admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    for admission in admissions:
        section = admission.section
        unique_opening = (
            "A compass uses magnetic forces to point north across a landscape. Travelers can navigate safely."
            if section.slot_id == "orient"
            else "A microscope magnifies tiny structures inside a sample. Scientists compare each observation carefully."
        )
        text = (
            f"{unique_opening} "
            + ". ".join(
                [
                    *section.entry_state,
                    *section.must_establish,
                    *([section.bridge_from_previous] if section.bridge_from_previous else []),
                    *section.exit_state,
                ]
            )
            + "."
        )
        draft = {
            "nodes": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "teaching_block_id": item.teaching_block_id,
                    "accessibility": {"description": "A clear explanation."},
                    "display": {"text": text},
                }
                for item in admission.request.composition_plan.items
                if item.kind == "paragraph"
            ]
        }
        output = validate_and_build_section(request=admission.request, draft=draft)
        item = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert item is not None
        payload = output.model_dump(mode="json")
        item.status = "ready"
        item.output_json = payload
        item.output_hash = content_hash(payload)
    await db_session.commit()
    return admissions


def _patch_approved_source(monkeypatch, source):
    async def load(**_kwargs):
        return source

    monkeypatch.setattr(boundary_dispatcher, "load_current_approved_teaching_plan_source", load)
    monkeypatch.setattr(
        boundary_dispatcher, "make_approved_source_verifier", lambda **_kw: _verifier
    )


async def _set_preparation_generation(db_session):
    from infra.database.models import PathLessonModel

    lesson = await db_session.get(PathLessonModel, "composer-admission-lesson")
    assert lesson is not None
    lesson.pack_id = "boundary-test-preparation"
    await db_session.commit()


async def _pass(_request):
    return BoundarySemanticVerdict(status="pass")


async def _issue(request):
    return BoundarySemanticVerdict(
        status="issue",
        issue=ContinuityIssue(
            issue_code="boundary_test_issue",
            affected_section_id=request.next_plan.slot_id,
            explanation="The example needs a clearer connection.",
            required_correction="Clarify the connection in the next section.",
        ),
    )


@pytest.mark.asyncio
async def test_dispatch_admits_and_passes_adjacent_boundaries_on_same_run(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_pass,
    )
    assert result.state == "passed", result
    assert len(result.admitted_work_item_ids) == 1
    row = await db_session.get(GenerationWorkItemModel, result.admitted_work_item_ids[0])
    assert row is not None and row.run_id == run_id and row.status == "ready"


@pytest.mark.asyncio
async def test_boundary_aggregate_deadline_fails_recoverably_before_lease_expiry(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)
    provider_cancelled = asyncio.Event()

    async def slow_semantic_review(_request):
        try:
            await asyncio.sleep(2)
        finally:
            provider_cancelled.set()
        return BoundarySemanticVerdict(status="pass")

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=slow_semantic_review,
        lease_seconds=1,
    )

    assert result.state == "pending_repair"
    assert len(result.pending_repair_work_item_ids) == 1
    assert result.outcomes[0].error_code == "boundary_validation_timeout"
    assert provider_cancelled.is_set()
    boundary = await db_session.get(
        GenerationWorkItemModel, result.pending_repair_work_item_ids[0]
    )
    assert boundary is not None and boundary.status == "failed_recoverable"
    for admission in admissions:
        writer = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert writer is not None and writer.status == "ready"


@pytest.mark.asyncio
@pytest.mark.parametrize("writer_state", ["missing", "queued", "stale"])
async def test_missing_or_nonready_writer_blocks_boundary_admission(
    db_session, db_session_factory, monkeypatch, writer_state
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    first_writer = await db_session.get(GenerationWorkItemModel, admissions[0].work_item_id)
    assert first_writer is not None
    if writer_state == "missing":
        await db_session.delete(first_writer)
    elif writer_state == "stale":
        first_writer.status = "ready"
        first_writer.output_json = {"invalid": "stale writer output"}
        first_writer.output_hash = content_hash(first_writer.output_json)
    await db_session.commit()
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )

    assert result.state == "blocked"
    boundary_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "continuity_validation",
                )
            )
        ).all()
    )
    assert boundary_rows == []
    for admission in admissions[1:]:
        row = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert row is not None and row.status == "queued"


@pytest.mark.asyncio
async def test_duplicate_dispatch_reuses_ready_boundary_identity(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    first = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )
    second = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )

    assert first.state == second.state == "passed", (first, second)
    assert first.admitted_work_item_ids == second.admitted_work_item_ids


@pytest.mark.asyncio
async def test_one_section_plan_returns_without_admitting_a_boundary(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    first_plan_section = source.plan.sections[0]
    one_section_source = source.model_copy(
        update={"plan": source.plan.model_copy(update={"sections": (first_plan_section,)})}
    )
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None

    async def verified(_session, **_kwargs):
        from document.shared_lesson.models import SharedSection

        return (
            one_section_source,
            SimpleNamespace(id=run.id),
            (
                SharedSection(
                    id=first_plan_section.slot_id,
                    title=first_plan_section.display_title,
                    position=0,
                    nodes=(),
                ),
            ),
            {},
            {},
        )

    monkeypatch.setattr(boundary_dispatcher, "_verified_run_inputs", verified)
    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner
    )
    assert result.state == "no_boundaries"
    assert result.admitted_work_item_ids == ()


@pytest.mark.asyncio
async def test_boundary_failure_is_pending_repair_and_preserves_ready_writers(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_issue,
    )

    assert result.state == "pending_repair"
    assert len(result.pending_repair_work_item_ids) == 1
    for admission in admissions:
        writer = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert writer is not None and writer.status == "ready"

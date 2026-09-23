"""P03 native realization identity gates."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture

from application.unit_lesson.realization_contracts import (
    DEFAULT_VARIANT_ID,
    LEGACY_AMBIGUOUS_VARIANT,
    canonical_hash,
    package_contract_for,
    policy_for,
)
from application.unit_lesson.realizations import (
    RealizationAdmissionError,
    RealizationReadOnlyError,
    backfill_legacy_realization,
    classify_legacy_chunked,
    list_realizations_for_lesson,
    mark_stale_for_policy_change,
    mark_stale_for_teaching_change,
    persisted_path_is_stable,
    request_outputs,
    resolve_by_path,
    retry_realization,
    to_identity,
)
from application.unit_lesson.realize_print_handoff import (
    realize_print_from_preparation,
    retry_print_realization,
)
from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    NativeRealizationModel,
    PathLessonModel,
    UserModel,
)
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from curriculum.workspace_projection import project_lesson_workspace
from print.generation.whole_lesson.repository import (
    PAGE_DOCUMENT_KEY,
    PageDocumentRepository,
    claim_next_native_job,
    empty_page_document_state,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _prepared_lesson(db_session: AsyncSession, *, user_id: str) -> PathLessonModel:
    user = UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id)
    db_session.add(user)
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None
    # Shared preparation link (legacy pack_id) — not a path discriminator.
    prep_id = f"prep-{user_id}"
    db_session.add(
        GenerationModel(
            id=prep_id,
            user_id=user.id,
            subject="science",
            context="shared prep",
            status="awaiting_review",
            requested_template_id="lesson",
            requested_preset_id="standard",
            created_at=_utcnow(),
            chunked_state_json={
                "shared_preparation": True,
                "stage": "awaiting_review",
                "teaching_plan_id": f"tp-{user_id}",
                "teaching_review": {"approved_revision": 1, "status": "approved"},
                "teaching_plan": {
                    "teaching_plan_id": f"tp-{user_id}",
                    "revision": 1,
                    "preparation_hash": "hash-rev-1",
                    "arc": "build",
                    "sections": [],
                },
            },
        )
    )
    lesson.pack_id = prep_id
    await db_session.flush()
    return lesson


async def _approved_native_preparation(
    db_session: AsyncSession, *, user_id: str, approved: bool = True
) -> tuple[PathLessonModel, TeachingPlan, dict, dict]:
    lesson = await _prepared_lesson(db_session, user_id=user_id)
    plan = TeachingPlan(
        teaching_plan_id=f"tp-{user_id}",
        revision=1,
        preparation_hash=f"input-{user_id}",
        arc="Trace how water moves through a plant.",
        sections=[
            {
                "slot_id": "orient",
                "specific_purpose": "Connect an observation to the investigation.",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a covered leaf.",
                        "evidence": "A relevant observation.",
                    }
                ],
            }
        ],
    )
    state = empty_page_document_state()
    revisions = TeachingRevisionStore(state)
    revisions.record_draft(
        plan,
        preparation_hash=str(plan.preparation_hash),
        revision=1,
    )
    if approved:
        revisions.approve(
            expected_revision=1,
            expected_content_hash=teaching_plan_content_hash(plan),
            reviewed_by=user_id,
            teacher_note="Approved fixture",
        )
    state["lesson_packet"] = {
        "lesson": {"path_lesson_id": lesson.id, "objective": "Fixture objective"},
        "approved_items": [],
    }
    state["lesson_legality"] = {"resource_id": "lesson", "catalogue_hash": "fixture"}
    # Simulate a legacy preparation which already contains Print-only state.
    state["form_plan"] = {"legacy_output": "old form"}
    state["form_validation"] = {"legacy_output": True}
    state["block_execution"] = {"old-block": {"status": "ready"}}
    state["execution"] = {
        "worker_id": "old-print-worker",
        "lease_token": 8,
        "attempt": 5,
        "last_error": {"message": "legacy output failure"},
        "work_kind": "post_approval_execution",
    }
    generation = await db_session.get(GenerationModel, lesson.pack_id)
    assert generation is not None
    generation.status = "ready" if approved else "awaiting_teaching_approval"
    generation.document_json = {"document_version": 2, "title": "Legacy Print output"}
    source_chunked = {
        "stage": "ready",
        "page_document_v2": state,
        "native_whole_lesson": True,
        "context": {"path_lesson_id": lesson.id, "subject": "Science"},
        "structural_plan": {"lesson_intent": {"goal": "Fixture objective"}},
        "smart_lesson": {
            "teaching_plan_hash": teaching_plan_content_hash(plan),
            "lesson_sourcebook": {"source": "immutable shared semantic input"},
            "shared_tasks": [],
        },
        "checkpoint_store": {"old-print-checkpoint": True},
        "call_budget_ledger": {"legacy": 18},
        "progress_store": {"legacy-output": True},
        "visual_topology_v1": {"legacy-visual": True},
    }
    generation.chunked_state_json = source_chunked
    await db_session.flush()
    return lesson, plan, source_chunked, generation.document_json


@pytest.mark.asyncio
async def test_p03_r01_dual_outputs_idempotent(db_session: AsyncSession) -> None:
    """P03-R01: one lesson creates both outputs; duplicates reuse rows."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r01")
    first = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r01",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert len(first) == 2
    assert all(created for _, created in first)
    print_row, learn_row = first[0][0], first[1][0]
    assert print_row.path == "print"
    assert learn_row.path == "learn"
    assert print_row.id != learn_row.id
    assert print_row.teaching_plan_revision == learn_row.teaching_plan_revision == 1

    second = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r01",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert all(not created for _, created in second)
    assert second[0][0].id == print_row.id
    assert second[1][0].id == learn_row.id
    count = await db_session.scalar(
        select(func.count()).select_from(NativeRealizationModel).where(
            NativeRealizationModel.path_lesson_id == lesson.id,
            NativeRealizationModel.variant_id == DEFAULT_VARIANT_ID,
        )
    )
    assert count == 2


@pytest.mark.asyncio
async def test_p03_r02_print_retry_leaves_learn_and_plan(db_session: AsyncSession) -> None:
    """P03-R02: Print retry does not change Learn output or shared plan pins."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r02")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r02",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    print_row, learn_row = rows[0][0], rows[1][0]
    print_row.output_id = "print-out-1"
    print_row.status = "ready"
    learn_row.output_id = "learn-out-1"
    learn_row.status = "ready"
    await db_session.flush()

    learn_before = (
        learn_row.id,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_id,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
        learn_row.status,
    )
    shared_before = (
        print_row.teaching_plan_id,
        print_row.teaching_plan_revision,
        print_row.teaching_plan_hash,
    )

    retried = await retry_realization(db_session, realization_id=print_row.id, new_output_id="print-out-2")
    await db_session.refresh(learn_row)

    assert retried.output_id == "print-out-2"
    assert retried.realization_revision == 2
    assert retried.path == "print"
    assert (
        retried.teaching_plan_id,
        retried.teaching_plan_revision,
        retried.teaching_plan_hash,
    ) == shared_before
    assert (
        learn_row.id,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_id,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
        learn_row.status,
    ) == learn_before

    # Inverse: Learn retry leaves Print untouched.
    print_snapshot = (
        retried.output_id,
        retried.realization_revision,
        retried.teaching_plan_hash,
    )
    learn_retried = await retry_realization(
        db_session, realization_id=learn_row.id, new_output_id="learn-out-2"
    )
    await db_session.refresh(retried)
    assert learn_retried.output_id == "learn-out-2"
    assert (
        retried.output_id,
        retried.realization_revision,
        retried.teaching_plan_hash,
    ) == print_snapshot


@pytest.mark.asyncio
async def test_p03_r02b_print_retry_without_override_keeps_preparation_output(
    db_session: AsyncSession,
) -> None:
    """Print retries cannot silently fall back to the shared preparation id."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r02b")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id="tp-p03-r02b",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    row = rows[0][0]
    row.status = "failed_recoverable"
    row.error_summary = "retryable print failure"
    await db_session.flush()

    with pytest.raises(RealizationAdmissionError, match="newly created detached output"):
        await retry_realization(db_session, realization_id=row.id)
    assert row.output_id is None
    assert row.status == "failed_recoverable"
    assert row.realization_revision == 1


@pytest.mark.asyncio
async def test_p03_detached_print_output_is_idempotent_and_failure_retry_isolated(
    db_session: AsyncSession,
) -> None:
    lesson, plan, source_chunked, _source_document = await _approved_native_preparation(
        db_session, user_id="p03-detached-print"
    )
    preparation_id = str(lesson.pack_id)
    source_generation = await db_session.get(GenerationModel, preparation_id)
    assert source_generation is not None
    source_outer = dict(source_generation.chunked_state_json)
    source_outer["context"] = {
        "shared_preparation": True,
        "path_prepared": True,
        "native_whole_lesson": True,
    }
    source_generation.chunked_state_json = source_outer
    source_status = source_generation.status
    source_snapshot = dict(source_generation.chunked_state_json)
    source_document_snapshot = dict(source_generation.document_json or {})

    first = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=preparation_id,
        user_id="p03-detached-print",
        path_lesson_id=lesson.id,
        admission_request_key="create-print-once",
    )
    print_row = await db_session.get(NativeRealizationModel, first["realization_id"])
    assert print_row is not None
    output_id = str(first["output_id"])
    assert output_id != preparation_id
    assert print_row.output_id == output_id
    assert print_row.preparation_generation_id == preparation_id
    assert print_row.pack_id is None
    assert first["open_href"] == f"/studio/print/{output_id}"

    output = await db_session.get(GenerationModel, output_id)
    assert output is not None
    assert output.status == "queued"
    output_context = output.chunked_state_json["context"]
    assert output_context["native_whole_lesson"] is True
    assert output_context["requested_realization_path"] == "print"
    assert output_context["preparation_generation_id"] == preparation_id
    assert "shared_preparation" not in output_context
    assert "path_prepared" not in output_context
    from print.http.v3_studio.router import _normalize_chunked_state

    output_status = _normalize_chunked_state(output_id, output.chunked_state_json)
    assert output_status.requested_realization_path == "print"
    assert source_snapshot["context"]["shared_preparation"] is True
    assert output.document_json is None
    assert output.pack_id is None
    output_page = (output.chunked_state_json or {}).get(PAGE_DOCUMENT_KEY) or {}
    assert teaching_plan_content_hash(output_page["teaching_plan"]) == print_row.teaching_plan_hash
    assert output_page["teaching_plan"]["revision"] == 1
    assert output_page["teaching_review"]["approved_revision"] == 1
    assert output_page["teaching_revisions"][0]["status"] == "approved"
    assert output_page["lesson_packet"] == source_chunked[PAGE_DOCUMENT_KEY]["lesson_packet"]
    assert output_page["lesson_legality"] == source_chunked[PAGE_DOCUMENT_KEY]["lesson_legality"]
    assert output_page["form_plan"] is None
    assert output_page["block_execution"] == {}
    assert output_page["execution"]["worker_id"] is None
    assert "visual_topology_v1" not in output.chunked_state_json
    assert "checkpoint_store" not in output.chunked_state_json
    assert "call_budget_ledger" not in output.chunked_state_json
    assert "progress_store" not in output.chunked_state_json

    repeated = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=preparation_id,
        user_id="p03-detached-print",
        path_lesson_id=lesson.id,
        admission_request_key="create-print-once",
    )
    assert repeated["realization_id"] == first["realization_id"]
    assert repeated["output_id"] == output_id
    assert await db_session.scalar(
        select(func.count()).select_from(GenerationModel).where(GenerationModel.id == output_id)
    ) == 1

    learn_rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["learn"],
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=1,
        teaching_plan_hash=teaching_plan_content_hash(plan),
        preparation_generation_id=preparation_id,
        pack_id=None,
    )
    learn_row = learn_rows[0][0]
    learn_row.output_id = "learn-output-stable"
    learn_row.status = "ready"
    await db_session.flush()
    learn_before = (
        learn_row.id,
        learn_row.output_id,
        learn_row.status,
        learn_row.realization_revision,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
    )

    lease = await claim_next_native_job(
        db_session, worker_id="detached-print-worker"
    )
    assert lease is not None
    assert lease.generation_id == output_id
    await db_session.refresh(print_row)
    assert print_row.status == "running"

    output.document_json = {"document_version": 2, "title": "Retained failed Print snapshot"}
    await PageDocumentRepository(db_session, output_id).persist_native_failure(
        exc=TimeoutError("temporary provider timeout"),
        stage="planning_forms",
        event="worker_failure",
        attempt=1,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        expected={"planning_forms"},
    )
    await db_session.refresh(print_row)
    assert print_row.status == "failed_recoverable"
    assert "timeout" in str(print_row.error_summary).lower()

    preparation_page = source_snapshot[PAGE_DOCUMENT_KEY]
    pinned_approval_before = (
        preparation_page["teaching_review"],
        preparation_page["teaching_revisions"],
        preparation_page["teaching_plan"],
    )
    retried = await retry_print_realization(
        db_session,
        realization_id=print_row.id,
        user_id="p03-detached-print",
    )
    assert retried["output_id"] != output_id
    assert retried["output_id"] != preparation_id
    assert retried["realization_revision"] == 2
    assert retried["teaching_plan_revision"] == 1
    await db_session.refresh(print_row)
    assert print_row.output_id == retried["output_id"]
    assert print_row.realization_revision == 2
    assert print_row.teaching_plan_revision == 1
    assert print_row.status == "queued"
    old_output = await db_session.get(GenerationModel, output_id)
    new_output = await db_session.get(GenerationModel, retried["output_id"])
    assert old_output is not None
    assert old_output.document_json == {
        "document_version": 2,
        "title": "Retained failed Print snapshot",
    }
    assert new_output is not None
    assert new_output.status == "queued"

    await db_session.refresh(source_generation)
    assert source_generation.status == source_status
    assert source_generation.chunked_state_json == source_snapshot
    assert source_generation.document_json == source_document_snapshot
    source_review_after = source_generation.chunked_state_json[PAGE_DOCUMENT_KEY]["teaching_review"]
    source_revisions_after = source_generation.chunked_state_json[PAGE_DOCUMENT_KEY]["teaching_revisions"]
    source_plan_after = source_generation.chunked_state_json[PAGE_DOCUMENT_KEY]["teaching_plan"]
    assert (source_review_after, source_revisions_after, source_plan_after) == pinned_approval_before
    await db_session.refresh(learn_row)
    assert (
        learn_row.id,
        learn_row.output_id,
        learn_row.status,
        learn_row.realization_revision,
        learn_row.teaching_plan_revision,
        learn_row.teaching_plan_hash,
    ) == learn_before


@pytest.mark.asyncio
async def test_p07_detached_print_export_failure_preserves_approval_and_ready_learn(
    db_session: AsyncSession,
) -> None:
    lesson, plan, source_state, _source_document = await _approved_native_preparation(
        db_session, user_id="p07-print-export-failure"
    )
    preparation_id = str(lesson.pack_id)
    source = await db_session.get(GenerationModel, preparation_id)
    assert source is not None
    source_status = source.status
    source_chunked = dict(source.chunked_state_json or {})
    source_document_snapshot = dict(source.document_json or {})

    admitted = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=preparation_id,
        user_id="p07-print-export-failure",
        path_lesson_id=lesson.id,
    )
    print_row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert print_row is not None
    learn_rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["learn"],
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=admitted["teaching_plan_hash"],
        preparation_generation_id=preparation_id,
    )
    learn_row = learn_rows[0][0]
    learn_row.status = "ready"
    learn_row.output_id = "p07-ready-learn-sibling"
    learn_before = (
        learn_row.status,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_hash,
    )

    lease = await claim_next_native_job(db_session, worker_id="p07-print-renderer")
    assert lease is not None and lease.generation_id == admitted["output_id"]
    await PageDocumentRepository(db_session, admitted["output_id"]).persist_native_failure(
        exc=TimeoutError("controlled PDF export timeout"),
        stage="exporting",
        event="print_export_failure",
        attempt=1,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        expected={"planning_forms"},
    )

    await db_session.refresh(print_row)
    await db_session.refresh(learn_row)
    await db_session.refresh(source)
    failed_output = await db_session.get(GenerationModel, admitted["output_id"])
    assert print_row.status == "failed_recoverable"
    assert print_row.output_id == admitted["output_id"]
    assert failed_output is not None and failed_output.status == "failed_recoverable"
    assert "timeout" in str(failed_output.error).lower()
    assert (
        learn_row.status,
        learn_row.output_id,
        learn_row.realization_revision,
        learn_row.teaching_plan_hash,
    ) == learn_before
    assert source.status == source_status
    assert source.chunked_state_json == source_chunked
    assert source.document_json == source_document_snapshot
    assert (source_state[PAGE_DOCUMENT_KEY]["teaching_review"]["approved_revision"]) == 1

    projection = project_lesson_workspace(
        generation_id=preparation_id,
        state=source_state[PAGE_DOCUMENT_KEY],
        generation_status=source.status,
        workflow_stage="approved",
        learn_realization={
            "realization_id": learn_row.id,
            "path": "learn",
            "status": learn_row.status,
            "output_id": learn_row.output_id,
        },
        print_realization={
            "realization_id": print_row.id,
            "path": "print",
            "status": print_row.status,
            "output_id": print_row.output_id,
            "error_summary": print_row.error_summary,
            "error_detail": {
                "code": "TIMEOUT",
                "failure_class": "timeout",
                "retryable": True,
            },
        },
    )
    assert projection.preparation.state == "approved"
    assert projection.learn.state == "ready"
    assert projection.print.state == "failed_recoverable"


@pytest.mark.asyncio
async def test_p03_old_print_completion_does_not_resurrect_stale_realization(
    db_session: AsyncSession,
) -> None:
    lesson, _, _, _ = await _approved_native_preparation(
        db_session, user_id="p03-stale-print-output"
    )
    admitted = await realize_print_from_preparation(
        db_session,
        path_lesson_id=lesson.id,
        preparation_generation_id=lesson.pack_id,
        user_id="p03-stale-print-output",
    )
    realization = await db_session.get(
        NativeRealizationModel, admitted["realization_id"]
    )
    assert realization is not None
    realization.status = "stale"
    await db_session.flush()

    def complete_old_output(generation: GenerationModel, state: dict) -> None:
        generation.status = "ready"
        generation.document_json = {"document_version": 2, "title": "Old output"}

    await PageDocumentRepository(db_session, admitted["output_id"]).mutate_state(
        mutation=complete_old_output
    )
    await db_session.refresh(realization)
    assert realization.status == "stale"


@pytest.mark.asyncio
async def test_p03_existing_print_output_pointer_must_match_pinned_identity(
    db_session: AsyncSession,
) -> None:
    lesson, _, _, _ = await _approved_native_preparation(
        db_session, user_id="p03-print-pointer-identity"
    )
    created = await realize_print_from_preparation(
        db_session,
        path_lesson_id=lesson.id,
        preparation_generation_id=lesson.pack_id,
        user_id="p03-print-pointer-identity",
    )
    output = await db_session.get(GenerationModel, created["output_id"])
    assert output is not None
    corrupt = dict(output.chunked_state_json)
    metadata = dict(corrupt["print_realization"])
    metadata["teaching_plan_hash"] = "stale-or-corrupt-hash"
    corrupt["print_realization"] = metadata
    output.chunked_state_json = corrupt
    await db_session.flush()

    with pytest.raises(HTTPException) as error:
        await realize_print_from_preparation(
            db_session,
            path_lesson_id=lesson.id,
            preparation_generation_id=lesson.pack_id,
            user_id="p03-print-pointer-identity",
        )

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "PRINT_OUTPUT_IDENTITY_CONFLICT"


@pytest.mark.asyncio
async def test_p03_ready_print_artifact_resolves_through_its_owned_output(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id = "p03-ready-print-output"
    async with db_session_factory() as session:
        lesson, _, _, _ = await _approved_native_preparation(session, user_id=user_id)
        preparation_id = str(lesson.pack_id)
        admitted = await realize_print_from_preparation(
            session,
            path_lesson_id=lesson.id,
            preparation_generation_id=preparation_id,
            user_id=user_id,
        )
        output_id = str(admitted["output_id"])

        def complete_output(generation: GenerationModel, state: dict) -> None:
            generation.status = "ready"
            generation.document_json = {
                "document_version": 2,
                "title": "Detached ready Print artifact",
                "sections": [],
            }

        await PageDocumentRepository(session, output_id).mutate_state(
            mutation=complete_output
        )
        row = await session.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "ready"
        assert row.output_id == output_id
        source = await session.get(GenerationModel, preparation_id)
        assert source is not None
        source_page = source.chunked_state_json[PAGE_DOCUMENT_KEY]
        assert source_page["teaching_review"]["status"] == "approved"
        assert source_page["teaching_review"]["approved_revision"] == 1

    from print.http.v3_studio.generation_writer import V3GenerationWriter

    writer = V3GenerationWriter(db_session_factory)
    owned_document = await writer.get_document_json(output_id, user_id)
    assert owned_document is not None
    assert owned_document["title"] == "Detached ready Print artifact"
    assert await writer.get_document_json(output_id, "another-user") is None


@pytest.mark.asyncio
async def test_p03_print_approval_route_approves_source_and_returns_output_id(
    db_session_factory, monkeypatch
) -> None:
    import json
    from unittest.mock import AsyncMock

    import print.http.v3_studio.router as studio_router
    from core.entities.user import User

    async with db_session_factory() as setup:
        lesson, plan, _chunked, _document = await _approved_native_preparation(
            setup, user_id="p03-print-approval-route", approved=False
        )
        generation = await setup.get(GenerationModel, lesson.pack_id)
        assert generation is not None
        generation_id = generation.id
        await setup.commit()

    monkeypatch.setattr(studio_router, "async_session_factory", db_session_factory)
    monkeypatch.setattr(
        studio_router, "_load_owned_generation", AsyncMock(return_value=generation)
    )
    teacher = User(
        id="p03-print-approval-route",
        email="p03-print-approval-route@example.invalid",
        name="Teacher",
        created_at="2026-09-23T00:00:00Z",
        updated_at="2026-09-23T00:00:00Z",
    )
    response = await studio_router.post_lesson_approach_approve(
        generation_id,
        studio_router.LessonApproachApproveRequest(
            expected_revision=1,
            expected_content_hash=teaching_plan_content_hash(plan),
            teacher_note="Approved",
        ),
        teacher,
        path="print",
    )
    payload = json.loads(response.body)
    assert response.status_code == 202
    assert payload["path"] == "print"
    assert payload["preparation_generation_id"] == generation_id
    assert payload["output_id"] != generation_id
    assert payload["generation_id"] == payload["output_id"]

    async with db_session_factory() as verify:
        source = await verify.get(GenerationModel, generation_id)
        output = await verify.get(GenerationModel, payload["output_id"])
        realization = await verify.get(NativeRealizationModel, payload["realization_id"])
        assert source is not None and output is not None and realization is not None
        assert source.status == "awaiting_teaching_approval"
        source_state = (source.chunked_state_json or {})[PAGE_DOCUMENT_KEY]
        assert source_state["teaching_review"]["approved_revision"] == 1
        assert output.status == "queued"
        assert realization.output_id == output.id
        assert realization.preparation_generation_id == source.id


@pytest.mark.asyncio
async def test_p03_retry_pins_superseded_approved_snapshot_as_output_approval(
    db_session: AsyncSession,
) -> None:
    lesson, plan, _chunked, _document = await _approved_native_preparation(
        db_session, user_id="p03-retry-superseded"
    )
    preparation_id = str(lesson.pack_id)
    first = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=preparation_id,
        user_id="p03-retry-superseded",
        path_lesson_id=lesson.id,
    )
    realization = await db_session.get(NativeRealizationModel, first["realization_id"])
    source = await db_session.get(GenerationModel, preparation_id)
    old_output = await db_session.get(GenerationModel, first["output_id"])
    assert realization is not None and source is not None and old_output is not None
    source_state = dict((source.chunked_state_json or {})[PAGE_DOCUMENT_KEY])
    store = TeachingRevisionStore(source_state)
    plan2 = plan.model_copy(update={"arc": "Trace how water travels from roots to leaves."})
    store.edit_plan(plan2, preparation_hash=str(plan.preparation_hash))
    store.approve(
        expected_revision=2,
        expected_content_hash=teaching_plan_content_hash(plan2),
        reviewed_by="p03-retry-superseded",
        teacher_note="Approved revised draft",
    )
    source.chunked_state_json = {
        **(source.chunked_state_json or {}),
        PAGE_DOCUMENT_KEY: source_state,
    }
    realization.status = "failed_recoverable"
    old_output.status = "failed_recoverable"
    old_output.error = "temporary failure"
    await db_session.flush()
    assert source_state["teaching_review"]["approved_revision"] == 2
    assert next(
        row for row in source_state["teaching_revisions"] if row["revision"] == 1
    )["status"] == "superseded"

    retried = await retry_print_realization(
        db_session,
        realization_id=realization.id,
        user_id="p03-retry-superseded",
    )
    new_output = await db_session.get(GenerationModel, retried["output_id"])
    assert new_output is not None
    output_state = (new_output.chunked_state_json or {})[PAGE_DOCUMENT_KEY]
    assert output_state["teaching_plan"]["revision"] == 1
    assert output_state["teaching_review"]["approved_revision"] == 1
    assert output_state["teaching_revisions"][0]["revision"] == 1
    assert output_state["teaching_revisions"][0]["status"] == "approved"
    assert teaching_plan_content_hash(output_state["teaching_plan"]) == realization.teaching_plan_hash

    await db_session.refresh(source)
    current_source_state = (source.chunked_state_json or {})[PAGE_DOCUMENT_KEY]
    assert current_source_state["teaching_review"]["approved_revision"] == 2
    assert next(
        row for row in current_source_state["teaching_revisions"] if row["revision"] == 1
    )["status"] == "superseded"


@pytest.mark.asyncio
async def test_p03_concurrent_print_retry_accepts_one_new_output(
    db_session_factory,
) -> None:
    preparation_id = ""
    realization_id = ""
    old_output_id = ""
    async with db_session_factory() as setup:
        lesson, _plan, _chunked, _document = await _approved_native_preparation(
            setup, user_id="p03-concurrent-retry"
        )
        preparation_id = str(lesson.pack_id)
        result = await realize_print_from_preparation(
            setup,
            preparation_generation_id=preparation_id,
            user_id="p03-concurrent-retry",
            path_lesson_id=lesson.id,
        )
        realization_id = str(result["realization_id"])
        old_output_id = str(result["output_id"])
        row = await setup.get(NativeRealizationModel, realization_id)
        output = await setup.get(GenerationModel, old_output_id)
        assert row is not None and output is not None
        row.status = "failed_recoverable"
        row.error_summary = "temporary failure"
        output.status = "failed_recoverable"
        await setup.commit()

    async def _attempt_retry() -> tuple[str, object]:
        async with db_session_factory() as session:
            try:
                result = await retry_print_realization(
                    session,
                    realization_id=realization_id,
                    user_id="p03-concurrent-retry",
                )
                await session.commit()
                return ("accepted", result)
            except HTTPException as exc:
                await session.rollback()
                return ("conflict", exc.detail)

    outcomes = await asyncio.gather(_attempt_retry(), _attempt_retry())
    assert sorted(outcome for outcome, _ in outcomes) == ["accepted", "conflict"]
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, realization_id)
        assert row is not None
        assert row.realization_revision == 2
        assert row.teaching_plan_revision == 1
        assert row.status == "queued"
        assert row.output_id != old_output_id
        generations = await verify.scalars(
            select(GenerationModel).where(GenerationModel.user_id == "p03-concurrent-retry")
        )
        detached = [
            generation
            for generation in generations.all()
            if (generation.chunked_state_json or {}).get("print_realization", {}).get(
                "realization_id"
            )
            == realization_id
        ]
        assert {generation.id for generation in detached} == {old_output_id, row.output_id}


@pytest.mark.asyncio
async def test_p03_standalone_studio_print_approval_creates_distinct_output(
    db_session_factory, monkeypatch
) -> None:
    import json
    from unittest.mock import AsyncMock

    import print.http.v3_studio.router as studio_router
    from core.entities.user import User

    user_id = "p03-standalone-studio"
    plan = TeachingPlan(
        teaching_plan_id="tp-p03-standalone",
        revision=1,
        preparation_hash="standalone-input",
        arc="Trace water through the plant.",
        sections=[
            {
                "slot_id": "orient",
                "specific_purpose": "Observe water movement.",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a leaf.",
                        "evidence": "A relevant observation.",
                    }
                ],
            }
        ],
    )
    state = empty_page_document_state()
    TeachingRevisionStore(state).record_draft(
        plan,
        preparation_hash="standalone-input",
        revision=1,
    )
    state["lesson_packet"] = {"lesson": {"objective": "Standalone objective"}}
    state["lesson_legality"] = {"resource_id": "lesson", "catalogue_hash": "fixture"}
    async with db_session_factory() as setup:
        setup.add(UserModel(id=user_id, email=f"{user_id}@example.invalid", name="Teacher"))
        source = GenerationModel(
            id="p03-standalone-preparation",
            user_id=user_id,
            subject="Science",
            context="Standalone Studio lesson",
            status="awaiting_teaching_approval",
            requested_template_id="lesson",
            requested_preset_id="default",
            chunked_state_json={
                "page_document_v2": state,
                "stage": "awaiting_teaching_approval",
                "native_whole_lesson": True,
            },
        )
        setup.add(source)
        await setup.commit()

    monkeypatch.setattr(studio_router, "async_session_factory", db_session_factory)
    monkeypatch.setattr(
        studio_router, "_load_owned_generation", AsyncMock(return_value=source)
    )
    teacher = User(
        id=user_id,
        email=f"{user_id}@example.invalid",
        name="Teacher",
        created_at="2026-09-23T00:00:00Z",
        updated_at="2026-09-23T00:00:00Z",
    )
    response = await studio_router.post_lesson_approach_approve(
        source.id,
        studio_router.LessonApproachApproveRequest(
            expected_revision=1,
            expected_content_hash=teaching_plan_content_hash(plan),
            teacher_note="Approved",
        ),
        teacher,
        path="print",
    )
    payload = json.loads(response.body)
    assert response.status_code == 202
    assert payload["output_id"] != source.id
    assert payload["generation_id"] == payload["output_id"]
    async with db_session_factory() as verify:
        prepared = await verify.get(GenerationModel, source.id)
        output = await verify.get(GenerationModel, payload["output_id"])
        assert prepared is not None and output is not None
        assert prepared.status == "awaiting_teaching_approval"
        assert output.status == "queued"
        assert await verify.scalar(
            select(func.count()).select_from(NativeRealizationModel)
        ) == 0
        replay = await realize_print_from_preparation(
            verify,
            preparation_generation_id=source.id,
            user_id=user_id,
            allow_standalone=True,
        )
        assert replay["output_id"] == payload["output_id"]
        assert replay["realization_id"] is None


@pytest.mark.asyncio
async def test_p03_missing_unit_path_provenance_cannot_fall_back_to_studio(
    db_session: AsyncSession,
) -> None:
    lesson, _, _, _ = await _approved_native_preparation(
        db_session, user_id="p03-missing-path-link"
    )
    preparation_id = str(lesson.pack_id)
    user_id = "p03-missing-path-link"
    lesson.pack_id = None
    provenance = await db_session.get(LessonProvenanceModel, preparation_id)
    if provenance is not None:
        await db_session.delete(provenance)
    await db_session.flush()
    assert await db_session.scalar(
        select(PathLessonModel.id).where(PathLessonModel.pack_id == preparation_id)
    ) is None
    assert await db_session.get(LessonProvenanceModel, preparation_id) is None

    with pytest.raises(HTTPException) as error:
        await realize_print_from_preparation(
            db_session,
            preparation_generation_id=preparation_id,
            user_id=user_id,
            allow_standalone=True,
        )

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "PRINT_PATH_PROVENANCE_MISSING"

@pytest.mark.asyncio
async def test_p03_r03_persisted_path_survives_default_change(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P03-R03: restart / changed default config cannot switch a persisted path."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r03")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id="tp-p03-r03",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    row = rows[0][0]
    assert row.path == "print"
    realization_id = row.id

    # Simulate process restart + flipped environment default toward Learn.
    monkeypatch.setenv("GENERATION_PIPELINE_DEFAULT", "native_learn")
    from infra.config import settings

    monkeypatch.setattr(settings, "generation_pipeline_default", "native_learn", raising=False)

    reloaded = await db_session.get(NativeRealizationModel, realization_id)
    assert reloaded is not None
    assert persisted_path_is_stable(reloaded, "print")
    assert reloaded.path == "print"
    # Re-resolve by path still finds Print; defaults never rewrite the row.
    resolved = await resolve_by_path(db_session, path_lesson_id=lesson.id, path="print")
    assert resolved is not None and resolved.id == realization_id
    assert resolved.path == "print"


@pytest.mark.asyncio
async def test_p03_r04_shared_revision_marks_stale_keeps_snapshots(
    db_session: AsyncSession,
) -> None:
    """P03-R04: shared revision change marks outputs stale; snapshots intact."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r04")
    rows = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print", "learn"],
        teaching_plan_id="tp-p03-r04",
        teaching_plan_revision=1,
        teaching_plan_hash="hash-rev-1",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    print_row, learn_row = rows[0][0], rows[1][0]
    print_row.output_id = "print-snap-1"
    print_row.status = "ready"
    learn_row.output_id = "learn-snap-1"
    learn_row.status = "ready"
    await db_session.flush()

    stale_rows = await mark_stale_for_teaching_change(
        db_session,
        path_lesson_id=lesson.id,
        teaching_plan_id="tp-p03-r04",
        previous_revision=1,
    )
    assert len(stale_rows) == 2
    assert {row.output_id for row in stale_rows} == {"print-snap-1", "learn-snap-1"}
    assert all(row.status == "stale" for row in stale_rows)

    # Independent path regeneration under the new revision.
    refreshed = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["print"],
        teaching_plan_id="tp-p03-r04",
        teaching_plan_revision=2,
        teaching_plan_hash="hash-rev-2",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    new_print = refreshed[0][0]
    assert refreshed[0][1] is True
    assert new_print.teaching_plan_revision == 2
    assert new_print.id != print_row.id
    # Old Print snapshot row remains readable.
    await db_session.refresh(print_row)
    assert print_row.output_id == "print-snap-1"
    assert print_row.status == "stale"

    # Policy change invalidates only that path.
    _policy_version, policy_hash = policy_for("learn")
    await mark_stale_for_policy_change(
        db_session,
        path="learn",
        previous_policy_hash=policy_hash,
        path_lesson_id=lesson.id,
    )
    await db_session.refresh(learn_row)
    assert learn_row.status == "stale"
    await db_session.refresh(new_print)
    assert new_print.status == "queued"
    assert new_print.path == "print"


@pytest.mark.asyncio
async def test_p03_r05_legacy_backfill_ambiguous_read_only(db_session: AsyncSession) -> None:
    """P03-R05: migration backfill; ambiguous legacy is read-only, not guessed."""
    lesson = await _prepared_lesson(db_session, user_id="p03-r05")

    unambiguous = await backfill_legacy_realization(
        db_session,
        path_lesson_id=lesson.id,
        pack_id="legacy-print-pack",
        chunked={
            "native_whole_lesson": True,
            "page_document_v2": True,
            "teaching_plan_id": "tp-legacy",
            "teaching_review": {"approved_revision": 1},
            "teaching_plan": {"preparation_hash": "legacy-hash", "revision": 1},
        },
        planning_spec={"document_contract_version": 2},
        generation_status="completed",
    )
    assert unambiguous.path == "print"
    assert unambiguous.status == "ready"
    assert unambiguous.variant_id == DEFAULT_VARIANT_ID

    ambiguous_chunked = {
        "shared_preparation": True,
        "stage": "awaiting_review",
        # Conflicting / incomplete markers — do not invent a path.
    }
    assert classify_legacy_chunked(ambiguous_chunked) is None
    ambiguous = await backfill_legacy_realization(
        db_session,
        path_lesson_id=lesson.id,
        pack_id="legacy-ambiguous-pack",
        chunked=ambiguous_chunked,
        planning_spec={"document_contract_version": 1},
        generation_status="awaiting_review",
    )
    assert ambiguous.status == "read_only"
    assert ambiguous.variant_id == LEGACY_AMBIGUOUS_VARIANT
    assert ambiguous.error_summary and "Ambiguous" in ambiguous.error_summary
    assert ambiguous.output_id == "legacy-ambiguous-pack"

    with pytest.raises(RealizationReadOnlyError):
        await retry_realization(db_session, realization_id=ambiguous.id)

    # Explicit regenerate still allowed under normal variant keys.
    fresh = await request_outputs(
        db_session,
        path_lesson_id=lesson.id,
        paths=["learn"],
        teaching_plan_id="tp-legacy",
        teaching_plan_revision=1,
        teaching_plan_hash="legacy-hash",
        preparation_generation_id=lesson.pack_id,
        pack_id=lesson.pack_id,
    )
    assert fresh[0][1] is True
    assert fresh[0][0].path == "learn"
    assert fresh[0][0].status == "queued"


@pytest.mark.asyncio
async def test_p03_r06_concurrent_uniqueness_and_status_routing(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """P03-R06: concurrent creates unique; status/open identify the correct artifact."""
    async with db_session_factory() as setup:
        lesson = await _prepared_lesson(setup, user_id="p03-r06")
        await setup.commit()
        lesson_id = lesson.id
        pack_id = lesson.pack_id
        user_id = "p03-r06"

    async def _admit_once(label: str) -> str:
        async with db_session_factory() as session:
            results = await request_outputs(
                session,
                path_lesson_id=lesson_id,
                paths=["print"],
                teaching_plan_id="tp-p03-r06",
                teaching_plan_revision=1,
                teaching_plan_hash="hash-rev-1",
                preparation_generation_id=pack_id,
                pack_id=pack_id,
            )
            row, _created = results[0]
            # Attach a path-specific output artifact for open routing.
            if row.output_id is None:
                output_id = f"print-artifact-{label}"
                session.add(
                    GenerationModel(
                        id=output_id,
                        user_id=user_id,
                        subject="science",
                        context="print realization",
                        status="ready",
                        requested_template_id="lesson",
                        requested_preset_id="standard",
                        created_at=_utcnow(),
                        document_json={"sections": [{"id": "s1"}], "path": "print"},
                        chunked_state_json={"stage": "ready", "native_whole_lesson": True},
                    )
                )
                row.output_id = output_id
                row.status = "ready"
            await session.commit()
            return row.id

    ids = await asyncio.gather(*[_admit_once(str(i)) for i in range(8)])
    assert len(set(ids)) == 1

    async with db_session_factory() as session:
        # Admit Learn with a distinct artifact.
        learn_results = await request_outputs(
            session,
            path_lesson_id=lesson_id,
            paths=["learn"],
            teaching_plan_id="tp-p03-r06",
            teaching_plan_revision=1,
            teaching_plan_hash="hash-rev-1",
            preparation_generation_id=pack_id,
            pack_id=pack_id,
        )
        learn_row = learn_results[0][0]
        learn_output = f"learn-artifact-{uuid.uuid4().hex[:8]}"
        session.add(
            GenerationModel(
                id=learn_output,
                user_id=user_id,
                subject="science",
                context="learn realization",
                status="ready",
                requested_template_id="lesson",
                requested_preset_id="standard",
                created_at=_utcnow(),
                document_json={"sections": [{"id": "learn"}], "path": "learn"},
                chunked_state_json={
                    "stage": "ready",
                    "control": {"pipeline": "native_learn", "pipeline_version": 1},
                },
            )
        )
        learn_row.output_id = learn_output
        learn_row.status = "ready"
        await session.commit()

        print_row = await resolve_by_path(session, path_lesson_id=lesson_id, path="print")
        learn_resolved = await resolve_by_path(session, path_lesson_id=lesson_id, path="learn")
        assert print_row is not None and learn_resolved is not None
        print_id = to_identity(print_row)
        learn_id = to_identity(learn_resolved)
        assert print_id.output_id != learn_id.output_id
        assert print_id.open_href == f"/studio/print/{print_id.output_id}"
        assert learn_id.open_href == f"/builder/from-native-learn/{learn_id.output_id}"
        assert print_id.path == "print"
        assert learn_id.path == "learn"

        all_rows = await list_realizations_for_lesson(session, path_lesson_id=lesson_id)
        assert len([r for r in all_rows if r.variant_id == DEFAULT_VARIANT_ID]) == 2
        # Uniqueness still holds after the concurrent race.
        count = await session.scalar(
            select(func.count()).select_from(NativeRealizationModel).where(
                NativeRealizationModel.path_lesson_id == lesson_id,
                NativeRealizationModel.path == "print",
                NativeRealizationModel.teaching_plan_revision == 1,
                NativeRealizationModel.variant_id == DEFAULT_VARIANT_ID,
                NativeRealizationModel.native_policy_hash == policy_for("print")[1],
                NativeRealizationModel.package_contract_hash == package_contract_for("print")[1],
            )
        )
        assert count == 1


@pytest.mark.asyncio
async def test_p2b_print_rejects_unreviewed_newer_draft_without_auto_approval(
    db_session: AsyncSession,
) -> None:
    """Print must not approve rev 2 when the teacher only approved rev 1."""
    from application.unit_lesson.realize_print_handoff import realize_print_from_preparation

    lesson = await _prepared_lesson(db_session, user_id="p2b-print-pending-review")
    plan = TeachingPlan(
        teaching_plan_id="p2b-print-plan",
        revision=1,
        preparation_hash="preparation-hash",
        arc="Trace how water moves through a plant.",
        sections=[
            {
                "slot_id": "orient",
                "specific_purpose": "Connect an observation to the investigation.",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a covered leaf.",
                        "evidence": "A relevant observation.",
                    }
                ],
            }
        ],
    )
    state: dict = {}
    revisions = TeachingRevisionStore(state)
    revisions.record_draft(plan, preparation_hash="preparation-hash", revision=1)
    revisions.approve(expected_revision=1, expected_content_hash=None, reviewed_by="teacher")
    revisions.edit_plan(
        plan.model_copy(update={"arc": "Trace water from roots to leaves."}),
        preparation_hash="preparation-hash",
    )
    generation = await db_session.get(GenerationModel, lesson.pack_id)
    assert generation is not None
    generation.chunked_state_json = {"page_document_v2": state}
    await db_session.flush()

    with pytest.raises(HTTPException) as raised:
        await realize_print_from_preparation(
            db_session,
            preparation_generation_id=lesson.pack_id,
            user_id="p2b-print-pending-review",
            path_lesson_id=lesson.id,
        )

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "TEACHING_REVISION_PENDING_REVIEW"
    reloaded = await PageDocumentRepository(
        db_session, lesson.pack_id
    ).load_page_generation_state()
    assert reloaded["teaching_review"]["status"] == "pending"
    assert reloaded["teaching_review"]["revision"] == 2
    assert reloaded["teaching_review"]["approved_revision"] == 1
    assert next(
        row for row in reloaded["teaching_revisions"] if row["revision"] == 2
    )["status"] == "pending"


@pytest.mark.asyncio
async def test_p03_policy_hash_helper_stable() -> None:
    """Sanity: policy/package hashes are stable fingerprints used in identity keys."""
    v1, h1 = policy_for("print")
    v2, h2 = policy_for("print")
    assert v1 == v2 and h1 == h2
    assert policy_for("print")[1] != policy_for("learn")[1]
    assert package_contract_for("print")[1] != package_contract_for("learn")[1]
    assert canonical_hash({"a": 1}) == canonical_hash({"a": 1})

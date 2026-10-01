from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

import infra.generation_runtime.repository as generation_runtime_repository
from infra.database.models import (
    ConceptModel,
    GenerationEventModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    ArtifactVerificationError,
    BuildAdmission,
    CheckpointCompatibilityError,
    InvalidRunTransition,
    InvalidWorkItemTransition,
    LeaseLostError,
    OutputHashMismatch,
    OutputValidationError,
    RecoveryAction,
    RunAdmission,
    RunAdmissionConflict,
    RunContract,
    RunFinalization,
    RunNotFound,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    RunType,
    SourceIdentity,
    SourceIdentityConflict,
    VerifiedArtifact,
    WorkItemAdmission,
    WorkItemConflict,
    WorkItemContract,
    WorkItemFailure,
    WorkItemReplacement,
    WorkItemUnavailable,
    add_work_item,
    admit_run,
    append_event,
    cancel_run,
    claim_work_item,
    complete_work_item,
    create_build,
    fail_work_item,
    finalize_run,
    get_run_status,
    heartbeat_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    reconcile_expired_work_item,
    replace_work_item,
    retry_work_item,
    retry_work_items,
)


async def _seed_lesson(session, *, suffix: str = "a") -> tuple[str, str]:
    owner_id = f"runtime-owner-{suffix}"
    lesson_id = f"runtime-lesson-{suffix}"
    user = UserModel(id=owner_id, email=f"{owner_id}@example.invalid")
    concept = ConceptModel(
        id=f"runtime-concept-{suffix}",
        canonical_slug=f"runtime.{suffix}",
        subject="Science",
        title="Runtime fixture",
        created_by=owner_id,
    )
    unit = UnitModel(
        id=f"runtime-unit-{suffix}",
        owner_id=owner_id,
        title="Runtime fixture",
        topic="Persistence",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Persist runtime state.",
    )
    version = PathVersionModel(
        id=f"runtime-path-{suffix}",
        unit_id=unit.id,
        version=1,
        source_plan_json={},
    )
    lesson = PathLessonModel(
        id=lesson_id,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Runtime fixture",
        objective="Persist runtime state.",
        objective_hash="objective-hash",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all([user, concept, unit, version, lesson])
    await session.flush()
    return owner_id, lesson_id


async def _admit(session, *, owner_id: str, lesson_id: str, request_key: str = "req-1"):
    build = await create_build(
        session,
        BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id),
    )
    result = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner_id,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=request_key,
            stage="section_composition",
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-1",
            source_revision=3,
            source_hash="sha256:plan-a",
        ),
    )
    return build, result


def _source_identity() -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id="plan-1",
        source_revision=3,
        source_hash="sha256:plan-a",
    )


def _finalization_request(**updates) -> RunFinalization:
    fields = {
        "source": _source_identity(),
        "output_artifact_type": "shared_lesson_document",
        "output_artifact_id": "document-runtime-1",
        "output_revision": 1,
    }
    fields.update(updates)
    return RunFinalization(**fields)


async def _verify_source(_session, requested: SourceIdentity) -> SourceIdentity:
    return requested


def _load_verified_artifact(output_json, **identity_overrides):
    async def loader(_session, artifact_type: str, artifact_id: str, revision: int):
        fields = {
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "revision": revision,
            "output_json": output_json,
            "output_hash": content_hash(output_json),
        }
        fields.update(identity_overrides)
        return VerifiedArtifact(**fields)

    return loader


async def _complete_item(session, *, item_id: str, worker_id: str, value, now):
    claim = await claim_work_item(
        session,
        work_item_id=item_id,
        worker_id=worker_id,
        source=_source_identity(),
        now=now,
    )
    return await complete_work_item(
        session,
        work_item_id=item_id,
        worker_id=worker_id,
        lease_token=claim.lease_token,
        output_json=value,
        output_hash=content_hash(value),
        now=now + timedelta(seconds=1),
    )


def _checkpoint_compatibility(**updates) -> RuntimeCheckpointCompatibility:
    fields = {
        "schema_version": 1,
        "source_revision": 3,
        "source_hash": "sha256:plan-a",
        "input_hash": "input-checkpoint",
        "definition_hash": "definition-checkpoint",
        "composition_identity": "section:checkpoint:v1",
    }
    fields.update(updates)
    return RuntimeCheckpointCompatibility.model_validate(fields)


def test_contracts_keep_closed_status_separate_from_stage() -> None:
    now = datetime.now(UTC)
    run_fields = {
        "id": "run-1",
        "build_id": "build-1",
        "run_type": "shared_document",
        "owner_user_id": "owner-1",
        "stage": "section_writing",
        "attempt": 1,
        "source_artifact_type": "teaching_plan",
        "source_artifact_id": "plan-1",
        "source_revision": 1,
        "source_hash": "source-hash",
        "request_key": "request-1",
        "created_at": now,
        "updated_at": now,
    }
    queued = RunContract.model_validate({**run_fields, "status": "queued"})
    assert queued.stage == "section_writing"
    with pytest.raises(ValidationError, match="complete output"):
        RunContract.model_validate({**run_fields, "status": "ready"})
    with pytest.raises(ValidationError):
        RunContract.model_validate({"status": "writing", "stage": "section_writing"})
    with pytest.raises(ValidationError):
        WorkItemContract.model_validate({"status": "awaiting_review", "stage": "section_writing"})
    with pytest.raises(ValidationError, match="output_json"):
        WorkItemContract.model_validate(
            {
                "id": "item-1",
                "run_id": "run-1",
                "item_key": "section:explain",
                "stage": "section_writing",
                "status": "ready",
                "attempt": 1,
                "max_attempts": 1,
                "input_hash": "input-hash",
                "definition_hash": "definition-hash",
                "created_at": now,
                "updated_at": now,
            }
        )
    list_output = WorkItemContract.model_validate(
        {
            "id": "item-list-output",
            "run_id": "run-1",
            "item_key": "section:examples",
            "stage": "section_writing",
            "status": "ready",
            "attempt": 1,
            "max_attempts": 1,
            "input_hash": "input-hash",
            "definition_hash": "definition-hash",
            "checkpoint_json": ["checkpoint-a", 2],
            "output_json": [{"example": 1}, "complete"],
            "output_hash": "output-hash",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert list_output.checkpoint_json == ["checkpoint-a", 2]
    assert list_output.output_json == [{"example": 1}, "complete"]
    with pytest.raises(ValidationError):
        RuntimeCheckpoint.model_validate(
            {
                "compatibility": _checkpoint_compatibility().model_dump(),
                "payload": object(),
                "payload_hash": "not-json",
            }
        )
    with pytest.raises(ValidationError, match="strict JSON"):
        RuntimeCheckpoint.model_validate(
            {
                "compatibility": _checkpoint_compatibility().model_dump(),
                "payload": float("nan"),
                "payload_hash": "not-json",
            }
        )


@pytest.mark.asyncio
async def test_run_admission_reuses_identical_key_and_rejects_hash_conflict(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    build, first = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    same_request = RunAdmission(
        build_id=build.id,
        owner_user_id=owner_id,
        run_type=RunType.SHARED_DOCUMENT,
        request_key="req-1",
        stage="teaching_planning",
        source_artifact_type="teaching_plan",
        source_artifact_id="plan-1",
        source_revision=3,
        source_hash="sha256:plan-a",
    )

    duplicate = await admit_run(db_session, same_request)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    assert duplicate.record.stage == "section_composition"

    with pytest.raises(RunAdmissionConflict):
        await admit_run(
            db_session, same_request.model_copy(update={"source_hash": "sha256:plan-b"})
        )

    with pytest.raises(RunAdmissionConflict):
        await admit_run(db_session, same_request.model_copy(update={"run_type": RunType.PRINT}))


@pytest.mark.asyncio
async def test_build_rejects_path_lesson_owned_by_another_user(db_session) -> None:
    owner_id, _owner_lesson = await _seed_lesson(db_session)
    _other_owner, other_lesson = await _seed_lesson(db_session, suffix="other")

    with pytest.raises(ValueError, match="unavailable to this owner"):
        await create_build(
            db_session,
            BuildAdmission(owner_user_id=owner_id, path_lesson_id=other_lesson),
        )


@pytest.mark.asyncio
async def test_work_item_key_is_idempotent_only_for_same_identity(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    request = WorkItemAdmission(
        run_id=admitted.record.id,
        item_key="section:explain",
        stage="section_writing",
        input_hash="input-a",
        definition_hash="definition-a",
        composition_identity="section:explain:v1",
    )

    first = await add_work_item(db_session, request)
    duplicate = await add_work_item(db_session, request)

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    with pytest.raises(WorkItemConflict):
        await add_work_item(db_session, request.model_copy(update={"input_hash": "input-b"}))


@pytest.mark.asyncio
async def test_claim_competition_grants_one_lease_and_preserves_siblings(
    db_session, db_session_factory
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:claimed",
            stage="section_writing",
            input_hash="input-claimed",
            definition_hash="definition-claimed",
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:sibling",
            stage="section_writing",
            input_hash="input-sibling",
            definition_hash="definition-sibling",
        ),
    )
    await db_session.commit()

    async def attempt_claim(worker_id: str):
        async with db_session_factory() as session:
            try:
                claimed = await claim_work_item(
                    session,
                    work_item_id=item.record.id,
                    worker_id=worker_id,
                    source=_source_identity(),
                )
                await session.commit()
                return claimed
            except WorkItemUnavailable:
                await session.rollback()
                return None

    winners = [
        result
        for result in await asyncio.gather(attempt_claim("worker-a"), attempt_claim("worker-b"))
        if result is not None
    ]

    assert len(winners) == 1
    assert winners[0].status == "running"
    assert winners[0].attempt == 1
    assert winners[0].lease_token == 1
    assert winners[0].lease_owner in {"worker-a", "worker-b"}
    await db_session.refresh(admitted.record)
    assert admitted.record.status == "running"
    await db_session.refresh(sibling.record)
    assert sibling.record.status == "queued"
    assert sibling.record.lease_owner is None
    assert sibling.record.lease_token is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("source_artifact_type", "different_type"),
        ("source_artifact_id", "different-id"),
        ("source_revision", 4),
        ("source_hash", "sha256:changed"),
    ],
)
async def test_claim_rejects_fresh_source_identity_conflict_without_mutation(
    db_session, field: str, value: object
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:source-check",
            stage="section_writing",
            input_hash="input",
            definition_hash="definition",
        ),
    )

    with pytest.raises(SourceIdentityConflict, match="fresh source identity"):
        await claim_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-a",
            source=_source_identity().model_copy(update={field: value}),
        )

    await db_session.refresh(item.record)
    assert item.record.status == "queued"
    assert item.record.lease_owner is None
    assert item.record.lease_token is None


@pytest.mark.asyncio
async def test_claim_rejects_item_when_run_is_not_active(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:terminal-run",
            stage="section_writing",
            input_hash="input",
            definition_hash="definition",
        ),
    )
    admitted.record.status = "cancelled"
    await db_session.flush()

    with pytest.raises(WorkItemUnavailable, match="active"):
        await claim_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-a",
            source=_source_identity(),
        )

    await db_session.refresh(item.record)
    assert item.record.status == "queued"
    assert item.record.lease_owner is None
    assert item.record.lease_token is None


@pytest.mark.asyncio
async def test_claim_rolls_back_when_run_turns_terminal_during_claim(
    db_session, db_session_factory, monkeypatch
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:run-race",
            stage="section_writing",
            input_hash="input",
            definition_hash="definition",
        ),
    )
    await db_session.commit()

    original_execute = db_session.execute
    injected_terminal_transition = False

    async def terminate_run_before_item_update(statement, *args, **kwargs):
        nonlocal injected_terminal_transition
        target_table = getattr(statement, "table", None)
        if (
            not injected_terminal_transition
            and getattr(target_table, "name", None) == "generation_work_items"
        ):
            injected_terminal_transition = True
            async with db_session_factory() as concurrent_session:
                concurrent_run = await concurrent_session.get(
                    GenerationRunModel, admitted.record.id
                )
                assert concurrent_run is not None
                concurrent_run.status = "cancelled"
                await concurrent_session.commit()
        return await original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", terminate_run_before_item_update)
    with pytest.raises(WorkItemUnavailable, match="run changed"):
        await claim_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-a",
            source=_source_identity(),
        )

    assert injected_terminal_transition is True
    await db_session.refresh(item.record)
    assert item.record.status == "queued"
    assert item.record.lease_owner is None
    assert item.record.lease_token is None


@pytest.mark.asyncio
async def test_expired_lease_recovery_increments_attempt_and_fence(
    db_session, db_session_factory
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:recover",
            stage="section_writing",
            input_hash="input",
            definition_hash="definition",
            max_attempts=2,
        ),
    )
    start = datetime(2026, 9, 1, tzinfo=UTC)
    first = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        source=_source_identity(),
        lease_seconds=20,
        now=start,
    )
    assert first.attempt == 1
    assert first.lease_token == 1
    assert first.lease_expires_at == (start + timedelta(seconds=20)).replace(tzinfo=None)

    await db_session.commit()
    async with db_session_factory() as restarted_session:
        recovered = await claim_work_item(
            restarted_session,
            work_item_id=item.record.id,
            worker_id="worker-new",
            source=_source_identity(),
            lease_seconds=20,
            now=start + timedelta(seconds=20),
        )
        await restarted_session.commit()
    assert recovered.attempt == 2
    assert recovered.lease_token == 2
    assert recovered.lease_owner == "worker-new"


@pytest.mark.asyncio
async def test_heartbeat_and_checkpoint_are_fenced_across_expired_reclaim(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:checkpoint",
            stage="section_writing",
            input_hash="input-checkpoint",
            definition_hash="definition-checkpoint",
            composition_identity="section:checkpoint:v1",
            max_attempts=2,
        ),
    )
    start = datetime(2026, 9, 2, tzinfo=UTC)
    first = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        source=_source_identity(),
        lease_seconds=20,
        now=start,
    )
    first_token = first.lease_token
    compatibility = _checkpoint_compatibility()
    saved = await persist_checkpoint(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        lease_token=first_token,
        compatibility=compatibility,
        payload=[{"section": "orient"}, "draft"],
        now=start + timedelta(seconds=2),
    )
    assert saved.payload == [{"section": "orient"}, "draft"]

    heartbeat = await heartbeat_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        lease_token=first_token,
        lease_seconds=20,
        now=start + timedelta(seconds=10),
    )
    assert heartbeat.lease_expires_at == (start + timedelta(seconds=30)).replace(tzinfo=None)

    recovered = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-new",
        source=_source_identity(),
        lease_seconds=30,
        now=start + timedelta(seconds=30),
    )
    assert recovered.lease_token == 2
    assert recovered.attempt == 2

    with pytest.raises(LeaseLostError):
        await heartbeat_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=first_token,
            now=start + timedelta(seconds=31),
        )
    with pytest.raises(LeaseLostError):
        await persist_checkpoint(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=first_token,
            compatibility=compatibility,
            payload={"stale": True},
            now=start + timedelta(seconds=31),
        )

    resumed = await load_compatible_checkpoint(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-new",
        lease_token=recovered.lease_token,
        compatibility=compatibility,
        now=start + timedelta(seconds=31),
    )
    assert resumed == saved


@pytest.mark.asyncio
async def test_checkpoint_cas_rejects_worker_overtaken_after_lease_read(
    db_session, db_session_factory, monkeypatch
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:interleaved-checkpoint",
            stage="section_writing",
            input_hash="input-checkpoint",
            definition_hash="definition-checkpoint",
            composition_identity="section:checkpoint:v1",
            max_attempts=2,
        ),
    )
    start = datetime(2026, 9, 5, tzinfo=UTC)
    first = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        source=_source_identity(),
        lease_seconds=10,
        now=start,
    )
    stale_token = first.lease_token
    await db_session.commit()

    source_read = asyncio.Event()
    allow_checkpoint_write = asyncio.Event()
    original_require_lease = generation_runtime_repository._require_live_lease

    async def pause_after_lease_read(*args, **kwargs):
        claimed_item = await original_require_lease(*args, **kwargs)
        if kwargs.get("worker_id") == "worker-old":
            source_read.set()
            await allow_checkpoint_write.wait()
        return claimed_item

    monkeypatch.setattr(
        generation_runtime_repository, "_require_live_lease", pause_after_lease_read
    )
    compatibility = _checkpoint_compatibility()

    async with (
        db_session_factory() as old_worker_session,
        db_session_factory() as new_worker_session,
    ):
        pending_checkpoint = asyncio.create_task(
            persist_checkpoint(
                old_worker_session,
                work_item_id=item.record.id,
                worker_id="worker-old",
                lease_token=stale_token,
                compatibility=compatibility,
                payload={"owner": "old-worker"},
                now=start + timedelta(seconds=1),
            )
        )
        try:
            await asyncio.wait_for(source_read.wait(), timeout=5)
            new_claim = await claim_work_item(
                new_worker_session,
                work_item_id=item.record.id,
                worker_id="worker-new",
                source=_source_identity(),
                lease_seconds=30,
                now=start + timedelta(seconds=10),
            )
            await new_worker_session.commit()
        finally:
            allow_checkpoint_write.set()

        with pytest.raises(LeaseLostError, match="before checkpoint persistence"):
            await pending_checkpoint
        await old_worker_session.rollback()

    assert new_claim.lease_token == 2
    await db_session.refresh(item.record)
    assert item.record.lease_owner == "worker-new"
    assert item.record.lease_token == 2
    assert item.record.checkpoint_json is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("source_revision", 4),
        ("source_hash", "sha256:changed"),
        ("input_hash", "input-changed"),
        ("definition_hash", "definition-changed"),
        ("composition_identity", "section:checkpoint:v2"),
    ],
)
async def test_checkpoint_reuse_rejects_each_incompatible_identity_field(
    db_session, field: str, value: object
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:checkpoint-mismatch",
            stage="section_writing",
            input_hash="input-checkpoint",
            definition_hash="definition-checkpoint",
            composition_identity="section:checkpoint:v1",
        ),
    )
    now = datetime(2026, 9, 3, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-a",
        source=_source_identity(),
        now=now,
    )
    compatibility = _checkpoint_compatibility()
    await persist_checkpoint(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-a",
        lease_token=claim.lease_token,
        compatibility=compatibility,
        payload={"draft": "safe to resume"},
        now=now + timedelta(seconds=1),
    )

    with pytest.raises(CheckpointCompatibilityError):
        await load_compatible_checkpoint(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-a",
            lease_token=claim.lease_token,
            compatibility=compatibility.model_copy(update={field: value}),
            now=now + timedelta(seconds=2),
        )


@pytest.mark.asyncio
async def test_persist_checkpoint_refuses_to_replace_incompatible_checkpoint(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:preserve-checkpoint",
            stage="section_writing",
            input_hash="input-checkpoint",
            definition_hash="definition-checkpoint",
            composition_identity="section:checkpoint:v1",
        ),
    )
    now = datetime(2026, 9, 3, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-a",
        source=_source_identity(),
        now=now,
    )
    compatible = _checkpoint_compatibility()
    incompatible = _checkpoint_compatibility(source_hash="sha256:old-source")
    existing = RuntimeCheckpoint(
        compatibility=incompatible,
        payload={"saved": "prior source"},
        payload_hash=content_hash({"saved": "prior source"}),
    )
    item.record.checkpoint_json = existing.model_dump(mode="json")
    await db_session.flush()

    with pytest.raises(CheckpointCompatibilityError, match="existing checkpoint"):
        await persist_checkpoint(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-a",
            lease_token=claim.lease_token,
            compatibility=compatible,
            payload={"saved": "new source"},
            now=now + timedelta(seconds=1),
        )

    await db_session.refresh(item.record)
    assert item.record.checkpoint_json["compatibility"]["source_hash"] == "sha256:old-source"


@pytest.mark.asyncio
async def test_expired_lease_cannot_be_reclaimed_beyond_attempt_budget(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:bounded",
            stage="section_writing",
            input_hash="input",
            definition_hash="definition",
            max_attempts=1,
        ),
    )
    start = datetime(2026, 9, 4, tzinfo=UTC)
    first = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-a",
        source=_source_identity(),
        lease_seconds=10,
        now=start,
    )

    reconciled = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-b",
        source=_source_identity(),
        lease_seconds=10,
        now=start + timedelta(seconds=10),
    )

    await db_session.refresh(item.record)
    assert reconciled.status == "failed_terminal"
    assert item.record.status == "failed_terminal"
    assert item.record.attempt == 1
    assert item.record.lease_token == first.lease_token
    assert item.record.lease_owner is None
    assert item.record.error_code == "budget_exhausted"
    assert item.record.error_class == "budget_exhausted"
    run = await db_session.get(GenerationRunModel, item.record.run_id)
    assert run is not None
    assert run.status == "failed_terminal"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationEventModel)
            .where(GenerationEventModel.work_item_id == item.record.id)
        )
        == 1
    )


def _failure(
    *,
    error_class="provider_output",
    recovery_action=RecoveryAction.RETRY,
    error_code="invalid_output",
    safe_summary="Generated output did not pass validation.",
) -> WorkItemFailure:
    return WorkItemFailure(
        error_code=error_code,
        error_class=error_class,
        safe_summary=safe_summary,
        recovery_action=recovery_action,
    )


@pytest.mark.asyncio
async def test_work_item_completion_hash_and_duplicate_are_idempotent(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:complete-once",
            stage="section_writing",
            input_hash="input-complete",
            definition_hash="definition-complete",
        ),
    )
    now = datetime(2026, 9, 5, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-complete",
        source=_source_identity(),
        lease_seconds=60,
        now=now,
    )
    output = [{"type": "paragraph", "text": "A canonical output."}, "complete"]
    output_hash = content_hash(output)

    with pytest.raises(OutputHashMismatch):
        await complete_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-complete",
            lease_token=claim.lease_token,
            output_json=output,
            output_hash="wrong-hash",
            now=now + timedelta(seconds=1),
        )

    completed = await complete_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-complete",
        lease_token=claim.lease_token,
        output_json=output,
        output_hash=output_hash,
        now=now + timedelta(seconds=2),
    )
    duplicate = await complete_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-complete",
        lease_token=claim.lease_token,
        output_json=output,
        output_hash=output_hash,
        now=now + timedelta(seconds=3),
    )
    duplicate_after_expiry = await complete_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-complete",
        lease_token=claim.lease_token,
        output_json=output,
        output_hash=output_hash,
        now=now + timedelta(seconds=61),
    )

    assert completed.status == duplicate.status == "ready"
    assert duplicate_after_expiry.output_json == output
    assert duplicate_after_expiry.output_hash == output_hash
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationEventModel)
            .where(GenerationEventModel.work_item_id == item.record.id)
        )
        == 1
    )

    with pytest.raises(OutputHashMismatch):
        await complete_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-complete",
            lease_token=claim.lease_token,
            output_json={"different": True},
            output_hash=content_hash({"different": True}),
            now=now + timedelta(seconds=4),
        )

    with pytest.raises(OutputValidationError):
        await complete_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-complete",
            lease_token=claim.lease_token,
            output_json=object(),
            output_hash="invalid",
            now=now + timedelta(seconds=4),
        )


@pytest.mark.asyncio
async def test_stale_fence_cannot_complete_or_fail_work_item(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:stale-outcome",
            stage="section_writing",
            input_hash="input-stale",
            definition_hash="definition-stale",
            max_attempts=2,
        ),
    )
    start = datetime(2026, 9, 6, tzinfo=UTC)
    first = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        source=_source_identity(),
        lease_seconds=5,
        now=start,
    )
    second = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-new",
        source=_source_identity(),
        lease_seconds=30,
        now=start + timedelta(seconds=5),
    )

    with pytest.raises(LeaseLostError):
        await complete_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=first.lease_token,
            output_json={"stale": True},
            output_hash=content_hash({"stale": True}),
            now=start + timedelta(seconds=6),
        )
    with pytest.raises(LeaseLostError):
        await fail_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=first.lease_token,
            failure=_failure(),
            now=start + timedelta(seconds=6),
        )

    await db_session.refresh(item.record)
    assert item.record.status == "running"
    assert item.record.lease_owner == "worker-new"
    assert item.record.lease_token == second.lease_token


@pytest.mark.asyncio
async def test_targeted_retry_preserves_ready_sibling_and_checkpoint(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    target = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:retry-target",
            stage="section_writing",
            input_hash="input-checkpoint",
            definition_hash="definition-checkpoint",
            composition_identity="section:checkpoint:v1",
            max_attempts=3,
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:healthy-sibling",
            stage="section_writing",
            input_hash="input-sibling",
            definition_hash="definition-sibling",
        ),
    )
    now = datetime(2026, 9, 7, tzinfo=UTC)
    target_claim = await claim_work_item(
        db_session,
        work_item_id=target.record.id,
        worker_id="worker-first",
        source=_source_identity(),
        now=now,
    )
    target_initial_token = target_claim.lease_token
    compatibility = _checkpoint_compatibility()
    checkpoint = await persist_checkpoint(
        db_session,
        work_item_id=target.record.id,
        worker_id="worker-first",
        lease_token=target_claim.lease_token,
        compatibility=compatibility,
        payload={"saved_section": "orient"},
        now=now + timedelta(seconds=1),
    )
    sibling_claim = await claim_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="worker-sibling",
        source=_source_identity(),
        now=now + timedelta(seconds=2),
    )
    sibling_output = {"section": "healthy", "content": ["kept"]}
    await complete_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="worker-sibling",
        lease_token=sibling_claim.lease_token,
        output_json=sibling_output,
        output_hash=content_hash(sibling_output),
        now=now + timedelta(seconds=3),
    )
    failed = await fail_work_item(
        db_session,
        work_item_id=target.record.id,
        worker_id="worker-first",
        lease_token=target_claim.lease_token,
        failure=_failure(),
        now=now + timedelta(seconds=4),
    )
    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    assert failed.status == "failed_recoverable"
    assert run.status == "failed_recoverable"

    retried = await retry_work_item(
        db_session,
        work_item_id=target.record.id,
        owner_user_id=owner_id,
        now=now + timedelta(seconds=5),
    )
    await db_session.refresh(sibling.record)
    assert retried.status == "queued"
    assert retried.attempt == 2
    assert retried.lease_token == target_initial_token + 1
    retried_token = retried.lease_token
    assert retried.checkpoint_json == checkpoint.model_dump(mode="json")
    assert retried.error_code is None
    assert run.status == "queued"
    assert sibling.record.status == "ready"
    assert sibling.record.output_json == sibling_output
    assert sibling.record.output_hash == content_hash(sibling_output)

    next_claim = await claim_work_item(
        db_session,
        work_item_id=target.record.id,
        worker_id="worker-second",
        source=_source_identity(),
        now=now + timedelta(seconds=6),
    )
    assert next_claim.attempt == 2
    assert next_claim.lease_token == retried_token + 1
    resumed = await load_compatible_checkpoint(
        db_session,
        work_item_id=target.record.id,
        worker_id="worker-second",
        lease_token=next_claim.lease_token,
        compatibility=compatibility,
        now=now + timedelta(seconds=7),
    )
    assert resumed == checkpoint
    with pytest.raises(LeaseLostError):
        await complete_work_item(
            db_session,
            work_item_id=target.record.id,
            worker_id="worker-first",
            lease_token=target_initial_token,
            output_json={"late": True},
            output_hash=content_hash({"late": True}),
            now=now + timedelta(seconds=7),
        )


@pytest.mark.asyncio
async def test_batch_retry_reopens_run_atomically_and_preserves_ready_sibling(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="batch-retry")
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    now = datetime(2026, 9, 10, tzinfo=UTC)
    targets = [
        await add_work_item(
            db_session,
            WorkItemAdmission(
                run_id=admitted.record.id,
                item_key=f"section:batch-{index}",
                stage="section_writing",
                input_hash="input-checkpoint",
                definition_hash="definition-checkpoint",
                composition_identity="section:checkpoint:v1",
                max_attempts=3,
            ),
        )
        for index in range(2)
    ]
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:batch-healthy",
            stage="section_writing",
            input_hash="batch-sibling-input",
            definition_hash="batch-sibling-definition",
        ),
    )
    sibling_claim = await claim_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="batch-sibling-worker",
        source=_source_identity(),
        now=now,
    )
    sibling_output = {"section": "keep"}
    await complete_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="batch-sibling-worker",
        lease_token=sibling_claim.lease_token,
        output_json=sibling_output,
        output_hash=content_hash(sibling_output),
        now=now + timedelta(seconds=1),
    )
    checkpoints = {}
    for index, target in enumerate(targets):
        claim = await claim_work_item(
            db_session,
            work_item_id=target.record.id,
            worker_id=f"batch-worker-{index}",
            source=_source_identity(),
            now=now + timedelta(seconds=2 + index * 2),
        )
        checkpoints[target.record.id] = await persist_checkpoint(
            db_session,
            work_item_id=target.record.id,
            worker_id=f"batch-worker-{index}",
            lease_token=claim.lease_token,
            compatibility=_checkpoint_compatibility(),
            payload={"saved": index},
            now=now + timedelta(seconds=3 + index * 2),
        )
        await fail_work_item(
            db_session,
            work_item_id=target.record.id,
            worker_id=f"batch-worker-{index}",
            lease_token=claim.lease_token,
            failure=_failure(),
            now=now + timedelta(seconds=4 + index * 2),
        )

    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None and run.status == "failed_recoverable"
    retried = await retry_work_items(
        db_session,
        run_id=run.id,
        work_item_ids=[target.record.id for target in reversed(targets)],
        owner_user_id=owner_id,
        now=now + timedelta(seconds=10),
    )
    assert [item.id for item in retried] == sorted(target.record.id for target in targets)
    assert all(item.status == "queued" and item.attempt == 2 for item in retried)
    assert all(
        item.checkpoint_json == checkpoints[item.id].model_dump(mode="json")
        for item in retried
    )
    assert run.status == "queued"
    await db_session.refresh(sibling.record)
    assert sibling.record.status == "ready"
    assert sibling.record.output_json == sibling_output
    assert sibling.record.output_hash == content_hash(sibling_output)
    events = list(
        (
            await db_session.scalars(
                select(GenerationEventModel).where(
                    GenerationEventModel.run_id == run.id,
                    GenerationEventModel.event_type == "work_item_retry_queued",
                )
            )
        ).all()
    )
    assert {event.work_item_id for event in events} == {target.record.id for target in targets}


@pytest.mark.asyncio
async def test_batch_retry_rejects_mixed_invalid_items_without_partial_changes(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="batch-invalid")
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    now = datetime(2026, 9, 11, tzinfo=UTC)
    target = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:batch-invalid-target",
            stage="section_writing",
            input_hash="invalid-target-input",
            definition_hash="invalid-target-definition",
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:batch-invalid-sibling",
            stage="section_writing",
            input_hash="invalid-sibling-input",
            definition_hash="invalid-sibling-definition",
        ),
    )
    claim = await claim_work_item(
        db_session,
        work_item_id=target.record.id,
        worker_id="batch-invalid-worker",
        source=_source_identity(),
        now=now,
    )
    await fail_work_item(
        db_session,
        work_item_id=target.record.id,
        worker_id="batch-invalid-worker",
        lease_token=claim.lease_token,
        failure=_failure(),
        now=now + timedelta(seconds=1),
    )
    with pytest.raises(InvalidWorkItemTransition):
        await retry_work_items(
            db_session,
            run_id=admitted.record.id,
            work_item_ids=[target.record.id, sibling.record.id],
            owner_user_id=owner_id,
            now=now + timedelta(seconds=2),
        )
    await db_session.refresh(target.record)
    await db_session.refresh(sibling.record)
    assert target.record.status == "failed_recoverable" and target.record.attempt == 1
    assert sibling.record.status == "queued" and sibling.record.attempt == 1
    retry_events = await db_session.scalar(
        select(func.count(GenerationEventModel.id)).where(
            GenerationEventModel.run_id == admitted.record.id,
            GenerationEventModel.event_type == "work_item_retry_queued",
        )
    )
    assert retry_events == 0


@pytest.mark.asyncio
async def test_retry_exhaustion_and_nonretryable_failure_are_terminal(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:no-retries-left",
            stage="section_writing",
            input_hash="input-terminal",
            definition_hash="definition-terminal",
            max_attempts=1,
        ),
    )
    now = datetime(2026, 9, 8, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-only-attempt",
        source=_source_identity(),
        now=now,
    )
    terminal = await fail_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-only-attempt",
        lease_token=claim.lease_token,
        failure=_failure(error_class="provider_transport", error_code="timeout"),
        now=now + timedelta(seconds=1),
    )
    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    assert terminal.status == "failed_terminal"
    assert terminal.recovery_action == RecoveryAction.REGENERATE.value
    assert run.status == "failed_terminal"
    with pytest.raises(InvalidWorkItemTransition):
        await retry_work_item(
            db_session,
            work_item_id=item.record.id,
            owner_user_id=owner_id,
            now=now + timedelta(seconds=2),
        )

    with pytest.raises(ValidationError, match="cannot request a work-item retry"):
        _failure(error_class="internal_programming")


@pytest.mark.asyncio
async def test_invalid_recovery_action_is_rejected() -> None:
    with pytest.raises(ValidationError, match="recovery_action"):
        WorkItemFailure(
            error_code="provider_error",
            error_class="provider_output",
            safe_summary="Safe summary.",
            recovery_action="invented_action",
        )


@pytest.mark.asyncio
async def test_failure_action_none_cannot_be_target_retried(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:no-action-retry",
            stage="section_writing",
            input_hash="input-no-retry",
            definition_hash="definition-no-retry",
        ),
    )
    now = datetime(2026, 9, 8, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-no-action",
        source=_source_identity(),
        now=now,
    )
    failed = await fail_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-no-action",
        lease_token=claim.lease_token,
        failure=_failure(recovery_action=RecoveryAction.NONE),
        now=now + timedelta(seconds=1),
    )
    assert failed.status == "failed_terminal"
    with pytest.raises(InvalidWorkItemTransition, match="failed_recoverable"):
        await retry_work_item(
            db_session,
            work_item_id=item.record.id,
            owner_user_id=owner_id,
            now=now + timedelta(seconds=2),
        )


@pytest.mark.asyncio
async def test_reviewable_content_failure_is_recoverable_but_requires_replacement(
    db_session,
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="reviewable")
    _build, admitted = await _admit(
        db_session, owner_id=owner_id, lesson_id=lesson_id, request_key="reviewable"
    )
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="document-qa",
            stage="document_qa",
            input_hash="document-before-repair",
            definition_hash="document-qa-definition",
        ),
    )
    now = datetime(2026, 9, 25, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="document-qa-worker",
        source=_source_identity(),
        now=now,
    )
    failed = await fail_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="document-qa-worker",
        lease_token=claim.lease_token,
        failure=_failure(
            error_class="validation",
            recovery_action=RecoveryAction.REVIEW,
            error_code="document_qa_semantic_issue",
        ),
        now=now + timedelta(seconds=1),
    )
    assert failed.status == "failed_recoverable"
    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None and run.status == "failed_recoverable"
    with pytest.raises(InvalidWorkItemTransition, match="recovery action"):
        await retry_work_item(
            db_session,
            work_item_id=item.record.id,
            owner_user_id=owner_id,
            now=now + timedelta(seconds=2),
        )

    replacement = await replace_work_item(
        db_session,
        WorkItemReplacement(
            predecessor_work_item_id=item.record.id,
            owner_user_id=owner_id,
            source=_source_identity(),
            replacement=WorkItemAdmission(
                run_id=admitted.record.id,
                item_key="document-qa:repaired",
                stage="document_qa",
                input_hash="document-after-repair",
                definition_hash="document-qa-definition",
                composition_identity="repaired-document-hash",
            ),
        ),
        now=now + timedelta(seconds=3),
    )
    assert replacement.status == "queued"
    assert replacement.replaces_work_item_id == item.record.id


@pytest.mark.asyncio
async def test_terminal_failure_blocks_live_sibling_worker(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    fatal = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:fatal",
            stage="section_writing",
            input_hash="input-fatal",
            definition_hash="definition-fatal",
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:still-running",
            stage="section_writing",
            input_hash="input-still-running",
            definition_hash="definition-still-running",
        ),
    )
    now = datetime(2026, 9, 8, tzinfo=UTC)
    fatal_claim = await claim_work_item(
        db_session,
        work_item_id=fatal.record.id,
        worker_id="worker-fatal",
        source=_source_identity(),
        now=now,
    )
    sibling_claim = await claim_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="worker-sibling",
        source=_source_identity(),
        now=now + timedelta(seconds=1),
    )
    failed = await fail_work_item(
        db_session,
        work_item_id=fatal.record.id,
        worker_id="worker-fatal",
        lease_token=fatal_claim.lease_token,
        failure=_failure(
            error_class="internal_programming",
            recovery_action=RecoveryAction.REVIEW,
            error_code="unexpected_state",
        ),
        now=now + timedelta(seconds=2),
    )
    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    assert failed.status == "failed_terminal"
    assert run.status == "failed_terminal"

    with pytest.raises(LeaseLostError):
        await complete_work_item(
            db_session,
            work_item_id=sibling.record.id,
            worker_id="worker-sibling",
            lease_token=sibling_claim.lease_token,
            output_json={"late": True},
            output_hash=content_hash({"late": True}),
            now=now + timedelta(seconds=3),
        )
    with pytest.raises(LeaseLostError):
        await persist_checkpoint(
            db_session,
            work_item_id=sibling.record.id,
            worker_id="worker-sibling",
            lease_token=sibling_claim.lease_token,
            compatibility=_checkpoint_compatibility(),
            payload={"late": True},
            now=now + timedelta(seconds=3),
        )

    await db_session.refresh(sibling.record)
    assert sibling.record.status == "running"
    assert sibling.record.output_json is None


@pytest.mark.asyncio
async def test_sibling_completion_settles_drained_recoverable_run(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    failing = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:fail-first",
            stage="section_writing",
            input_hash="input-fail-first",
            definition_hash="definition-fail-first",
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:complete-after-failure",
            stage="section_writing",
            input_hash="input-complete-after",
            definition_hash="definition-complete-after",
        ),
    )
    now = datetime(2026, 9, 8, tzinfo=UTC)
    failing_claim = await claim_work_item(
        db_session,
        work_item_id=failing.record.id,
        worker_id="worker-failing",
        source=_source_identity(),
        now=now,
    )
    sibling_claim = await claim_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="worker-sibling",
        source=_source_identity(),
        now=now + timedelta(seconds=1),
    )
    await fail_work_item(
        db_session,
        work_item_id=failing.record.id,
        worker_id="worker-failing",
        lease_token=failing_claim.lease_token,
        failure=_failure(),
        now=now + timedelta(seconds=2),
    )
    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    assert run.status == "running"

    sibling_output = {"section": "still-valid"}
    await complete_work_item(
        db_session,
        work_item_id=sibling.record.id,
        worker_id="worker-sibling",
        lease_token=sibling_claim.lease_token,
        output_json=sibling_output,
        output_hash=content_hash(sibling_output),
        now=now + timedelta(seconds=3),
    )
    assert sibling.record.status == "ready"
    assert run.status == "failed_recoverable"
    assert run.error_code == "invalid_output"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["complete", "fail"])
async def test_outcome_cas_rejects_takeover_between_lease_read_and_write(
    db_session, db_session_factory, monkeypatch, outcome: str
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key=f"section:outcome-race-{outcome}",
            stage="section_writing",
            input_hash="input-race",
            definition_hash="definition-race",
            max_attempts=2,
        ),
    )
    started = datetime(2026, 9, 10, tzinfo=UTC)
    old_claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-old",
        source=_source_identity(),
        lease_seconds=5,
        now=started,
    )
    await db_session.commit()

    original_require = generation_runtime_repository._require_live_lease
    takeover_done = False

    async def claim_after_old_read(session, **kwargs):
        nonlocal takeover_done
        checked = await original_require(session, **kwargs)
        if session is db_session and not takeover_done:
            takeover_done = True
            async with db_session_factory() as takeover_session:
                replacement = await claim_work_item(
                    takeover_session,
                    work_item_id=item.record.id,
                    worker_id="worker-new",
                    source=_source_identity(),
                    lease_seconds=30,
                    now=started + timedelta(seconds=5),
                )
                await takeover_session.commit()
                assert replacement.lease_token == old_claim.lease_token + 1
        return checked

    monkeypatch.setattr(generation_runtime_repository, "_require_live_lease", claim_after_old_read)
    if outcome == "complete":
        operation = complete_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=old_claim.lease_token,
            output_json={"race": "old"},
            output_hash=content_hash({"race": "old"}),
            now=started + timedelta(seconds=4),
        )
    else:
        operation = fail_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-old",
            lease_token=old_claim.lease_token,
            failure=_failure(),
            now=started + timedelta(seconds=4),
        )
    with pytest.raises(LeaseLostError):
        await operation

    async with db_session_factory() as verify_session:
        current = await verify_session.get(GenerationWorkItemModel, item.record.id)
        assert current is not None
        assert current.status == "running"
        assert current.lease_owner == "worker-new"
        assert current.lease_token == old_claim.lease_token + 1
        assert current.output_json is None
        assert current.error_code is None
        assert (
            await verify_session.scalar(
                select(func.count())
                .select_from(GenerationEventModel)
                .where(GenerationEventModel.work_item_id == item.record.id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_reconciliation_cas_rejects_racing_reconciler_without_duplicate_event(
    db_session, db_session_factory, monkeypatch
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:reconcile-race",
            stage="section_writing",
            input_hash="input-reconcile-race",
            definition_hash="definition-reconcile-race",
            max_attempts=1,
        ),
    )
    started = datetime(2026, 9, 11, tzinfo=UTC)
    await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-lost",
        source=_source_identity(),
        lease_seconds=5,
        now=started,
    )
    await db_session.commit()

    original_execute = generation_runtime_repository._execute_fenced_update
    winner_done = False

    async def winner_reconciles_first(session, statement):
        nonlocal winner_done
        if session is db_session and not winner_done:
            winner_done = True
            async with db_session_factory() as winner_session:
                winning_item = await reconcile_expired_work_item(
                    winner_session,
                    work_item_id=item.record.id,
                    now=started + timedelta(seconds=5),
                )
                assert winning_item.status == "failed_terminal"
                await winner_session.commit()
        return await original_execute(session, statement)

    monkeypatch.setattr(
        generation_runtime_repository,
        "_execute_fenced_update",
        winner_reconciles_first,
    )
    with pytest.raises(WorkItemUnavailable, match="changed before exhausted-attempt"):
        await reconcile_expired_work_item(
            db_session,
            work_item_id=item.record.id,
            now=started + timedelta(seconds=5),
        )

    async with db_session_factory() as verify_session:
        current = await verify_session.get(GenerationWorkItemModel, item.record.id)
        assert current is not None
        assert current.status == "failed_terminal"
        assert current.error_code == "budget_exhausted"
        assert (
            await verify_session.scalar(
                select(func.count())
                .select_from(GenerationEventModel)
                .where(GenerationEventModel.work_item_id == item.record.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_expired_attempt_reconciliation_survives_restart(
    db_session, db_session_factory
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:reconcile-after-restart",
            stage="section_writing",
            input_hash="input-reconcile",
            definition_hash="definition-reconcile",
            max_attempts=1,
        ),
    )
    started = datetime(2026, 9, 9, tzinfo=UTC)
    first_claim = await claim_work_item(
        db_session,
        work_item_id=item.record.id,
        worker_id="worker-lost",
        source=_source_identity(),
        lease_seconds=10,
        now=started,
    )
    await db_session.commit()

    async with db_session_factory() as restarted_session:
        reconciled = await reconcile_expired_work_item(
            restarted_session,
            work_item_id=item.record.id,
            now=started + timedelta(seconds=10),
        )
        await restarted_session.commit()
        assert reconciled.status == "failed_terminal"
        assert reconciled.error_class == "budget_exhausted"
        assert reconciled.lease_owner is None
        assert reconciled.lease_token == first_claim.lease_token
        assert (
            await restarted_session.scalar(
                select(func.count())
                .select_from(GenerationEventModel)
                .where(
                    GenerationEventModel.work_item_id == item.record.id,
                    GenerationEventModel.event_type == "work_item_attempts_exhausted",
                )
            )
            == 1
        )
        run = await restarted_session.get(GenerationRunModel, admitted.record.id)
        assert run is not None
        assert run.status == "failed_terminal"

    async with db_session_factory() as restarted_session:
        repeated = await reconcile_expired_work_item(
            restarted_session,
            work_item_id=item.record.id,
            now=started + timedelta(seconds=20),
        )
        assert repeated.status == "failed_terminal"
        assert (
            await restarted_session.scalar(
                select(func.count())
                .select_from(GenerationEventModel)
                .where(GenerationEventModel.work_item_id == item.record.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_events_append_with_per_run_sequence_and_reject_mutation(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item_result = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:orient",
            stage="section_writing",
            input_hash="input-orient",
            definition_hash="writer-v1",
        ),
    )

    first = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="work_item_queued",
        work_item_id=item_result.record.id,
        safe_payload={"attempt": 1},
    )
    second = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="work_item_started",
        work_item_id=item_result.record.id,
    )

    assert (first.seq, second.seq) == (1, 2)
    assert second.stage == "section_writing"
    assert second.status == "queued"
    first.error_code = "rewritten"
    with pytest.raises(ValueError, match="append-only"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_run_status_is_owner_scoped_and_ready_output_is_immutable(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    other_owner, _other_lesson = await _seed_lesson(db_session, suffix="b")
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)

    assert (
        await get_run_status(db_session, run_id=admitted.record.id, owner_user_id=other_owner)
        is None
    )
    visible = await get_run_status(db_session, run_id=admitted.record.id, owner_user_id=owner_id)
    assert visible is not None
    assert visible.status == "queued"

    run = await db_session.get(GenerationRunModel, admitted.record.id)
    assert run is not None
    run.output_artifact_type = "shared_lesson_document"
    run.output_artifact_id = "document-1"
    run.output_revision = 1
    run.output_hash = "sha256:document-1"
    run.status = "ready"
    await db_session.flush()

    ready_event = await append_event(
        db_session,
        run_id=admitted.record.id,
        event_type="run_ready_observed",
        safe_payload={"source": "test"},
    )
    assert ready_event.status == "ready"
    assert run.status == "ready"
    assert run.output_hash == "sha256:document-1"

    run.output_hash = "sha256:document-2"
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_work_item_ready_output_is_immutable(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="document-qa",
            stage="document_qa",
            input_hash="input-qa",
            definition_hash="qa-v1",
        ),
    )

    work_item = await db_session.get(GenerationWorkItemModel, item.record.id)
    assert work_item is not None
    work_item.output_json = {"passed": True}
    work_item.output_hash = "sha256:qa-passed"
    work_item.status = "ready"
    await db_session.flush()

    work_item.output_hash = "sha256:qa-failed"
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_finalize_run_requires_persisted_verified_artifact_and_is_idempotent(
    db_session,
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:final-output",
            stage="section_writing",
            input_hash="input-final",
            definition_hash="definition-final",
        ),
    )
    now = datetime(2026, 9, 18, tzinfo=UTC)
    await _complete_item(
        db_session,
        item_id=item.record.id,
        worker_id="finalizer-worker",
        value={"sections": [{"body": "complete"}]},
        now=now,
    )
    artifact_json = {"document": {"sections": ["verified"]}}
    request = _finalization_request()
    run = await finalize_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        finalization=request,
        source_verifier=_verify_source,
        artifact_loader=_load_verified_artifact(artifact_json),
        now=now + timedelta(seconds=2),
    )
    assert run.status == "ready"
    assert run.output_artifact_type == request.output_artifact_type
    assert run.output_artifact_id == request.output_artifact_id
    assert run.output_revision == request.output_revision
    assert run.output_hash == content_hash(artifact_json)

    async def source_changed_after_ready(_session, _requested):
        raise AssertionError("ready result must be idempotent without a fresh source read")

    repeated = await finalize_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        finalization=request,
        source_verifier=source_changed_after_ready,
        artifact_loader=_load_verified_artifact(artifact_json),
        now=now + timedelta(seconds=3),
    )
    assert repeated.status == "ready"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationEventModel)
            .where(
                GenerationEventModel.run_id == admitted.record.id,
                GenerationEventModel.event_type == "run_ready",
            )
        )
        == 1
    )
    with pytest.raises(InvalidRunTransition, match="active or failed-recoverable"):
        await cancel_run(
            db_session,
            run_id=admitted.record.id,
            owner_user_id=owner_id,
        )
    with pytest.raises(InvalidRunTransition, match="after run termination"):
        await add_work_item(
            db_session,
            WorkItemAdmission(
                run_id=admitted.record.id,
                item_key="section:too-late",
                stage="section_writing",
                input_hash="late-input",
                definition_hash="late-definition",
            ),
        )


@pytest.mark.asyncio
async def test_running_run_accepts_dynamic_items_but_finalization_rechecks_workset(
    db_session,
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    first = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:first-stage",
            stage="composer",
            input_hash="input-first",
            definition_hash="definition-first",
        ),
    )
    await _complete_item(
        db_session,
        item_id=first.record.id,
        worker_id="composer-worker",
        value={"composition": "done"},
        now=datetime(2026, 9, 23, tzinfo=UTC),
    )
    late_dynamic = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="media:generated-after-composition",
            stage="media_generation",
            input_hash="input-media",
            definition_hash="definition-media",
        ),
    )
    assert late_dynamic.created is True
    with pytest.raises(InvalidRunTransition, match="all declared work items"):
        await finalize_run(
            db_session,
            run_id=admitted.record.id,
            owner_user_id=owner_id,
            finalization=_finalization_request(),
            source_verifier=_verify_source,
            artifact_loader=_load_verified_artifact({"not": "yet"}),
        )
    await db_session.refresh(admitted.record)
    assert admitted.record.status == "running"
    assert admitted.record.output_hash is None
    await db_session.refresh(late_dynamic.record)
    assert late_dynamic.record.status == "queued"


@pytest.mark.asyncio
async def test_add_work_item_refreshes_run_after_sqlite_build_lock(db_session, monkeypatch) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    original_lock = generation_runtime_repository._serialize_run_build_on_sqlite

    async def terminalize_between_read_and_lock(session, *, run_id: str) -> None:
        if session is db_session:
            await session.execute(
                update(GenerationRunModel)
                .where(GenerationRunModel.id == run_id)
                .values(
                    status="ready",
                    output_artifact_type="test_artifact",
                    output_artifact_id="test-artifact-1",
                    output_revision=1,
                    output_hash="sha256:test-artifact",
                )
            )
        await original_lock(session, run_id=run_id)

    monkeypatch.setattr(
        generation_runtime_repository,
        "_serialize_run_build_on_sqlite",
        terminalize_between_read_and_lock,
    )
    with pytest.raises(InvalidRunTransition, match="after run termination"):
        await add_work_item(
            db_session,
            WorkItemAdmission(
                run_id=admitted.record.id,
                item_key="section:late-terminal-race",
                stage="section_writing",
                input_hash="late-race-input",
                definition_hash="late-race-definition",
            ),
        )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationWorkItemModel)
            .where(
                GenerationWorkItemModel.run_id == admitted.record.id,
                GenerationWorkItemModel.item_key == "section:late-terminal-race",
            )
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "identity", "hash", "source", "callback"])
async def test_finalize_run_verification_failures_never_partially_ready(
    db_session, failure: str
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key=f"section:final-failure-{failure}",
            stage="section_writing",
            input_hash="input-final-failure",
            definition_hash="definition-final-failure",
        ),
    )
    now = datetime(2026, 9, 19, tzinfo=UTC)
    await _complete_item(
        db_session,
        item_id=item.record.id,
        worker_id="finalizer-worker",
        value={"complete": True},
        now=now,
    )
    artifact_json = {"persisted": ["value"]}
    loader = _load_verified_artifact(artifact_json)
    verifier = _verify_source
    expected_error = ArtifactVerificationError
    request = _finalization_request()
    if failure == "missing":

        async def loader(_session, *_args):
            raise LookupError("artifact does not exist")
    elif failure == "identity":
        loader = _load_verified_artifact(artifact_json, artifact_id="other-document")
    elif failure == "hash":
        loader = _load_verified_artifact(artifact_json, output_hash="sha256:wrong")
    elif failure == "source":

        async def verifier(_session, _requested):
            return _source_identity().model_copy(update={"source_hash": "sha256:changed"})

        expected_error = SourceIdentityConflict
    else:

        async def loader(session, *_args):
            run = await session.get(GenerationRunModel, admitted.record.id)
            assert run is not None
            run.stage = "must-roll-back"
            await session.flush()
            raise LookupError("verification adapter failed")

    with pytest.raises(expected_error):
        await finalize_run(
            db_session,
            run_id=admitted.record.id,
            owner_user_id=owner_id,
            finalization=request,
            source_verifier=verifier,
            artifact_loader=loader,
            now=now + timedelta(seconds=2),
        )
    await db_session.refresh(admitted.record)
    assert admitted.record.status == "running"
    assert admitted.record.output_hash is None
    if failure == "callback":
        assert admitted.record.stage == "section_composition"


@pytest.mark.asyncio
async def test_finalize_run_requires_all_work_items_ready(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    for key in ("ready", "unfinished"):
        item = await add_work_item(
            db_session,
            WorkItemAdmission(
                run_id=admitted.record.id,
                item_key=f"section:{key}",
                stage="section_writing",
                input_hash=f"input-{key}",
                definition_hash=f"definition-{key}",
            ),
        )
        if key == "ready":
            await _complete_item(
                db_session,
                item_id=item.record.id,
                worker_id=f"worker-{key}",
                value={"ready": True},
                now=datetime(2026, 9, 20, tzinfo=UTC),
            )

    with pytest.raises(InvalidRunTransition, match="all declared work items"):
        await finalize_run(
            db_session,
            run_id=admitted.record.id,
            owner_user_id=owner_id,
            finalization=_finalization_request(),
            source_verifier=_verify_source,
            artifact_loader=_load_verified_artifact({"should": "not-load"}),
        )
    await db_session.refresh(admitted.record)
    assert admitted.record.status == "running"
    assert admitted.record.output_artifact_id is None


@pytest.mark.asyncio
async def test_cancel_run_fences_remaining_items_and_preserves_ready_sibling(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    ready = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:keep-ready",
            stage="section_writing",
            input_hash="input-ready",
            definition_hash="definition-ready",
        ),
    )
    await _complete_item(
        db_session,
        item_id=ready.record.id,
        worker_id="worker-ready",
        value={"ready": ["preserve"]},
        now=datetime(2026, 9, 21, tzinfo=UTC),
    )
    running = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:cancel-running",
            stage="section_writing",
            input_hash="input-running",
            definition_hash="definition-running",
        ),
    )
    queued = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:cancel-queued",
            stage="section_writing",
            input_hash="input-queued",
            definition_hash="definition-queued",
        ),
    )
    started = datetime(2026, 9, 21, 0, 0, 2, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=running.record.id,
        worker_id="worker-running",
        source=_source_identity(),
        now=started,
    )
    compatibility = _checkpoint_compatibility(
        input_hash=running.record.input_hash,
        definition_hash=running.record.definition_hash,
        composition_identity=None,
    )
    await persist_checkpoint(
        db_session,
        work_item_id=running.record.id,
        worker_id="worker-running",
        lease_token=claim.lease_token,
        compatibility=compatibility,
        payload={"keep": "checkpoint"},
        now=started + timedelta(seconds=1),
    )
    previous_token = claim.lease_token
    late_queued = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="media:admitted-after-run-start",
            stage="media_generation",
            input_hash="input-late-media",
            definition_hash="definition-late-media",
        ),
    )

    cancelled = await cancel_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        now=started + timedelta(seconds=2),
    )
    assert cancelled.status == "cancelled"
    await db_session.refresh(ready.record)
    await db_session.refresh(running.record)
    await db_session.refresh(queued.record)
    await db_session.refresh(late_queued.record)
    assert ready.record.status == "ready"
    assert ready.record.output_json == {"ready": ["preserve"]}
    assert running.record.status == "cancelled"
    assert running.record.lease_owner is None
    assert running.record.lease_expires_at is None
    assert running.record.lease_token == previous_token + 1
    assert running.record.checkpoint_json["payload"] == {"keep": "checkpoint"}
    assert queued.record.status == "cancelled"
    assert queued.record.lease_token == 1
    assert late_queued.record.status == "cancelled"
    assert late_queued.record.error_code == "cancelled"
    assert running.record.error_code == queued.record.error_code == "cancelled"
    assert running.record.error_class == queued.record.error_class == "cancelled"

    with pytest.raises(LeaseLostError):
        await complete_work_item(
            db_session,
            work_item_id=running.record.id,
            worker_id="worker-running",
            lease_token=previous_token,
            output_json={"late": True},
            output_hash=content_hash({"late": True}),
            now=started + timedelta(seconds=3),
        )
    with pytest.raises(LeaseLostError):
        await persist_checkpoint(
            db_session,
            work_item_id=running.record.id,
            worker_id="worker-running",
            lease_token=previous_token,
            compatibility=compatibility,
            payload={"late": True},
            now=started + timedelta(seconds=3),
        )
    await cancel_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        now=started + timedelta(seconds=4),
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationEventModel)
            .where(
                GenerationEventModel.run_id == admitted.record.id,
                GenerationEventModel.event_type == "run_cancelled",
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_cancel_committing_first_blocks_finalization(db_session, db_session_factory) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    item = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:terminal-race",
            stage="section_writing",
            input_hash="input-terminal-race",
            definition_hash="definition-terminal-race",
        ),
    )
    race_time = datetime(2026, 9, 22, tzinfo=UTC)
    await _complete_item(
        db_session,
        item_id=item.record.id,
        worker_id="worker-race",
        value={"item": "ready"},
        now=race_time,
    )
    await db_session.commit()
    run_id = admitted.record.id
    winner = await cancel_run(
        db_session,
        run_id=run_id,
        owner_user_id=owner_id,
        now=race_time + timedelta(seconds=3),
    )
    assert winner.status == "cancelled"
    await db_session.commit()
    with pytest.raises(InvalidRunTransition):
        await finalize_run(
            db_session,
            run_id=run_id,
            owner_user_id=owner_id,
            finalization=_finalization_request(),
            source_verifier=_verify_source,
            artifact_loader=_load_verified_artifact({"terminal": "race"}),
            now=race_time + timedelta(seconds=4),
        )
    await db_session.rollback()
    async with db_session_factory() as verify_session:
        run = await verify_session.get(GenerationRunModel, run_id)
        assert run is not None
        assert run.status == "cancelled"
        assert run.output_hash is None
        assert (
            await verify_session.scalar(
                select(func.count())
                .select_from(GenerationEventModel)
                .where(
                    GenerationEventModel.run_id == run_id,
                    GenerationEventModel.event_type == "run_ready",
                )
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_ready_item_replacement_preserves_history_and_finalizes_active_leaves(
    db_session,
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="replacement-ready")
    _build, admitted = await _admit(
        db_session, owner_id=owner_id, lesson_id=lesson_id, request_key="replacement-ready"
    )
    prior = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:original",
            stage="section_writing",
            input_hash="input-original",
            definition_hash="definition-original",
        ),
    )
    sibling = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:sibling",
            stage="section_writing",
            input_hash="input-sibling",
            definition_hash="definition-sibling",
        ),
    )
    now = datetime(2026, 9, 25, tzinfo=UTC)
    original_output = {"section": "original"}
    sibling_output = {"section": "unchanged"}
    await _complete_item(
        db_session, item_id=prior.record.id, worker_id="writer-1", value=original_output, now=now
    )
    await _complete_item(
        db_session,
        item_id=sibling.record.id,
        worker_id="writer-2",
        value=sibling_output,
        now=now + timedelta(seconds=2),
    )

    replacement_request = WorkItemAdmission(
        run_id=admitted.record.id,
        item_key="section:original-repair-1",
        stage="section_writing",
        input_hash="input-repaired",
        definition_hash="definition-v2",
        composition_identity="repair:qa-1",
    )
    replacement = await replace_work_item(
        db_session,
        WorkItemReplacement(
            predecessor_work_item_id=prior.record.id,
            owner_user_id=owner_id,
            source=_source_identity(),
            replacement=replacement_request,
        ),
        now=now + timedelta(seconds=4),
    )
    duplicate = await replace_work_item(
        db_session,
        WorkItemReplacement(
            predecessor_work_item_id=prior.record.id,
            owner_user_id=owner_id,
            source=_source_identity(),
            replacement=replacement_request,
        ),
        now=now + timedelta(seconds=5),
    )
    assert duplicate.id == replacement.id
    assert replacement.replaces_work_item_id == prior.record.id
    assert prior.record.status == "ready" and prior.record.output_json == original_output
    assert sibling.record.status == "ready" and sibling.record.output_json == sibling_output
    assert admitted.record.status == "queued"

    await _complete_item(
        db_session,
        item_id=replacement.id,
        worker_id="writer-repair",
        value={"section": "repaired"},
        now=now + timedelta(seconds=6),
    )
    artifact_json = {"document": {"sections": ["repaired", "unchanged"]}}
    run = await finalize_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        finalization=_finalization_request(),
        source_verifier=_verify_source,
        artifact_loader=_load_verified_artifact(artifact_json),
        now=now + timedelta(seconds=8),
    )
    assert run.status == "ready"
    assert prior.record.status == sibling.record.status == replacement.status == "ready"
    assert replacement.output_json == {"section": "repaired"}


@pytest.mark.asyncio
async def test_failed_recoverable_item_replacement_reopens_run_and_requires_changed_identity(
    db_session,
) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="replacement-failed")
    _build, admitted = await _admit(
        db_session, owner_id=owner_id, lesson_id=lesson_id, request_key="replacement-failed"
    )
    failed = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:recoverable",
            stage="section_writing",
            input_hash="input-before-repair",
            definition_hash="definition-before-repair",
        ),
    )
    now = datetime(2026, 9, 25, tzinfo=UTC)
    claim = await claim_work_item(
        db_session,
        work_item_id=failed.record.id,
        worker_id="writer-fails",
        source=_source_identity(),
        now=now,
    )
    await fail_work_item(
        db_session,
        work_item_id=failed.record.id,
        worker_id="writer-fails",
        lease_token=claim.lease_token,
        failure=_failure(recovery_action=RecoveryAction.RETRY),
        now=now + timedelta(seconds=1),
    )
    assert admitted.record.status == "failed_recoverable"

    same_identity = WorkItemAdmission(
        run_id=admitted.record.id,
        item_key="section:repair-bad",
        stage="section_writing",
        input_hash="input-before-repair",
        definition_hash="definition-before-repair",
    )
    base_request = WorkItemReplacement(
        predecessor_work_item_id=failed.record.id,
        owner_user_id=owner_id,
        source=_source_identity(),
        replacement=same_identity,
    )
    with pytest.raises(WorkItemConflict, match="changed work identity"):
        await replace_work_item(db_session, base_request, now=now + timedelta(seconds=2))
    with pytest.raises(RunNotFound):
        await replace_work_item(
            db_session,
            base_request.model_copy(update={"owner_user_id": "another-owner"}),
            now=now + timedelta(seconds=2),
        )
    replacement = await replace_work_item(
        db_session,
        base_request.model_copy(
            update={
                "replacement": same_identity.model_copy(
                    update={
                        "item_key": "section:repair-good",
                        "input_hash": "input-after-repair",
                        "definition_hash": "definition-after-repair",
                        "composition_identity": "repair:qa-2",
                    }
                )
            }
        ),
        now=now + timedelta(seconds=3),
    )
    assert replacement.status == "queued"
    assert replacement.replaces_work_item_id == failed.record.id
    assert failed.record.status == "failed_recoverable"
    assert admitted.record.status == "queued"
    with pytest.raises(WorkItemUnavailable):
        await claim_work_item(
            db_session,
            work_item_id=failed.record.id,
            worker_id="stale-original",
            source=_source_identity(),
            now=now + timedelta(seconds=4),
        )


@pytest.mark.asyncio
async def test_finalized_run_rejects_late_replacement(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session, suffix="replacement-after-ready")
    _build, admitted = await _admit(
        db_session, owner_id=owner_id, lesson_id=lesson_id, request_key="replacement-after-ready"
    )
    original = await add_work_item(
        db_session,
        WorkItemAdmission(
            run_id=admitted.record.id,
            item_key="section:finalized",
            stage="section_writing",
            input_hash="input-finalized",
            definition_hash="definition-finalized",
        ),
    )
    now = datetime(2026, 9, 25, tzinfo=UTC)
    await _complete_item(
        db_session,
        item_id=original.record.id,
        worker_id="writer-finalized",
        value={"section": "final"},
        now=now,
    )
    artifact_json = {"document": {"sections": ["final"]}}
    await finalize_run(
        db_session,
        run_id=admitted.record.id,
        owner_user_id=owner_id,
        finalization=_finalization_request(),
        source_verifier=_verify_source,
        artifact_loader=_load_verified_artifact(artifact_json),
        now=now + timedelta(seconds=2),
    )
    with pytest.raises(InvalidRunTransition):
        await replace_work_item(
            db_session,
            WorkItemReplacement(
                predecessor_work_item_id=original.record.id,
                owner_user_id=owner_id,
                source=_source_identity(),
                replacement=WorkItemAdmission(
                    run_id=admitted.record.id,
                    item_key="section:too-late",
                    stage="section_writing",
                    input_hash="input-after-finalization",
                    definition_hash="definition-after-finalization",
                ),
            ),
            now=now + timedelta(seconds=3),
        )
    assert admitted.record.status == "ready"


async def test_database_rejects_unknown_run_status(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    build, _admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    db_session.add(
        GenerationRunModel(
            id="invalid-status-run",
            build_id=build.id,
            run_type="shared_document",
            owner_user_id=owner_id,
            status="writing",
            stage="section_writing",
            attempt=1,
            source_artifact_type="teaching_plan",
            source_artifact_id="plan-invalid",
            source_revision=1,
            source_hash="hash",
            request_key="invalid-status",
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_work_item_cannot_use_run_only_awaiting_review_status(db_session) -> None:
    owner_id, lesson_id = await _seed_lesson(db_session)
    _build, admitted = await _admit(db_session, owner_id=owner_id, lesson_id=lesson_id)
    db_session.add(
        GenerationWorkItemModel(
            id="invalid-work-item-status",
            run_id=admitted.record.id,
            item_key="invalid",
            stage="section_writing",
            status="awaiting_review",
            attempt=1,
            max_attempts=1,
            input_hash="input",
            definition_hash="definition",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

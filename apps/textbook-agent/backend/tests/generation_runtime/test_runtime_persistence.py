from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

import infra.generation_runtime.repository as generation_runtime_repository
from infra.database.models import (
    ConceptModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    AttemptLimitExceeded,
    BuildAdmission,
    CheckpointCompatibilityError,
    LeaseLostError,
    RunAdmission,
    RunAdmissionConflict,
    RunContract,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    RunType,
    SourceIdentity,
    SourceIdentityConflict,
    WorkItemAdmission,
    WorkItemConflict,
    WorkItemContract,
    WorkItemUnavailable,
    add_work_item,
    admit_run,
    append_event,
    claim_work_item,
    create_build,
    get_run_status,
    heartbeat_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
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

    with pytest.raises(AttemptLimitExceeded, match="max_attempts"):
        await claim_work_item(
            db_session,
            work_item_id=item.record.id,
            worker_id="worker-b",
            source=_source_identity(),
            lease_seconds=10,
            now=start + timedelta(seconds=10),
        )

    await db_session.refresh(item.record)
    assert item.record.status == "running"
    assert item.record.attempt == 1
    assert item.record.lease_token == first.lease_token
    assert item.record.lease_owner == "worker-a"


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

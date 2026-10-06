"""PostgreSQL integration gates for the generic generation runtime.

These tests deliberately use an explicit PostgreSQL engine because the normal
test session is SQLite.  Every test uses unique fixture identities and removes
only rows belonging to its own build after the assertions complete.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
    BuildAdmission,
    CheckpointCompatibilityError,
    LeaseLostError,
    RunAdmission,
    RunAdmissionConflict,
    RuntimeCheckpointCompatibility,
    RunType,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemReplacement,
    add_work_item,
    admit_run,
    cancel_run,
    claim_work_item,
    complete_work_item,
    create_build,
    heartbeat_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    replace_work_item,
)

POSTGRES_URL = "postgresql+asyncpg://textbook:textbook@127.0.0.1:5432/textbook_agent"
APPLIED_RUNTIME_HEAD = "20261006_0050"


@pytest.fixture
async def pg_runtime() -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    """Connect to the local migrated database, skipping when it is unavailable."""

    url = os.environ.get("POSTGRES_TEST_URL") or POSTGRES_URL
    schema = f"runtime_test_{uuid.uuid4().hex}"
    bootstrap = create_async_engine(url, pool_pre_ping=True)
    try:
        try:
            async with bootstrap.begin() as connection:
                await connection.execute(text("SELECT 1"))
                head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                table_names = (
                    "users",
                    "concepts",
                    "units",
                    "path_versions",
                    "path_lessons",
                    "generation_builds",
                    "generation_runs",
                    "generation_work_items",
                    "generation_events",
                )
                for table_name in table_names:
                    await connection.execute(
                        text(
                            f'CREATE TABLE "{schema}"."{table_name}" '
                            f'(LIKE public."{table_name}" INCLUDING ALL)'
                        )
                    )
                trigger_rows = (
                    await connection.execute(
                        text(
                            "SELECT pg_get_triggerdef(t.oid) "
                            "FROM pg_trigger t "
                            "JOIN pg_class c ON c.oid=t.tgrelid "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname='public' AND NOT t.tgisinternal "
                            "AND c.relname LIKE 'generation%'"
                        )
                    )
                ).scalars()
                for trigger_definition in trigger_rows:
                    await connection.execute(
                        text(str(trigger_definition).replace(" ON public.", f' ON "{schema}".'))
                    )
        except (OSError, SQLAlchemyError) as exc:  # pragma: no cover
            await bootstrap.dispose()
            pytest.skip(
                f"postgres unreachable or test schema could not be prepared at {url}: {exc}"
            )
        assert head == APPLIED_RUNTIME_HEAD, f"unexpected PostgreSQL migration head: {head!r}"
        await bootstrap.dispose()
        engine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={"server_settings": {"search_path": f'"{schema}", public'}},
        )
        yield engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        if "engine" in locals():
            await engine.dispose()
        cleanup = create_async_engine(url, pool_pre_ping=True)
        try:
            async with cleanup.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await cleanup.dispose()


@pytest.fixture
async def pg_fixture(
    pg_runtime: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> AsyncIterator[dict[str, object]]:
    """Seed one isolated build and clean only its rows after the test."""

    _engine, factory = pg_runtime
    suffix = uuid.uuid4().hex
    owner_id = f"pg-runtime-owner-{suffix}"
    lesson_id = f"pg-runtime-lesson-{suffix}"
    concept_id = f"pg-runtime-concept-{suffix}"
    unit_id = f"pg-runtime-unit-{suffix}"
    path_id = f"pg-runtime-path-{suffix}"

    async with factory() as session:
        owner = UserModel(id=owner_id, email=f"{owner_id}@example.invalid")
        concept = ConceptModel(
            id=concept_id,
            canonical_slug=f"pg.runtime.{suffix}",
            subject="Science",
            title="PostgreSQL runtime fixture",
            created_by=owner_id,
        )
        unit = UnitModel(
            id=unit_id,
            owner_id=owner_id,
            title="PostgreSQL runtime fixture",
            topic="Runtime persistence",
            subject="Science",
            grade_level="Grade 7",
            destination_objective="Exercise durable runtime gates.",
        )
        path = PathVersionModel(id=path_id, unit_id=unit_id, version=1, source_plan_json={})
        lesson = PathLessonModel(
            id=lesson_id,
            path_version_id=path_id,
            concept_id=concept_id,
            concept_slug=concept.canonical_slug,
            title="PostgreSQL runtime fixture",
            objective="Exercise durable runtime gates.",
            objective_hash="pg-runtime-objective",
            primary_knowledge_type="conceptual",
            position=0,
        )
        session.add_all([owner, concept, unit, path, lesson])
        await session.commit()

    # The parent fixture owns this temporary schema and drops it with CASCADE
    # after this fixture returns. That keeps append-only event rows intact
    # while guaranteeing that no test data reaches the shared public schema.
    yield {
        "factory": factory,
        "owner_id": owner_id,
        "lesson_id": lesson_id,
        "build_id": None,
        "source": SourceIdentity(
            source_artifact_type="teaching_plan",
            source_artifact_id=f"plan-{suffix}",
            source_revision=3,
            source_hash="sha256:pg-plan-a",
        ),
    }


async def _admit(
    session: AsyncSession,
    fixture: dict[str, object],
    *,
    request_key: str,
    source: SourceIdentity | None = None,
):
    owner_id = str(fixture["owner_id"])
    lesson_id = str(fixture["lesson_id"])
    build = await create_build(
        session, BuildAdmission(owner_user_id=owner_id, path_lesson_id=lesson_id)
    )
    fixture["build_id"] = build.id
    identity = source or fixture["source"]
    result = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner_id,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=request_key,
            stage="section_writing",
            source_artifact_type=identity.source_artifact_type,
            source_artifact_id=identity.source_artifact_id,
            source_revision=identity.source_revision,
            source_hash=identity.source_hash,
        ),
    )
    return build, result


def _source(fixture: dict[str, object]) -> SourceIdentity:
    return fixture["source"]  # type: ignore[return-value]


async def _add_item(session: AsyncSession, run_id: str, item_key: str, *, suffix: str = "a"):
    return await add_work_item(
        session,
        WorkItemAdmission(
            run_id=run_id,
            item_key=item_key,
            stage="section_writing",
            input_hash=f"input-{item_key}-{suffix}",
            definition_hash=f"definition-{item_key}-{suffix}",
            composition_identity=f"composition-{item_key}-{suffix}",
        ),
    )


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_duplicate_admission_conflict_and_concurrent_same_key(
    pg_runtime, pg_fixture
) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    owner_id = str(fixture["owner_id"])
    source = _source(fixture)

    async with factory() as setup:
        build, first = await _admit(setup, fixture, request_key="pg-admission")
        await setup.commit()

    async with factory() as check:
        duplicate = await admit_run(
            check,
            RunAdmission(
                build_id=build.id,
                owner_user_id=owner_id,
                run_type=RunType.SHARED_DOCUMENT,
                request_key="pg-admission",
                stage="document_qa",
                source_artifact_type=source.source_artifact_type,
                source_artifact_id=source.source_artifact_id,
                source_revision=source.source_revision,
                source_hash=source.source_hash,
            ),
        )
        assert duplicate.created is False
        assert duplicate.record.id == first.record.id
        with pytest.raises(RunAdmissionConflict):
            await admit_run(
                check,
                RunAdmission(
                    build_id=build.id,
                    owner_user_id=owner_id,
                    run_type=RunType.SHARED_DOCUMENT,
                    request_key="pg-admission",
                    stage="section_writing",
                    source_artifact_type=source.source_artifact_type,
                    source_artifact_id=source.source_artifact_id,
                    source_revision=source.source_revision,
                    source_hash="sha256:pg-plan-conflict",
                ),
            )
        await check.rollback()

    async def concurrent_admission() -> tuple[bool, str]:
        async with factory() as session:
            try:
                result = await admit_run(
                    session,
                    RunAdmission(
                        build_id=build.id,
                        owner_user_id=owner_id,
                        run_type=RunType.SHARED_DOCUMENT,
                        request_key="pg-concurrent-admission",
                        stage="section_writing",
                        source_artifact_type=source.source_artifact_type,
                        source_artifact_id=source.source_artifact_id,
                        source_revision=source.source_revision,
                        source_hash=source.source_hash,
                    ),
                )
                await session.commit()
                return result.created, result.record.id
            except Exception:
                await session.rollback()
                raise

    results = await asyncio.gather(concurrent_admission(), concurrent_admission())
    assert sorted(created for created, _run_id in results) == [False, True]
    assert len({run_id for _created, run_id in results}) == 1


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_linked_replacement_keeps_ready_sibling_and_active_leaves(
    pg_runtime, pg_fixture
) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source = _source(fixture)
    async with factory() as session:
        _build, admitted = await _admit(session, fixture, request_key="pg-replacement")
        target = await _add_item(session, admitted.record.id, "section:target")
        sibling = await _add_item(session, admitted.record.id, "section:sibling")
        await session.commit()

    now = datetime.now(UTC)
    async with factory() as session:
        target_claim = await claim_work_item(
            session,
            work_item_id=target.record.id,
            worker_id="pg-target-worker",
            source=source,
            now=now,
        )
        await complete_work_item(
            session,
            work_item_id=target.record.id,
            worker_id="pg-target-worker",
            lease_token=target_claim.lease_token,
            output_json={"section": "target", "text": "original"},
            output_hash=content_hash({"section": "target", "text": "original"}),
            now=now + timedelta(seconds=1),
        )
        sibling_claim = await claim_work_item(
            session,
            work_item_id=sibling.record.id,
            worker_id="pg-sibling-worker",
            source=source,
            now=now,
        )
        await complete_work_item(
            session,
            work_item_id=sibling.record.id,
            worker_id="pg-sibling-worker",
            lease_token=sibling_claim.lease_token,
            output_json={"section": "sibling", "text": "healthy"},
            output_hash=content_hash({"section": "sibling", "text": "healthy"}),
            now=now + timedelta(seconds=1),
        )
        replacement = await replace_work_item(
            session,
            WorkItemReplacement(
                predecessor_work_item_id=target.record.id,
                owner_user_id=str(fixture["owner_id"]),
                source=source,
                replacement=WorkItemAdmission(
                    run_id=admitted.record.id,
                    item_key="section:target-repair",
                    stage="section_writing",
                    input_hash="input-section-target-repaired",
                    definition_hash="definition-section-target-repaired",
                    composition_identity="composition-section-target-repaired",
                ),
            ),
        )
        await session.commit()

    async with factory() as verify:
        items = list(
            (
                await verify.scalars(
                    select(GenerationWorkItemModel)
                    .where(GenerationWorkItemModel.run_id == admitted.record.id)
                    .order_by(GenerationWorkItemModel.id)
                )
            ).all()
        )
        active_ids = {
            item.id
            for item in items
            if item.id
            not in {child.replaces_work_item_id for child in items if child.replaces_work_item_id}
        }
        assert replacement.id in active_ids
        assert sibling.record.id in active_ids
        assert target.record.id not in active_ids
        persisted_sibling = await verify.get(GenerationWorkItemModel, sibling.record.id)
        assert persisted_sibling is not None
        assert persisted_sibling.status == "ready"
        assert persisted_sibling.output_json == {"section": "sibling", "text": "healthy"}


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_expired_lease_recovery_rejects_stale_fence(pg_runtime, pg_fixture) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source = _source(fixture)
    now = datetime.now(UTC)
    async with factory() as session:
        _build, admitted = await _admit(session, fixture, request_key="pg-lease-recovery")
        item = await _add_item(session, admitted.record.id, "section:lease")
        await session.commit()

    async with factory() as first_session:
        first_claim = await claim_work_item(
            first_session,
            work_item_id=item.record.id,
            worker_id="pg-worker-old",
            source=source,
            lease_seconds=1,
            now=now,
        )
        old_token = first_claim.lease_token
        await first_session.commit()

    async with factory() as recovered_session:
        recovered = await claim_work_item(
            recovered_session,
            work_item_id=item.record.id,
            worker_id="pg-worker-recovered",
            source=source,
            lease_seconds=30,
            now=now + timedelta(seconds=2),
        )
        assert recovered.attempt == 2
        assert recovered.lease_token != old_token
        await recovered_session.commit()

    async with factory() as stale_session:
        with pytest.raises(LeaseLostError):
            await complete_work_item(
                stale_session,
                work_item_id=item.record.id,
                worker_id="pg-worker-old",
                lease_token=old_token,
                output_json={"late": True},
                output_hash=content_hash({"late": True}),
                now=now + timedelta(seconds=3),
            )
        await stale_session.rollback()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_checkpoint_mismatch_refuses_reuse(pg_runtime, pg_fixture) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source = _source(fixture)
    now = datetime.now(UTC)
    async with factory() as session:
        _build, admitted = await _admit(session, fixture, request_key="pg-checkpoint")
        item = await _add_item(session, admitted.record.id, "section:checkpoint")
        await session.commit()

    async with factory() as session:
        claimed = await claim_work_item(
            session,
            work_item_id=item.record.id,
            worker_id="pg-checkpoint-worker",
            source=source,
            now=now,
        )
        compatibility = RuntimeCheckpointCompatibility(
            schema_version=1,
            source_revision=source.source_revision,
            source_hash=source.source_hash,
            input_hash=item.record.input_hash,
            definition_hash=item.record.definition_hash,
            composition_identity=item.record.composition_identity,
        )
        await persist_checkpoint(
            session,
            work_item_id=item.record.id,
            worker_id="pg-checkpoint-worker",
            lease_token=claimed.lease_token,
            compatibility=compatibility,
            payload={"checkpoint": "healthy"},
            now=now,
        )
        with pytest.raises(CheckpointCompatibilityError):
            await load_compatible_checkpoint(
                session,
                work_item_id=item.record.id,
                worker_id="pg-checkpoint-worker",
                lease_token=claimed.lease_token,
                compatibility=compatibility.model_copy(update={"source_hash": "sha256:changed"}),
                now=now,
            )
        await session.rollback()


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_cancellation_fences_late_worker_and_preserves_ready_sibling(
    pg_runtime, pg_fixture
) -> None:
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source = _source(fixture)
    now = datetime.now(UTC)
    async with factory() as session:
        _build, admitted = await _admit(session, fixture, request_key="pg-cancel")
        ready = await _add_item(session, admitted.record.id, "section:ready")
        running = await _add_item(session, admitted.record.id, "section:running")
        ready_claim = await claim_work_item(
            session,
            work_item_id=ready.record.id,
            worker_id="pg-ready-worker",
            source=source,
            now=now,
        )
        await complete_work_item(
            session,
            work_item_id=ready.record.id,
            worker_id="pg-ready-worker",
            lease_token=ready_claim.lease_token,
            output_json={"ready": True},
            output_hash=content_hash({"ready": True}),
            now=now + timedelta(seconds=1),
        )
        running_claim = await claim_work_item(
            session,
            work_item_id=running.record.id,
            worker_id="pg-late-worker",
            source=source,
            now=now,
        )
        await session.commit()

    async with factory() as canceller:
        cancelled = await cancel_run(
            canceller,
            run_id=admitted.record.id,
            owner_user_id=str(fixture["owner_id"]),
            now=now + timedelta(seconds=2),
        )
        assert cancelled.status == "cancelled"
        await canceller.commit()

    async with factory() as late_session:
        with pytest.raises(LeaseLostError):
            await complete_work_item(
                late_session,
                work_item_id=running.record.id,
                worker_id="pg-late-worker",
                lease_token=running_claim.lease_token,
                output_json={"late": True},
                output_hash=content_hash({"late": True}),
                now=now + timedelta(seconds=3),
            )
        await late_session.rollback()

    async with factory() as verify:
        persisted_ready = await verify.get(GenerationWorkItemModel, ready.record.id)
        persisted_running = await verify.get(GenerationWorkItemModel, running.record.id)
        persisted_run = await verify.get(GenerationRunModel, admitted.record.id)
        assert persisted_run is not None and persisted_run.status == "cancelled"
        assert persisted_ready is not None and persisted_ready.status == "ready"
        assert persisted_running is not None and persisted_running.status == "cancelled"
        assert persisted_running.output_json is None


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_concurrent_claims_then_run_lock_do_not_deadlock(
    pg_runtime, pg_fixture
) -> None:
    """Parallel leaves claim and then re-lock the Run in one transaction.

    Claim used to take the Run FOR SHARE; each leaf's next step (checkpoint
    load/heartbeat) locks the Run FOR UPDATE, so two overlapping leaves
    deadlocked on the share-to-exclusive upgrade.
    """
    _engine, factory = pg_runtime
    fixture = pg_fixture
    source = _source(fixture)
    async with factory() as session:
        _build, admitted = await _admit(session, fixture, request_key="pg-claim-deadlock")
        first = await _add_item(session, admitted.record.id, "section:first")
        left = await _add_item(session, admitted.record.id, "section:left")
        right = await _add_item(session, admitted.record.id, "section:right")
        await session.commit()
    # Move the Run to running so later claims take the "already running" branch.
    async with factory() as session:
        await claim_work_item(
            session, work_item_id=first.record.id, worker_id="pg-first", source=source
        )
        await session.commit()

    async def leaf(item_id: str, worker: str) -> int:
        async with factory() as session:
            claimed = await claim_work_item(
                session, work_item_id=item_id, worker_id=worker, source=source
            )
            await asyncio.sleep(0.3)  # let the sibling leaf finish its claim
            await heartbeat_work_item(
                session,
                work_item_id=item_id,
                worker_id=worker,
                lease_token=claimed.lease_token,
            )
            await session.commit()
            return int(claimed.lease_token)

    tokens = await asyncio.wait_for(
        asyncio.gather(leaf(left.record.id, "pg-left"), leaf(right.record.id, "pg-right")),
        timeout=30,
    )
    assert len(tokens) == 2

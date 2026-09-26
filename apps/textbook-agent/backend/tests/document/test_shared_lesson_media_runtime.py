from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from document.shared_lesson.media import SharedFigureWorkOrder
from document.shared_lesson.media_runtime import (
    MediaRuntimeError,
    MediaSourceConflict,
    MediaWorkItemJob,
    _verify_run_source,
    accepted_section_output_hash,
    admit_figure_media_work_item,
    admit_repaired_figure_media_work_item,
    execute_figure_media_work_item,
    frozen_figure_semantic_hash,
    project_media_readiness,
)
from document.shared_lesson.models import SharedSection
from infra.database.models import (
    ConceptModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    BuildAdmission,
    ErrorClass,
    LeaseLostError,
    RunAdmission,
    RunType,
    SourceIdentity,
    WorkItemFailure,
    admit_run,
    cancel_run,
    claim_work_item,
    create_build,
    fail_work_item,
    retry_work_item,
)
from media.generation.contracts import (
    GeneratedVisualBlock,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)

SOURCE_HASH = "a" * 64
SOURCE = SourceIdentity(
    source_artifact_type="teaching_plan",
    source_artifact_id="plan-media",
    source_revision=3,
    source_hash=SOURCE_HASH,
)


async def _seed_run(session, *, suffix: str = "a"):
    owner = f"media-owner-{suffix}"
    lesson = f"media-lesson-{suffix}"
    user = UserModel(id=owner, email=f"{owner}@example.invalid")
    concept = ConceptModel(
        id=f"media-concept-{suffix}",
        canonical_slug=f"media.{suffix}",
        subject="Science",
        title="Media fixture",
        created_by=owner,
    )
    unit = UnitModel(
        id=f"media-unit-{suffix}",
        owner_id=owner,
        title="Media fixture",
        topic="Media",
        subject="Science",
        grade_level="Grade 7",
        destination_objective="Persist media.",
    )
    version = PathVersionModel(
        id=f"media-path-{suffix}", unit_id=unit.id, version=1, source_plan_json={}
    )
    path_lesson = PathLessonModel(
        id=lesson,
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug=concept.canonical_slug,
        title="Media fixture",
        objective="Persist media.",
        objective_hash="media-objective",
        primary_knowledge_type="conceptual",
        position=0,
    )
    session.add_all([user, concept, unit, version, path_lesson])
    await session.flush()
    build = await create_build(session, BuildAdmission(owner_user_id=owner, path_lesson_id=lesson))
    admitted = await admit_run(
        session,
        RunAdmission(
            build_id=build.id,
            owner_user_id=owner,
            run_type=RunType.SHARED_DOCUMENT,
            request_key=f"media-request-{suffix}",
            stage="section_writing",
            source_artifact_type=SOURCE.source_artifact_type,
            source_artifact_id=SOURCE.source_artifact_id,
            source_revision=SOURCE.source_revision,
            source_hash=SOURCE.source_hash,
        ),
    )
    return owner, admitted.record.id


def _work(*, suffix: str = "a", required: bool = True) -> SharedFigureWorkOrder:
    figure_id = f"figure-{suffix}"
    accepted = _accepted_section(suffix)
    order = VisualGeneratorWorkOrder(
        work_order_id="placeholder",
        resource_type="shared_lesson_figure",
        dependency="section_text",
        visual=VisualPlanItem(
            id="placeholder",
            attaches_to=figure_id,
            mode="diagram",
            purpose=f"A diagram for {suffix}",
            must_show=[f"The {suffix} relationship"],
        ),
    )
    draft = SharedFigureWorkOrder(
        source_plan_id=SOURCE.source_artifact_id,
        source_plan_revision=SOURCE.source_revision,
        source_plan_hash=SOURCE.source_hash,
        section_id=f"section-{suffix}",
        section_output_hash=accepted_section_output_hash(accepted),
        figure_node_id=figure_id,
        figure_semantic_hash="0" * 64,
        required=required,
        work_order=order,
    )
    semantic_hash = frozen_figure_semantic_hash(draft, accepted)
    return draft.model_copy(
        update={
            "figure_semantic_hash": semantic_hash,
            "work_order": order.model_copy(
                update={
                    "work_order_id": f"shared-media-{semantic_hash}",
                    "visual": order.visual.model_copy(
                        update={"id": f"shared-figure-{semantic_hash[:24]}"}
                    ),
                }
            ),
        }
    )


def _accepted_section(
    suffix: str,
    *,
    caption: str | None = None,
    alt_text: str | None = None,
) -> SharedSection:
    caption = caption or f"A diagram for {suffix}"
    alt_text = alt_text or f"The {suffix} relationship"
    return SharedSection(
        id=f"section-{suffix}",
        title=f"Section {suffix}",
        position=0,
        nodes=(
            {
                "id": f"figure-{suffix}",
                "kind": "figure",
                "teaching_block_id": f"block-{suffix}",
                "display": {"caption": caption},
                "accessibility": {"alt_text": alt_text},
            },
        ),
    )


def _accepted_for(work: SharedFigureWorkOrder) -> SharedSection:
    return _accepted_section(work.section_id.removeprefix("section-"))


def _block(work: SharedFigureWorkOrder) -> GeneratedVisualBlock:
    return GeneratedVisualBlock(
        visual_id=work.work_order.visual.id,
        attaches_to=work.figure_node_id,
        mode=work.work_order.visual.mode,
        image_url="https://cdn.example.test/figure.png",
        caption=work.work_order.visual.purpose,
        alt_text=work.work_order.visual.must_show[0],
        source_work_order_id=work.work_order.work_order_id,
        status="ready",
    )


class _Executor:
    def __init__(self, work: SharedFigureWorkOrder, *, fail: bool = False) -> None:
        self.work = work
        self.fail = fail
        self.calls = 0

    async def execute_figure(self, order):
        self.calls += 1
        if self.fail:
            return []
        return [_block(self.work)]


@pytest.mark.asyncio
async def test_media_admission_is_idempotent_and_conflicts_on_same_key_hash_change(
    db_session,
) -> None:
    owner, run_id = await _seed_run(db_session)
    work = _work()
    first = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    second = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    assert first.created and not second.created
    assert first.record.id == second.record.id

    changed_section = _accepted_section("a", caption="A changed diagram")
    changed_payload = work.model_copy(
        update={
            "section_output_hash": content_hash(changed_section.model_dump(mode="json")),
            "work_order": work.work_order.model_copy(
                update={
                    "visual": work.work_order.visual.model_copy(
                        update={"purpose": "A changed diagram"}
                    )
                }
            ),
        }
    )
    with pytest.raises(MediaSourceConflict, match="semantic hash"):
        await admit_figure_media_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=SOURCE,
            work=changed_payload,
            accepted_section=changed_section,
        )


@pytest.mark.asyncio
async def test_source_mismatch_is_rejected_before_admission(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    with pytest.raises(MediaSourceConflict):
        await admit_figure_media_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=SOURCE.model_copy(update={"source_hash": "f" * 64}),
            work=_work(),
            accepted_section=_accepted_for(_work()),
        )


@pytest.mark.asyncio
async def test_ordinary_admission_locks_run_before_duplicate_scan() -> None:
    run = SimpleNamespace(
        owner_user_id="owner",
        source_artifact_type=SOURCE.source_artifact_type,
        source_artifact_id=SOURCE.source_artifact_id,
        source_revision=SOURCE.source_revision,
        source_hash=SOURCE.source_hash,
    )

    class Session:
        statement = None

        async def scalar(self, statement):
            self.statement = statement
            return run

    locked = Session()
    await _verify_run_source(
        locked,
        run_id="run",
        owner_user_id="owner",
        source=SOURCE,
        lock=True,
    )
    assert "FOR UPDATE" in str(locked.statement.compile(dialect=postgresql.dialect()))

    unlocked = Session()
    await _verify_run_source(
        unlocked,
        run_id="run",
        owner_user_id="owner",
        source=SOURCE,
    )
    assert "FOR UPDATE" not in str(unlocked.statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_changed_active_figure_requires_linked_replacement_and_preserves_sibling(
    db_session,
) -> None:
    owner, run_id = await _seed_run(db_session, suffix="replacement-admission")
    original = _work()
    sibling = _work(suffix="b", required=False)
    original_item = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=original,
        accepted_section=_accepted_for(original),
    )
    sibling_item = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=sibling,
        accepted_section=_accepted_for(sibling),
    )
    with pytest.raises(MediaRuntimeError, match="admit_repaired"):
        await admit_figure_media_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=SOURCE,
            work=_work(required=False),
            accepted_section=_accepted_for(_work(required=False)),
        )
    assert (
        await db_session.get(GenerationWorkItemModel, original_item.record.id)
    ).status == "queued"
    assert (
        await db_session.get(GenerationWorkItemModel, sibling_item.record.id)
    ).status == "queued"


@pytest.mark.asyncio
async def test_forged_work_order_is_rejected_against_accepted_section(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    accepted = _accepted_section("a")
    forged = _work().model_copy(
        update={
            "work_order": _work().work_order.model_copy(
                update={
                    "visual": _work().work_order.visual.model_copy(update={"purpose": "Forged"})
                }
            )
        }
    )
    with pytest.raises(MediaSourceConflict, match="purpose"):
        await admit_figure_media_work_item(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=SOURCE,
            work=forged,
            accepted_section=accepted,
        )


def test_missing_required_media_admission_blocks_readiness() -> None:
    work = _work()
    readiness = project_media_readiness(
        (),
        {"expected-media-item": work},
        expected_required_work_item_ids=("expected-media-item",),
    )
    assert not readiness.ready
    assert readiness.required_count == 1
    assert readiness.pending_required_work_item_ids == ("expected-media-item",)


def test_zero_admitted_items_block_on_expected_validated_figure_identity() -> None:
    readiness = project_media_readiness(
        (),
        {},
        expected_figure_identities=(("section-a", "figure-a"),),
    )
    assert not readiness.ready
    assert readiness.required_count == 1
    assert readiness.pending_required_figure_identities == ("section-a:figure-a",)


@pytest.mark.asyncio
async def test_non_ascii_section_hash_and_semantics_match_media_canonicalization(
    db_session,
) -> None:
    owner, run_id = await _seed_run(db_session, suffix="unicode")
    accepted = _accepted_section(
        "é", caption="Énergie solaire", alt_text="Relation énergie lumière"
    )
    draft = _work(suffix="é").model_copy(
        update={
            "section_output_hash": accepted_section_output_hash(accepted),
            "figure_semantic_hash": "0" * 64,
            "work_order": _work(suffix="é").work_order.model_copy(
                update={
                    "work_order_id": "placeholder",
                    "visual": _work(suffix="é").work_order.visual.model_copy(
                        update={
                            "id": "placeholder",
                            "purpose": "Énergie solaire",
                            "must_show": ["Relation énergie lumière"],
                        }
                    ),
                }
            ),
        }
    )
    semantic_hash = frozen_figure_semantic_hash(draft, accepted)
    work = draft.model_copy(
        update={
            "figure_semantic_hash": semantic_hash,
            "work_order": draft.work_order.model_copy(
                update={
                    "work_order_id": f"shared-media-{semantic_hash}",
                    "visual": draft.work_order.visual.model_copy(
                        update={"id": f"shared-figure-{semantic_hash[:24]}"}
                    ),
                }
            ),
        }
    )
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=accepted,
    )
    assert admitted.created


@pytest.mark.asyncio
async def test_media_execution_commits_checkpoint_and_ready_output(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    work = _work()
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    executor = _Executor(work)
    outcome = await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="media-worker",
            source=SOURCE,
            work=work,
            accepted_section=_accepted_for(work),
            executor=executor,
        )
    )
    assert outcome.media is not None
    stored = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert stored is not None
    assert stored.status == "ready"
    assert stored.checkpoint_json["payload"]["figure_semantic_hash"] == work.figure_semantic_hash
    assert stored.output_hash == content_hash(stored.output_json)


@pytest.mark.asyncio
async def test_invalid_media_is_recoverable_then_targeted_retry_preserves_sibling(
    db_session,
) -> None:
    owner, run_id = await _seed_run(db_session)
    failed_work = _work()
    sibling_work = _work(suffix="b", required=False)
    failed = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=failed_work,
        accepted_section=_accepted_for(failed_work),
    )
    sibling = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=sibling_work,
        accepted_section=_accepted_for(sibling_work),
    )
    sibling_outcome = await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=sibling.record.id,
            worker_id="sibling-worker",
            source=SOURCE,
            work=sibling_work,
            accepted_section=_accepted_for(sibling_work),
            executor=_Executor(sibling_work),
        )
    )
    assert sibling_outcome.media is not None
    queued_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    )
    queued_readiness = project_media_readiness(
        queued_rows, {failed.record.id: failed_work, sibling.record.id: sibling_work}
    )
    assert queued_readiness.pending_required_work_item_ids == (failed.record.id,)
    assert queued_readiness.failed_required_work_item_ids == ()

    first = await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=failed.record.id,
            worker_id="failed-worker",
            source=SOURCE,
            work=failed_work,
            accepted_section=_accepted_for(failed_work),
            executor=_Executor(failed_work, fail=True),
        )
    )
    assert first.media is None
    failed_row = await db_session.get(GenerationWorkItemModel, failed.record.id)
    assert failed_row is not None and failed_row.status == "failed_recoverable"
    current_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    )
    assert not project_media_readiness(
        current_rows, {failed.record.id: failed_work, sibling.record.id: sibling_work}
    ).ready
    failed_readiness = project_media_readiness(
        current_rows, {failed.record.id: failed_work, sibling.record.id: sibling_work}
    )
    assert failed_readiness.failed_required_work_item_ids == (failed.record.id,)
    assert failed_readiness.pending_required_work_item_ids == ()

    await retry_work_item(db_session, work_item_id=failed.record.id, owner_user_id=owner)
    retried = await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=failed.record.id,
            worker_id="retry-worker",
            source=SOURCE,
            work=failed_work,
            accepted_section=_accepted_for(failed_work),
            executor=_Executor(failed_work),
        )
    )
    assert retried.media is not None
    sibling_row = await db_session.get(GenerationWorkItemModel, sibling.record.id)
    assert sibling_row is not None and sibling_row.status == "ready"


@pytest.mark.asyncio
async def test_auth_or_programming_failure_is_terminal_without_semantic_retry(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    work = _work()
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )

    class MisconfiguredExecutor:
        async def execute_figure(self, _order):
            raise PermissionError("provider credentials rejected")

    outcome = await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="auth-worker",
            source=SOURCE,
            work=work,
            accepted_section=_accepted_for(work),
            executor=MisconfiguredExecutor(),
        )
    )
    assert outcome.error_code == "media_executor_configuration"
    row = await db_session.get(GenerationWorkItemModel, admitted.record.id)
    assert row is not None
    assert row.status == "failed_terminal"


@pytest.mark.asyncio
async def test_repaired_figure_uses_linked_replacement_and_active_readiness(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    original = _work()
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=original,
        accepted_section=_accepted_for(original),
    )
    await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="original-worker",
            source=SOURCE,
            work=original,
            accepted_section=_accepted_for(original),
            executor=_Executor(original),
        )
    )
    repaired_section = _accepted_section(
        "a", caption="A repaired diagram", alt_text="The repaired relationship"
    )
    repaired_draft = original.model_copy(
        update={
            "section_output_hash": accepted_section_output_hash(repaired_section),
            "figure_semantic_hash": "0" * 64,
            "work_order": original.work_order.model_copy(
                update={
                    "work_order_id": "placeholder",
                    "visual": original.work_order.visual.model_copy(
                        update={
                            "id": "placeholder",
                            "purpose": "A repaired diagram",
                            "must_show": ["The repaired relationship"],
                        }
                    ),
                }
            ),
        }
    )
    repaired_hash = frozen_figure_semantic_hash(repaired_draft, repaired_section)
    repaired = repaired_draft.model_copy(
        update={
            "figure_semantic_hash": repaired_hash,
            "work_order": repaired_draft.work_order.model_copy(
                update={
                    "work_order_id": f"shared-media-{repaired_hash}",
                    "visual": repaired_draft.work_order.visual.model_copy(
                        update={"id": f"shared-figure-{repaired_hash[:24]}"}
                    ),
                }
            ),
        }
    )
    replacement = await admit_repaired_figure_media_work_item(
        db_session,
        predecessor_work_item_id=admitted.record.id,
        owner_user_id=owner,
        source=SOURCE,
        work=repaired,
        accepted_section=repaired_section,
    )
    assert replacement.replaces_work_item_id == admitted.record.id
    await execute_figure_media_work_item(
        MediaWorkItemJob(
            session=db_session,
            work_item_id=replacement.id,
            worker_id="repair-worker",
            source=SOURCE,
            work=repaired,
            accepted_section=repaired_section,
            executor=_Executor(repaired),
        )
    )
    rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    )
    readiness = project_media_readiness(
        rows, {admitted.record.id: original, replacement.id: repaired}
    )
    assert readiness.ready
    assert readiness.required_count == 1
    assert readiness.failed_required_work_item_ids == ()

    mixed_rows = [
        *rows,
        GenerationWorkItemModel(
            id="section-write-sibling",
            run_id=run_id,
            item_key="write:section-a",
            stage="section_writing",
            status="ready",
            attempt=1,
            max_attempts=3,
            input_hash="section-input",
            definition_hash="section-definition",
        ),
    ]
    assert project_media_readiness(mixed_rows, {replacement.id: repaired}).ready


@pytest.mark.asyncio
async def test_stale_worker_fence_cannot_commit_media(db_session) -> None:
    owner, run_id = await _seed_run(db_session)
    work = _work()
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    claimed = await claim_work_item(
        db_session,
        work_item_id=admitted.record.id,
        worker_id="current-worker",
        source=SOURCE,
        now=datetime(2026, 9, 25, tzinfo=UTC),
    )
    with pytest.raises(LeaseLostError):
        await fail_work_item(
            db_session,
            work_item_id=claimed.id,
            worker_id="stale-worker",
            lease_token=(claimed.lease_token or 0) + 1,
            failure=WorkItemFailure(
                error_code="stale",
                error_class=ErrorClass.PROVIDER_OUTPUT,
                safe_summary="stale worker",
                recovery_action="retry",
            ),
        )


@pytest.mark.asyncio
async def test_media_provider_result_is_fenced_after_separate_session_cancellation(
    db_session,
    db_session_factory,
) -> None:
    owner, run_id = await _seed_run(db_session, suffix="cancel-during-provider")
    work = _work(suffix="cancel-during-provider")
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    await db_session.commit()

    class CancellingExecutor:
        calls = 0

        async def execute_figure(self, _order):
            self.calls += 1
            async with db_session_factory() as observer:
                await cancel_run(observer, run_id=run_id, owner_user_id=owner)
                await observer.commit()
            return [_block(work)]

    executor = CancellingExecutor()
    async with db_session_factory() as worker_session:
        with pytest.raises(LeaseLostError):
            await execute_figure_media_work_item(
                MediaWorkItemJob(
                    session=worker_session,
                    work_item_id=admitted.record.id,
                    worker_id="cancelled-media-worker",
                    source=SOURCE,
                    work=work,
                    accepted_section=_accepted_for(work),
                    executor=executor,
                )
            )

    async with db_session_factory() as verifier:
        row = await verifier.get(GenerationWorkItemModel, admitted.record.id)
        assert row is not None
        assert row.status == "cancelled"
        assert row.output_json is None
        assert executor.calls == 1

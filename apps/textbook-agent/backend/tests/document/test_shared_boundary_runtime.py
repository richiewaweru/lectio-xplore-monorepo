from __future__ import annotations

import asyncio
import weakref
from types import SimpleNamespace

import pytest
from test_shared_boundary_dispatcher import _ready_writers
from test_shared_writer_admission import _seed_ready_composer_run

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import boundary_runtime
from document.shared_lesson.boundary import BoundarySemanticVerdict, BoundaryValidationResult
from document.shared_lesson.boundary_runtime import (
    BoundaryCheckpointError,
    BoundarySourceConflict,
    BoundaryWorkOrder,
    _checkpoint_payload,
    _composition_identity_from_request,
    _logical_item_key,
    _validate_checkpoint_payload,
    accepted_section_output_hash,
    admit_boundary_work_item,
)
from document.shared_lesson.composer import (
    CompositionChoice,
    validate_and_build_composition,
)
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, make_section_writer_request
from document.shared_lesson.section_sources import build_section_sources
from document.shared_lesson.semantic_inputs import load_verified_semantic_inputs
from document.shared_lesson.work_item_inputs import load_verified_shared_lesson_inputs
from infra.database.models import GenerationWorkItemModel
from infra.execution.leases import LeaseLostError


def _section(section_id: str, position: int, text: str) -> SharedSection:
    return SharedSection(
        id=section_id,
        title=f"Section {section_id}",
        position=position,
        nodes=(
            ParagraphNode(
                id=f"{section_id}-node",
                teaching_block_id=f"{section_id}-block",
                display=ParagraphDisplay(text=text),
            ),
        ),
    )


def _source() -> TeachingPlanSource:
    sections = tuple(
        TeachingPlanSection(
            slot_id=slot,
            display_title=f"Section {slot}",
            entry_state=[f"Learner enters {slot}"],
            must_establish=[f"Learner understands {slot}"],
            avoid_repeating=[],
            bridge_from_previous=(None if slot == "s1" else "Connect s1 to s2"),
            exit_state=[f"Learner exits {slot}"],
            blocks=[
                TeachingPlanBlock(
                    id=f"{slot}-block",
                    position=0,
                    intent=f"Teach {slot}",
                    brief=f"Explain {slot}",
                    evidence=f"Learner explains {slot}",
                )
            ],
        )
        for slot in ("s1", "s2")
    )
    plan = TeachingPlan(
        arc="Teach two connected ideas",
        contract_version=2,
        learner_title="Two ideas",
        starting_state=["Learner is ready"],
        target_state=["Learner can explain both ideas"],
        teaching_plan_id="boundary-plan",
        revision=2,
        approval_status="approved",
        sections=list(sections),
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash="prep-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
        approved_at="2026-09-24T00:00:00Z",
        reviewed_by="teacher",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )


def _request(source: TeachingPlanSource, slot: str):
    plan = next(section for section in source.plan.sections if section.slot_id == slot)
    composition = validate_and_build_composition(
        section=plan,
        choices=(
            CompositionChoice(
                kind="paragraph",
                teaching_block_id=f"{slot}-block",
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    return make_section_writer_request(section=plan, composition=composition, tasks=())


def test_boundary_work_order_freezes_both_section_hashes_and_compositions() -> None:
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 1, "The second idea.")
    work = BoundaryWorkOrder(
        source_plan_id="plan",
        source_plan_revision=3,
        source_plan_hash="a" * 64,
        previous_section_id=previous.id,
        previous_section_output_hash=accepted_section_output_hash(previous),
        previous_composition_identity="composition-s1",
        next_section_id=following.id,
        next_section_output_hash=accepted_section_output_hash(following),
        next_composition_identity="composition-s2",
    )
    assert work.previous_section_output_hash != work.next_section_output_hash
    assert work.previous_composition_identity == "composition-s1"


def test_checkpoint_rejects_changed_boundary_inputs() -> None:
    work = BoundaryWorkOrder(
        source_plan_id="plan",
        source_plan_revision=3,
        source_plan_hash="a" * 64,
        previous_section_id="s1",
        previous_section_output_hash="b" * 64,
        previous_composition_identity="composition-s1",
        next_section_id="s2",
        next_section_output_hash="c" * 64,
        next_composition_identity="composition-s2",
    )
    payload = _checkpoint_payload(work)
    _validate_checkpoint_payload(payload, work)
    with pytest.raises(BoundaryCheckpointError):
        _validate_checkpoint_payload(
            payload
            | {
                "work": work.model_copy(update={"next_section_output_hash": "d" * 64}).model_dump(
                    mode="json"
                )
            },
            work,
        )


def test_writer_composition_identity_matches_runtime_canonical_hash() -> None:
    source = _source()
    request = _request(source, "s1")
    first = _composition_identity_from_request(request)
    second = _composition_identity_from_request(request.model_copy(deep=True))
    assert first == second
    assert len(first) == 64


@pytest.mark.asyncio
async def test_boundary_batch_settles_siblings_before_reraising_unexpected_error(
    monkeypatch,
) -> None:
    original = RuntimeError("unexpected boundary persistence defect")
    sibling_settled = asyncio.Event()

    async def execute(job):
        if job.work_item_id == "first":
            raise original
        await asyncio.sleep(0.02)
        sibling_settled.set()
        return boundary_runtime.BoundaryRuntimeOutcome(work_item_id=job.work_item_id)

    monkeypatch.setattr(boundary_runtime, "execute_boundary_work_item", execute)
    jobs = tuple(
        boundary_runtime.BoundaryWorkItemJob(
            session=object(),
            work_item_id=work_item_id,
            worker_id="boundary-batch-test",
            source=SimpleNamespace(),
            previous_section=SimpleNamespace(),
            next_section=SimpleNamespace(),
            writer_requests={},
        )
        for work_item_id in ("first", "sibling")
    )

    with pytest.raises(RuntimeError) as raised:
        await boundary_runtime.execute_boundary_work_items(jobs, concurrency=2)

    assert raised.value is original
    assert sibling_settled.is_set()


@pytest.mark.asyncio
async def test_boundary_job_commits_before_sibling_finishes(monkeypatch) -> None:
    lock = asyncio.Lock()
    first_locked = asyncio.Event()
    commits = []

    class LockingSession:
        def __init__(self, name):
            self.name = name
            self.owns_lock = False

        async def commit(self):
            commits.append(self.name)
            if self.owns_lock:
                self.owns_lock = False
                lock.release()

        async def rollback(self):
            if self.owns_lock:
                self.owns_lock = False
                lock.release()

    async def execute(job):
        session = job.session
        if job.work_item_id == "second":
            await first_locked.wait()
        await lock.acquire()
        session.owns_lock = True
        if job.work_item_id == "first":
            first_locked.set()
        return boundary_runtime.BoundaryRuntimeOutcome(work_item_id=job.work_item_id)

    monkeypatch.setattr(boundary_runtime, "execute_boundary_work_item", execute)
    jobs = tuple(
        boundary_runtime.BoundaryWorkItemJob(
            session=LockingSession(item_id),
            work_item_id=item_id,
            worker_id="boundary-lock-test",
            source=SimpleNamespace(),
            previous_section=SimpleNamespace(),
            next_section=SimpleNamespace(),
            writer_requests={},
        )
        for item_id in ("first", "second")
    )

    outcomes = await asyncio.wait_for(
        boundary_runtime.execute_boundary_work_items(jobs, concurrency=2), timeout=1
    )

    assert [outcome.work_item_id for outcome in outcomes] == ["first", "second"]
    assert set(commits) == {"first", "second"}


@pytest.mark.asyncio
async def test_boundary_batch_cancellation_settles_sibling_tasks(monkeypatch) -> None:
    sibling_cancelled = asyncio.Event()
    started = asyncio.Event()

    async def execute(job):
        if job.work_item_id == "sibling":
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                sibling_cancelled.set()
                raise
        await started.wait()
        await asyncio.Future()

    monkeypatch.setattr(boundary_runtime, "execute_boundary_work_item", execute)
    jobs = tuple(
        boundary_runtime.BoundaryWorkItemJob(
            session=object(),
            work_item_id=work_item_id,
            worker_id="boundary-cancel-test",
            source=SimpleNamespace(),
            previous_section=SimpleNamespace(),
            next_section=SimpleNamespace(),
            writer_requests={},
        )
        for work_item_id in ("cancel", "sibling")
    )
    task = asyncio.create_task(boundary_runtime.execute_boundary_work_items(jobs, concurrency=2))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert sibling_cancelled.is_set()


@pytest.mark.asyncio
async def test_detached_boundary_validator_retains_shared_cap_across_dispatches(monkeypatch) -> None:
    monkeypatch.setattr(boundary_runtime, "MAX_CONCURRENT_BOUNDARIES", 1)
    monkeypatch.setattr(
        boundary_runtime,
        "_BOUNDARY_VALIDATION_SEMAPHORES",
        weakref.WeakKeyDictionary(),
    )
    loop = asyncio.get_running_loop()
    release = asyncio.Event()
    cancelled = asyncio.Event()
    provider_started = 0
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 1, "The second idea.")
    result = BoundaryValidationResult(
        status="pass",
        previous_section=previous,
        next_section=following,
        semantic_calls=1,
    )

    async def cancellation_resistant_validator():
        nonlocal provider_started
        provider_started += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
        return result

    async def next_dispatch_validator():
        nonlocal provider_started
        provider_started += 1
        return result

    with pytest.raises(boundary_runtime.BoundaryValidationDeadlineExceeded):
        await boundary_runtime._run_boundary_validation_before_deadline(
            cancellation_resistant_validator,
            deadline=loop.time() + 0.02,
        )

    await asyncio.wait_for(cancelled.wait(), timeout=0.1)
    second_dispatch = asyncio.create_task(
        boundary_runtime._run_boundary_validation_before_deadline(
            next_dispatch_validator,
            deadline=loop.time() + 1,
        )
    )
    await asyncio.sleep(0.02)
    assert provider_started == 1
    assert second_dispatch.done() is False

    release.set()
    assert await second_dispatch == result
    assert provider_started == 2


@pytest.mark.asyncio
async def test_boundary_source_conflict_does_not_get_reclassified_as_provider_failure() -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 2, "The second idea.")
    from document.shared_lesson.boundary_runtime import _plan_pair

    with pytest.raises(BoundarySourceConflict, match="position"):
        _plan_pair(source, previous, following)


def test_boundary_work_order_is_closed() -> None:
    with pytest.raises(ValueError):
        BoundaryWorkOrder(
            source_plan_id="plan",
            source_plan_revision=3,
            source_plan_hash="a" * 64,
            previous_section_id="s1",
            previous_section_output_hash="b" * 64,
            previous_composition_identity="composition-s1",
            next_section_id="s2",
            next_section_output_hash="c" * 64,
            next_composition_identity="composition-s2",
            unexpected="forbidden",
        )


def test_active_writer_replacement_keeps_the_original_logical_section_key() -> None:
    predecessor = SimpleNamespace(id="writer-old", item_key="write:s1", replaces_work_item_id=None)
    replacement = SimpleNamespace(
        id="writer-new", item_key="write:s1:repair-1", replaces_work_item_id="writer-old"
    )
    assert (
        _logical_item_key(replacement, {predecessor.id: predecessor, replacement.id: replacement})
        == "write:s1"
    )


@pytest.mark.asyncio
async def test_replacement_during_validation_cannot_make_boundary_ready(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 1, "Connect s1 to s2. The second idea.")
    previous_request = _request(source, "s1")
    next_request = _request(source, "s2")
    previous_identity = _composition_identity_from_request(previous_request)
    next_identity = _composition_identity_from_request(next_request)
    work = boundary_runtime._work_order(
        boundary_runtime._identity(source),
        previous,
        following,
        previous_composition_identity=previous_identity,
        next_composition_identity=next_identity,
    )
    admission = boundary_runtime._item_request("run-1", work, max_attempts=3)
    item = SimpleNamespace(
        id="boundary-item",
        run_id="run-1",
        stage=admission.stage,
        input_hash=admission.input_hash,
        definition_hash=admission.definition_hash,
        composition_identity=admission.composition_identity,
        lease_token=1,
    )

    calls = 0

    async def writer_check(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BoundarySourceConflict("writer replacement won the fence")
        return SimpleNamespace(), SimpleNamespace()

    class Session:
        async def scalar(self, _statement):
            return "run-1"

        async def commit(self):
            return None

    async def claim(*_args, **_kwargs):
        return item

    failed = []

    async def fail(*_args, **kwargs):
        failed.append(kwargs["failure"].error_code)

    async def checkpoint(*_args, **_kwargs):
        return None

    async def validate(*_args, **_kwargs):
        return BoundaryValidationResult(
            status="pass",
            previous_section=previous,
            next_section=following,
            semantic_calls=1,
        )

    monkeypatch.setattr(boundary_runtime, "_verify_active_writer_outputs", writer_check)
    monkeypatch.setattr(boundary_runtime, "claim_work_item", claim)
    monkeypatch.setattr(boundary_runtime, "load_compatible_checkpoint", checkpoint)
    monkeypatch.setattr(boundary_runtime, "persist_checkpoint", checkpoint)
    monkeypatch.setattr(boundary_runtime, "validate_and_repair_boundary", validate)
    monkeypatch.setattr(boundary_runtime, "fail_work_item", fail)

    result = await boundary_runtime.execute_boundary_work_item(
        boundary_runtime.BoundaryWorkItemJob(
            session=Session(),
            work_item_id=item.id,
            worker_id="boundary-worker",
            source=source,
            previous_section=previous,
            next_section=following,
            writer_requests={"s1": previous_request, "s2": next_request},
        )
    )

    assert result.error_code == "boundary_source_changed_before_commit"
    assert failed == ["boundary_source_changed_before_commit"]
    assert calls == 2


@pytest.mark.asyncio
async def test_provider_sees_committed_lease_checkpoint_and_stale_result_is_fenced(
    db_session, db_session_factory
) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    semantic = await load_verified_semantic_inputs(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
    )
    section_sources = tuple(
        source_item
        for section in source.plan.sections
        for source_item in build_section_sources(semantic, section)
    )
    verified = await load_verified_shared_lesson_inputs(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        tasks=semantic.tasks,
        sources=section_sources,
    )
    sections = {section.id: section for section in verified.sections}
    writer_requests = {admission.section.slot_id: admission.request for admission in admissions}
    writer_identities = {
        admission.section.slot_id: admission.composition_identity for admission in admissions
    }
    previous_id, next_id = tuple(section.slot_id for section in source.plan.sections)
    admitted = await admit_boundary_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        previous_section=sections[previous_id],
        next_section=sections[next_id],
        previous_composition_identity=writer_identities[previous_id],
        next_composition_identity=writer_identities[next_id],
    )
    await db_session.commit()

    observed = False

    async def stale_provider_result(_request):
        nonlocal observed
        async with db_session_factory() as observer:
            item = await observer.get(GenerationWorkItemModel, admitted.record.id)
            assert item is not None
            assert item.status == "running"
            assert item.lease_token is not None and item.lease_token >= 1
            assert item.checkpoint_json is not None
            observed = True
            # Simulate a newer claimant taking the lease while the provider is
            # computing. Its result must fail the original fencing token.
            item.lease_token += 1
            await observer.commit()
        return BoundarySemanticVerdict(status="pass")

    async with db_session_factory() as worker_session:
        with pytest.raises(LeaseLostError):
            await boundary_runtime.execute_boundary_work_item(
                boundary_runtime.BoundaryWorkItemJob(
                    session=worker_session,
                    work_item_id=admitted.record.id,
                    worker_id="boundary-runtime-test",
                    source=source,
                    previous_section=sections[previous_id],
                    next_section=sections[next_id],
                    writer_requests=writer_requests,
                    semantic_validator=stale_provider_result,
                )
            )
        await worker_session.rollback()

    assert observed is True
    async with db_session_factory() as verifier:
        item = await verifier.get(GenerationWorkItemModel, admitted.record.id)
        assert item is not None
        assert item.status == "running"
        assert item.lease_token == 2
        assert item.checkpoint_json is not None

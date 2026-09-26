from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from test_shared_lesson_runtime_db import _admit_run as _admit_db_run
from test_shared_lesson_runtime_db import _seed_build as _seed_db_build
from test_shared_lesson_runtime_db import _source as _db_source
from test_shared_lesson_runtime_db import _writer_request as _db_writer_request

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode
from document.shared_lesson.runtime import (
    MAX_CONCURRENT_SECTION_WRITERS,
    SectionRuntimeError,
    SectionWriterJob,
    TeachingPlanSource,
    _record_execution_failure,
    _write_section_work_item,
    admit_section_run,
    admit_writer_work_item,
    cancel_section_run,
    compose_section_work_item,
    restart_section_run,
    retry_failed_section,
    verify_teaching_plan_source,
    verify_writer_checkpoint_payload,
    write_section_work_items,
)
from document.shared_lesson.writer import SectionWriteResult, SectionWriterRequest
from infra.database.models import GenerationWorkItemModel
from infra.generation_runtime import LeaseLostError


async def _commit_noop() -> None:
    return None


def _approved_source(plan: TeachingPlan) -> TeachingPlanSource:
    plan = plan.model_copy(update={"approval_status": "approved"})
    plan_id = str(plan.teaching_plan_id)
    revision = int(plan.revision or 1)
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan_id,
        revision=revision,
        status="approved",
        preparation_hash=plan.preparation_hash or "preparation-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
        approved_at="2026-09-24T00:00:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan_id,
        revision=revision,
        content_hash=digest,
    )


def _source() -> TeachingPlanSource:
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start with the idea",
        entry_state=["Learner is ready to learn"],
        must_establish=["Learner understands the idea"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["Learner can explain the idea"],
    )
    return _approved_source(
        TeachingPlan(
            arc="Teach a simple idea",
            contract_version=2,
            learner_title="A lesson about one idea",
            starting_state=["Learner is ready to learn"],
            target_state=["Learner can explain the idea"],
            teaching_plan_id="tp-approved-1",
            revision=3,
            sections=[section],
        )
    )


@pytest.mark.asyncio
async def test_admission_uses_generic_repository_records(monkeypatch) -> None:
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start with the idea",
        entry_state=["Learner is ready to learn"],
        must_establish=["Learner understands the idea"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["Learner can explain the idea"],
    )
    plan = TeachingPlan(
        arc="Teach a simple idea",
        contract_version=2,
        learner_title="A lesson about one idea",
        starting_state=["Learner is ready to learn"],
        target_state=["Learner can explain the idea"],
        teaching_plan_id="tp-approved-1",
        revision=3,
        sections=[section],
    )
    source = _approved_source(plan)
    calls = []

    async def fake_admit(_session, request):
        calls.append(("run", request))
        return SimpleNamespace(record=SimpleNamespace(id="run-1"), created=True)

    async def fake_add(_session, request):
        calls.append(("item", request))
        return SimpleNamespace(record=SimpleNamespace(item_key=request.item_key), created=True)

    monkeypatch.setattr("document.shared_lesson.runtime.admit_run", fake_admit)
    monkeypatch.setattr("document.shared_lesson.runtime.add_work_item", fake_add)
    run, items = await admit_section_run(
        "session",
        build_id="build-1",
        owner_user_id="teacher",
        request_key="request-1",
        source=source,
    )

    assert run.id == "run-1"
    assert [item.item_key for item in items] == ["compose:orient"]
    assert calls[0][0] == "run"
    assert calls[1][1].run_id == "run-1"


@pytest.mark.asyncio
async def test_writer_admission_returns_work_item_record(monkeypatch) -> None:
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start here",
        entry_state=["Learner recognizes the material"],
        must_establish=["Learner can identify the material"],
        avoid_repeating=["Do not repeat prior work"],
        bridge_from_previous=None,
        exit_state=["Learner identifies the material"],
        blocks=[
            TeachingPlanBlock(
                id="block-1",
                position=0,
                intent="identify the material",
                brief="name the material",
                evidence="Learner names the material",
            )
        ],
    )
    composition = SectionCompositionPlan(
        section_slot_id="orient",
        items=(
            CompositionItem(
                id="node-1",
                kind="paragraph",
                teaching_block_id="block-1",
                semantic_role="explanation",
            ),
        ),
    )
    request = SectionWriterRequest(section=section, composition_plan=composition)
    captured = []

    async def fake_add(_session, admission):
        captured.append(admission)
        return SimpleNamespace(record=SimpleNamespace(item_key=admission.item_key))

    monkeypatch.setattr("document.shared_lesson.runtime.add_work_item", fake_add)
    item = await admit_writer_work_item("session", run_id="run-1", section=section, request=request)

    assert item.item_key == "write:orient"
    assert captured[0].composition_identity


def test_source_identity_requires_exact_id_revision_and_recomputed_hash() -> None:
    source = _source()

    identity = verify_teaching_plan_source(source)
    assert identity.source_artifact_id == "tp-approved-1"
    assert identity.source_revision == 3
    assert identity.source_hash == source.content_hash

    with pytest.raises(SectionRuntimeError, match="source ID"):
        verify_teaching_plan_source(source.model_copy(update={"id": "foreign-plan"}))
    with pytest.raises(SectionRuntimeError, match="revision"):
        verify_teaching_plan_source(source.model_copy(update={"revision": 4}))
    with pytest.raises(SectionRuntimeError, match="content hash"):
        verify_teaching_plan_source(source.model_copy(update={"content_hash": "a" * 64}))

    for status in ("pending", "superseded", "rejected"):
        unapproved = source.model_copy(
            update={"revision_record": source.revision_record.model_copy(update={"status": status})}
        )
        with pytest.raises(SectionRuntimeError, match="must be approved"):
            verify_teaching_plan_source(unapproved)

    with pytest.raises(SectionRuntimeError, match="no content hash"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"content_hash": None}
                    )
                }
            )
        )

    with pytest.raises(SectionRuntimeError, match="content hash does not match"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"content_hash": "a" * 64}
                    )
                }
            )
        )

    forged_record_plan = source.revision_record.plan | {"arc": "Forged plan content"}
    with pytest.raises(SectionRuntimeError, match="content hash does not match"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"plan": forged_record_plan}
                    )
                }
            )
        )

    with pytest.raises(SectionRuntimeError, match="Record identity"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"teaching_plan_id": "another-plan"}
                    )
                }
            )
        )

    with pytest.raises(SectionRuntimeError, match="Record identity"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"revision": source.revision + 1}
                    )
                }
            )
        )

    forged_plan_identity = source.revision_record.plan | {"teaching_plan_id": "another-plan"}
    with pytest.raises(SectionRuntimeError, match="plan ID differs"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"plan": forged_plan_identity}
                    )
                }
            )
        )

    forged_plan_revision = source.revision_record.plan | {"revision": source.revision + 1}
    with pytest.raises(SectionRuntimeError, match="plan revision differs"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"plan": forged_plan_revision}
                    )
                }
            )
        )

    pending_record_plan = source.revision_record.plan | {"approval_status": "pending"}
    with pytest.raises(SectionRuntimeError, match="Record plan approval_status"):
        verify_teaching_plan_source(
            source.model_copy(
                update={
                    "revision_record": source.revision_record.model_copy(
                        update={"plan": pending_record_plan}
                    )
                }
            )
        )

    pending_plan = source.plan.model_copy(update={"approval_status": "pending"})
    with pytest.raises(SectionRuntimeError, match="approval_status"):
        verify_teaching_plan_source(source.model_copy(update={"plan": pending_plan}))


def test_source_admission_rejects_legacy_teaching_plan_contract() -> None:
    legacy = TeachingPlan(
        arc="Teach a simple idea",
        teaching_plan_id="tp-legacy-1",
        revision=1,
        sections=[TeachingPlanSection(slot_id="orient")],
    )
    source = _approved_source(legacy)

    with pytest.raises(SectionRuntimeError, match="contract version 2"):
        verify_teaching_plan_source(source)


@pytest.mark.asyncio
async def test_provider_validation_error_keeps_provider_output_classification(monkeypatch) -> None:
    from pydantic import TypeAdapter, ValidationError

    from infra.generation_runtime import ErrorClass

    with pytest.raises(ValidationError) as caught:
        TypeAdapter(int).validate_python("invalid")
    recorded = []

    async def fake_fail(_session, **kwargs):
        recorded.append(kwargs["failure"])

    monkeypatch.setattr("document.shared_lesson.runtime.fail_work_item", fake_fail)
    await _record_execution_failure(
        "session",
        work_item_id="item-1",
        worker_id="worker-1",
        lease_token=1,
        error=caught.value,
    )

    assert recorded[0].error_class == ErrorClass.PROVIDER_OUTPUT
    assert recorded[0].error_code == "invalid_section_output"


@pytest.mark.asyncio
async def test_writer_total_timeout_is_recorded_as_retryable_transport_failure(monkeypatch) -> None:
    from infra.generation_runtime import ErrorClass, RecoveryAction

    source = _source()
    composition_plan = SimpleNamespace(model_dump=lambda **_kwargs: {"items": []})
    request = SimpleNamespace(
        composition_plan=composition_plan,
        model_dump=lambda **_kwargs: {"composition_plan": {"items": []}},
    )
    recorded = []

    async def fake_claim(*_args, **_kwargs):
        return SimpleNamespace(lease_token=1)

    async def fake_no_checkpoint(*_args, **_kwargs):
        return None

    async def fake_fail(_session, **kwargs):
        recorded.append(kwargs["failure"])

    async def stalled_writer(**_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    monkeypatch.setattr(
        "document.shared_lesson.runtime.load_compatible_checkpoint", fake_no_checkpoint
    )
    monkeypatch.setattr("document.shared_lesson.runtime.persist_checkpoint", fake_no_checkpoint)
    monkeypatch.setattr("document.shared_lesson.runtime.fail_work_item", fake_fail)
    monkeypatch.setattr("document.shared_lesson.runtime.write_section", stalled_writer)
    monkeypatch.setattr("document.shared_lesson.runtime.SECTION_WRITER_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(TimeoutError):
        await _write_section_work_item(
            SimpleNamespace(commit=_commit_noop),
            work_item_id="write:orient",
            worker_id="worker-1",
            source=source,
            request=request,
            provider_semaphore=asyncio.Semaphore(1),
        )

    assert len(recorded) == 1
    assert recorded[0].error_class == ErrorClass.PROVIDER_TRANSPORT
    assert recorded[0].recovery_action == RecoveryAction.RETRY
    assert recorded[0].error_code == "provider_transport"


@pytest.mark.asyncio
async def test_writer_timeout_records_failure_without_awaiting_cancel_resistant_provider(
    monkeypatch,
) -> None:
    from infra.generation_runtime import ErrorClass, RecoveryAction

    source = _source()
    composition_plan = SimpleNamespace(model_dump=lambda **_kwargs: {"items": []})
    request = SimpleNamespace(
        composition_plan=composition_plan,
        model_dump=lambda **_kwargs: {"composition_plan": {"items": []}},
    )
    provider_started = asyncio.Event()
    provider_cancelled = asyncio.Event()
    release_provider = asyncio.Event()
    provider_finished = asyncio.Event()
    recorded = []

    async def fake_claim(*_args, **_kwargs):
        return SimpleNamespace(lease_token=1)

    async def fake_no_checkpoint(*_args, **_kwargs):
        return None

    async def fake_fail(_session, **kwargs):
        recorded.append(kwargs["failure"])

    async def cancel_resistant_provider(_payload):
        provider_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            provider_cancelled.set()
            await release_provider.wait()
        provider_finished.set()
        return {"nodes": []}

    async def writer_with_provider(*, provider, **_kwargs):
        return await provider({"repair_scope": "initial"})

    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    monkeypatch.setattr(
        "document.shared_lesson.runtime.load_compatible_checkpoint", fake_no_checkpoint
    )
    monkeypatch.setattr("document.shared_lesson.runtime.persist_checkpoint", fake_no_checkpoint)
    monkeypatch.setattr("document.shared_lesson.runtime.fail_work_item", fake_fail)
    monkeypatch.setattr("document.shared_lesson.runtime.write_section", writer_with_provider)
    monkeypatch.setattr("document.shared_lesson.runtime.SECTION_WRITER_TIMEOUT_SECONDS", 0.02)

    with pytest.raises(TimeoutError, match="aggregate deadline"):
        await asyncio.wait_for(
            _write_section_work_item(
                SimpleNamespace(commit=_commit_noop),
                work_item_id="write:orient",
                worker_id="worker-1",
                source=source,
                request=request,
                provider=cancel_resistant_provider,
                provider_semaphore=asyncio.Semaphore(1),
            ),
            timeout=0.5,
        )

    assert provider_started.is_set()
    assert len(recorded) == 1
    assert recorded[0].error_class == ErrorClass.PROVIDER_TRANSPORT
    assert recorded[0].recovery_action == RecoveryAction.RETRY
    assert recorded[0].error_code == "provider_transport"
    await asyncio.wait_for(provider_cancelled.wait(), timeout=0.1)
    assert provider_finished.is_set() is False

    release_provider.set()
    await asyncio.wait_for(provider_finished.wait(), timeout=0.2)


@pytest.mark.asyncio
async def test_detached_writer_retains_shared_provider_cap_across_batches(monkeypatch) -> None:
    source = _source()
    composition_plan = SimpleNamespace(model_dump=lambda **_kwargs: {"items": []})
    slow_request = SimpleNamespace(
        tag="slow",
        composition_plan=composition_plan,
        model_dump=lambda **_kwargs: {"section": "slow"},
    )
    fast_request = SimpleNamespace(
        tag="fast",
        composition_plan=composition_plan,
        model_dump=lambda **_kwargs: {"section": "fast"},
    )
    slow_cancelled = asyncio.Event()
    release_slow_provider = asyncio.Event()
    slow_provider_finished = asyncio.Event()
    fast_writer_started = asyncio.Event()
    fast_provider_started = asyncio.Event()
    failures = []
    lease_tokens = 0

    async def fake_claim(*_args, **_kwargs):
        nonlocal lease_tokens
        lease_tokens += 1
        return SimpleNamespace(lease_token=lease_tokens)

    async def fake_no_checkpoint(*_args, **_kwargs):
        return None

    async def fake_fail(_session, **kwargs):
        failures.append(kwargs["failure"])

    async def fake_complete(*_args, **_kwargs):
        return None

    async def fake_failed_item(*_args, **_kwargs):
        return SimpleNamespace(status="failed_recoverable")

    async def cancellation_resistant_provider(payload):
        if payload["tag"] == "fast":
            fast_provider_started.set()
            return {"nodes": []}
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            slow_cancelled.set()
            await release_slow_provider.wait()
        slow_provider_finished.set()
        return {"nodes": []}

    async def fake_write(*, request, provider):
        if request.tag == "fast":
            fast_writer_started.set()
        await provider({"tag": request.tag})
        return SimpleNamespace(model_dump=lambda **_kwargs: {"nodes": []})

    monkeypatch.setattr(
        "document.shared_lesson.runtime.MAX_CONCURRENT_SECTION_WRITERS", 1
    )
    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    monkeypatch.setattr(
        "document.shared_lesson.runtime.load_compatible_checkpoint", fake_no_checkpoint
    )
    monkeypatch.setattr("document.shared_lesson.runtime.persist_checkpoint", fake_no_checkpoint)
    monkeypatch.setattr("document.shared_lesson.runtime.fail_work_item", fake_fail)
    monkeypatch.setattr("document.shared_lesson.runtime.complete_work_item", fake_complete)
    monkeypatch.setattr("document.shared_lesson.runtime.write_section", fake_write)
    monkeypatch.setattr("document.shared_lesson.runtime.SECTION_WRITER_TIMEOUT_SECONDS", 0.02)

    def job(item_id, request):
        return SectionWriterJob(
            session=SimpleNamespace(commit=_commit_noop, get=fake_failed_item),
            work_item_id=item_id,
            worker_id=f"worker:{item_id}",
            source=source,
            request=request,
            status="queued",
            provider=cancellation_resistant_provider,
        )

    first = await write_section_work_items((job("write:slow", slow_request),))
    assert isinstance(first[0].error, TimeoutError)
    assert len(failures) == 1
    await asyncio.wait_for(slow_cancelled.wait(), timeout=0.1)

    monkeypatch.setattr("document.shared_lesson.runtime.SECTION_WRITER_TIMEOUT_SECONDS", 1)
    second_batch = asyncio.create_task(
        write_section_work_items((job("write:fast", fast_request),))
    )
    await asyncio.wait_for(fast_writer_started.wait(), timeout=0.1)
    await asyncio.sleep(0.02)
    assert fast_provider_started.is_set() is False
    assert second_batch.done() is False

    release_slow_provider.set()
    second = await asyncio.wait_for(second_batch, timeout=0.5)
    await asyncio.wait_for(slow_provider_finished.wait(), timeout=0.1)
    assert second[0].result is not None
    assert fast_provider_started.is_set()


@pytest.mark.asyncio
async def test_pending_source_is_rejected_before_work_item_claim(monkeypatch) -> None:
    source = _source()
    pending_plan = source.plan.model_copy(update={"approval_status": "pending"})
    pending_record = source.revision_record.model_copy(
        update={"status": "pending", "plan": pending_plan.model_dump(mode="json")}
    )
    pending_source = source.model_copy(
        update={"plan": pending_plan, "revision_record": pending_record}
    )
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start here",
        entry_state=["Learner is ready"],
        must_establish=["Learner understands the idea"],
        avoid_repeating=["Do not repeat prior content"],
        bridge_from_previous=None,
        exit_state=["Learner can explain the idea"],
        blocks=[
            TeachingPlanBlock(
                id="block-orient",
                position=0,
                intent="Explain the idea",
                brief="Explain the idea clearly.",
                evidence="Learner explains the idea.",
            )
        ],
    )
    composition = SectionCompositionPlan(
        section_slot_id="orient",
        items=(
            CompositionItem(
                id="node-orient",
                kind="paragraph",
                teaching_block_id="block-orient",
                semantic_role="explanation",
            ),
        ),
    )
    request = SectionWriterRequest(section=section, composition_plan=composition)
    claim_calls = []

    async def fake_claim(*args, **kwargs):
        claim_calls.append((args, kwargs))
        return SimpleNamespace(lease_token=1)

    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    with pytest.raises(SectionRuntimeError, match="approved"):
        await compose_section_work_item(
            "session",
            work_item_id="compose:orient",
            worker_id="worker-compose",
            source=pending_source,
            section=section,
            tasks=(),
        )
    with pytest.raises(SectionRuntimeError, match="approved"):
        await _write_section_work_item(
            "session",
            work_item_id="write:orient",
            worker_id="worker-1",
            source=pending_source,
            request=request,
            provider_semaphore=asyncio.Semaphore(1),
        )
    assert claim_calls == []


@pytest.mark.asyncio
async def test_public_writer_batch_enforces_four_and_skips_ready_sibling(monkeypatch) -> None:
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start here",
        entry_state=["Learner recognizes the material"],
        must_establish=["Learner can identify the material"],
        avoid_repeating=["Do not repeat prior work"],
        bridge_from_previous=None,
        exit_state=["Learner identifies the material"],
        blocks=[
            TeachingPlanBlock(
                id="block-1",
                position=0,
                intent="identify the material",
                brief="name the material",
                evidence="Learner names the material",
            )
        ],
    )
    plan = TeachingPlan(
        arc="Teach a simple idea",
        contract_version=2,
        learner_title="A simple lesson",
        starting_state=["Learner recognizes the material"],
        target_state=["Learner identifies the material"],
        teaching_plan_id="tp-approved-1",
        revision=3,
        sections=[section],
    )
    source = _approved_source(plan)
    composition = SectionCompositionPlan(
        section_slot_id="orient",
        items=(
            CompositionItem(
                id="node-1",
                kind="paragraph",
                teaching_block_id="block-1",
                semantic_role="explanation",
            ),
        ),
    )
    request = SectionWriterRequest(section=section, composition_plan=composition)
    active = 0
    peak = 0
    claim_count = 0

    async def fake_claim(*_args, **_kwargs):
        nonlocal claim_count
        claim_count += 1
        return SimpleNamespace(lease_token=claim_count)

    async def fake_no_checkpoint(*_args, **_kwargs):
        return None

    async def fake_write(*, request, provider):
        await provider({"draft": True})
        return SectionWriteResult(
            section_slot_id=request.section.slot_id,
            title="Start here",
            nodes=(
                ParagraphNode(
                    id="node-1",
                    teaching_block_id="block-1",
                    display=ParagraphDisplay(
                        text="A material can be identified by its properties."
                    ),
                ),
            ),
        )

    async def slow_provider(_payload):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1
        return {"nodes": []}

    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    monkeypatch.setattr(
        "document.shared_lesson.runtime.load_compatible_checkpoint", fake_no_checkpoint
    )
    monkeypatch.setattr("document.shared_lesson.runtime.persist_checkpoint", fake_no_checkpoint)
    monkeypatch.setattr("document.shared_lesson.runtime.complete_work_item", fake_no_checkpoint)
    monkeypatch.setattr("document.shared_lesson.runtime.write_section", fake_write)
    jobs = tuple(
        SectionWriterJob(
            session=SimpleNamespace(commit=_commit_noop),
            work_item_id=f"write:{index}",
            worker_id=f"worker:{index}",
            source=source,
            request=request,
            status="queued",
            provider=slow_provider,
        )
        for index in range(8)
    ) + (
        SectionWriterJob(
            session=object(),
            work_item_id="write:ready-sibling",
            worker_id="worker-ready",
            source=source,
            request=request,
            status="ready",
            provider=slow_provider,
        ),
    )

    outcomes = await write_section_work_items(jobs)

    assert len(outcomes) == 9
    assert all(outcome.result is not None for outcome in outcomes[:8])
    assert outcomes[-1].preserved_ready
    assert peak == MAX_CONCURRENT_SECTION_WRITERS
    assert claim_count == 8


@pytest.mark.asyncio
async def test_writer_job_commits_before_sibling_finishes(monkeypatch) -> None:
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

    async def write(session, *, work_item_id, **_kwargs):
        if work_item_id == "write:second":
            await first_locked.wait()
        await lock.acquire()
        session.owns_lock = True
        if work_item_id == "write:first":
            first_locked.set()
        return SimpleNamespace(section_slot_id=work_item_id)

    monkeypatch.setattr("document.shared_lesson.runtime._write_section_work_item", write)
    jobs = tuple(
        SectionWriterJob(
            session=LockingSession(item_id),
            work_item_id=f"write:{item_id}",
            worker_id="writer-lock-test",
            source=SimpleNamespace(),
            request=SimpleNamespace(),
            status="queued",
        )
        for item_id in ("first", "second")
    )

    outcomes = await asyncio.wait_for(write_section_work_items(jobs), timeout=1)

    assert all(outcome.result is not None for outcome in outcomes)
    assert set(commits) == {"first", "second"}


@pytest.mark.asyncio
async def test_writer_unrecorded_exception_rolls_back_and_propagates(monkeypatch) -> None:
    original = RuntimeError("unexpected failure before typed failure persistence")

    class Session:
        committed = False
        rolled_back = False

        async def get(self, _model, _work_item_id):
            return SimpleNamespace(status="running")

        async def commit(self):
            self.committed = True

        async def rollback(self):
            self.rolled_back = True

    async def fail_before_recording(*_args, **_kwargs):
        raise original

    monkeypatch.setattr(
        "document.shared_lesson.runtime._write_section_work_item", fail_before_recording
    )
    session = Session()
    job = SectionWriterJob(
        session=session,
        work_item_id="write:unexpected",
        worker_id="writer-failure-test",
        source=SimpleNamespace(),
        request=SimpleNamespace(),
        status="queued",
    )

    with pytest.raises(RuntimeError) as raised:
        await write_section_work_items((job,))

    assert raised.value is original
    assert session.rolled_back
    assert not session.committed


def test_writer_checkpoint_must_match_exact_composition_identity() -> None:
    composition = SectionCompositionPlan(
        section_slot_id="orient",
        items=(
            CompositionItem(
                id="node-1",
                kind="paragraph",
                teaching_block_id="block-1",
                semantic_role="explanation",
            ),
        ),
    )
    payload = {
        "composition_identity": "stale-composition-hash",
        "plan": composition.model_dump(mode="json"),
    }

    with pytest.raises(SectionRuntimeError, match="different composition"):
        verify_writer_checkpoint_payload(payload, composition=composition)


@pytest.mark.asyncio
async def test_targeted_retry_names_only_the_selected_failed_work_item(monkeypatch) -> None:
    calls = []

    async def fake_retry(session, *, work_item_id, owner_user_id):
        calls.append((session, work_item_id, owner_user_id))
        return "retried"

    monkeypatch.setattr("document.shared_lesson.runtime.retry_work_item", fake_retry)
    result = await retry_failed_section(
        "session", work_item_id="write:orient", owner_user_id="teacher"
    )

    assert result == "retried"
    assert calls == [("session", "write:orient", "teacher")]


@pytest.mark.asyncio
async def test_cancel_delegates_to_generic_run_cancellation(monkeypatch) -> None:
    calls = []

    async def fake_cancel(session, *, run_id, owner_user_id):
        calls.append((session, run_id, owner_user_id))
        return "cancelled"

    monkeypatch.setattr("document.shared_lesson.runtime.cancel_run", fake_cancel)
    result = await cancel_section_run("session", run_id="run-1", owner_user_id="teacher")

    assert result == "cancelled"
    assert calls == [("session", "run-1", "teacher")]


@pytest.mark.asyncio
async def test_restart_rejects_reuse_of_previous_run(monkeypatch) -> None:
    async def fake_admit(*_args, **_kwargs):
        return SimpleNamespace(id="old-run"), ()

    monkeypatch.setattr("document.shared_lesson.runtime.admit_section_run", fake_admit)
    with pytest.raises(SectionRuntimeError, match="fresh idempotency"):
        await restart_section_run(
            "session",
            previous_run_id="old-run",
            build_id="build-1",
            owner_user_id="teacher",
            request_key="reused-key",
            source=_source(),
        )


@pytest.mark.asyncio
async def test_late_provider_result_cannot_complete_after_lease_is_lost(monkeypatch) -> None:
    section = TeachingPlanSection(
        slot_id="orient",
        display_title="Start here",
        entry_state=["Learner recognizes the materials"],
        must_establish=["Learner identifies the material"],
        avoid_repeating=["Do not repeat prior work"],
        bridge_from_previous=None,
        exit_state=["Learner can identify the material"],
        blocks=[
            TeachingPlanBlock(
                id="block-1",
                position=0,
                intent="identify the material",
                brief="name the material",
                evidence="Learner names the material",
            )
        ],
    )
    plan = TeachingPlan(
        arc="Teach a simple idea",
        contract_version=2,
        learner_title="A simple lesson",
        starting_state=["Learner recognizes the materials"],
        target_state=["Learner can identify the material"],
        teaching_plan_id="tp-approved-1",
        revision=3,
        sections=[section],
    )
    source = _approved_source(plan)
    composition = SectionCompositionPlan(
        section_slot_id="orient",
        items=(
            CompositionItem(
                id="node-1",
                kind="paragraph",
                teaching_block_id="block-1",
                semantic_role="explanation",
            ),
        ),
    )
    request = SectionWriterRequest(section=section, composition_plan=composition)
    calls = []
    boundaries = []

    class FakeSession:
        async def commit(self):
            boundaries.append("commit")

    async def fake_claim(*_args, **_kwargs):
        return SimpleNamespace(lease_token=9)

    async def fake_load(*_args, **_kwargs):
        return None

    async def fake_persist(*_args, **_kwargs):
        return None

    async def fake_write(*, request, provider):
        boundaries.append("provider")
        await provider({"draft": True})
        return SectionWriteResult(
            section_slot_id=request.section.slot_id,
            title="Start here",
            nodes=(
                ParagraphNode(
                    id="node-1",
                    teaching_block_id="block-1",
                    display=ParagraphDisplay(
                        text="A material can be identified by its properties."
                    ),
                ),
            ),
        )

    async def late_fenced_complete(*_args, **_kwargs):
        calls.append("fenced")
        raise LeaseLostError("worker no longer holds a live lease")

    async def provider(_payload):
        return {"nodes": []}

    monkeypatch.setattr("document.shared_lesson.runtime.claim_work_item", fake_claim)
    monkeypatch.setattr("document.shared_lesson.runtime.load_compatible_checkpoint", fake_load)
    monkeypatch.setattr("document.shared_lesson.runtime.persist_checkpoint", fake_persist)
    monkeypatch.setattr("document.shared_lesson.runtime.write_section", fake_write)
    monkeypatch.setattr("document.shared_lesson.runtime.complete_work_item", late_fenced_complete)

    with pytest.raises(LeaseLostError, match="live lease"):
        await _write_section_work_item(
            FakeSession(),
            work_item_id="write:orient",
            worker_id="worker-1",
            source=source,
            request=request,
            provider=provider,
            provider_semaphore=asyncio.Semaphore(MAX_CONCURRENT_SECTION_WRITERS),
        )
    assert calls == ["fenced"]
    assert boundaries == ["commit", "provider"]


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_kind", ["composer", "writer"])
async def test_provider_observes_committed_claim_and_writer_checkpoint(
    db_session, db_session_factory, monkeypatch, worker_kind
):
    source = _db_source()
    owner_id, lesson_id = await _seed_db_build(db_session, suffix=f"provider-boundary-{worker_kind}")
    _build, (run, composition_items) = await _admit_db_run(
        db_session,
        owner_id=owner_id,
        lesson_id=lesson_id,
        source=source,
        request_key=f"provider-boundary-{worker_kind}-request",
    )
    section = source.plan.sections[0]
    request = _db_writer_request(section)
    composition = request.composition_plan
    if worker_kind == "composer":
        item = next(item for item in composition_items if item.item_key == "compose:orient")
    else:
        from document.shared_lesson.runtime import admit_writer_work_item

        item = await admit_writer_work_item(
            db_session,
            run_id=run.id,
            section=section,
            request=request,
        )
    await db_session.commit()
    observed = []

    async def provider(_payload):
        async with db_session_factory() as separate_session:
            persisted = await separate_session.get(GenerationWorkItemModel, item.id)
            assert persisted is not None
            assert persisted.status == "running"
            assert persisted.lease_owner == f"provider-{worker_kind}"
            if worker_kind == "writer":
                assert persisted.checkpoint_json is not None
                assert persisted.checkpoint_json["payload"]["plan"] == composition.model_dump(
                    mode="json"
                )
            else:
                assert persisted.checkpoint_json is None
        observed.append(True)
        return {"choices": []}

    if worker_kind == "composer":
        async def compose(*, provider, **_kwargs):
            await provider({"compose": True})
            return composition

        monkeypatch.setattr("document.shared_lesson.runtime.compose_section", compose)
        await compose_section_work_item(
            db_session,
            work_item_id=item.id,
            worker_id="provider-composer",
            source=source,
            section=section,
            tasks=(),
            provider=provider,
        )
    else:
        async def write(*, request, provider):
            await provider({"write": True})
            return SectionWriteResult(
                section_slot_id=request.section.slot_id,
                title="Start here",
                nodes=(
                    ParagraphNode(
                        id="node-1",
                        teaching_block_id=request.section.blocks[0].id,
                        display=ParagraphDisplay(text="A complete section."),
                    ),
                ),
            )

        monkeypatch.setattr("document.shared_lesson.runtime.write_section", write)
        await _write_section_work_item(
            db_session,
            work_item_id=item.id,
            worker_id="provider-writer",
            source=source,
            request=request,
            provider=provider,
            provider_semaphore=asyncio.Semaphore(1),
        )
    assert observed == [True]
    await db_session.commit()
    async with db_session_factory() as separate_session:
        persisted = await separate_session.get(GenerationWorkItemModel, item.id)
        assert persisted is not None
        assert persisted.status == "ready"
        assert persisted.checkpoint_json is not None

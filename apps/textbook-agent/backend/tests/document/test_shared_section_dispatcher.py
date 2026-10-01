from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from test_shared_composer_admission import _seed_run, _verifier
from test_shared_writer_admission import _seed_ready_composer_run

from document.shared_lesson import section_dispatcher
from document.shared_lesson.composer import CompositionChoice, validate_and_build_composition
from document.shared_lesson.runtime import SectionWriterOutcome
from document.shared_lesson.writer_admission import admit_writer_work_items
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import WorkItemUnavailable


def _dispatcher(db_session_factory) -> section_dispatcher.SharedSectionDispatcher:
    return section_dispatcher.SharedSectionDispatcher(
        db_session_factory,
        worker_id="section-dispatcher-test",
    )


@pytest.mark.asyncio
async def test_run_one_uses_same_run_and_dispatches_composer_then_writers(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source, _sourcebook = await _seed_run(db_session)
    composer_calls: list[str] = []
    writer_calls: list[str] = []

    async def compose(session, *, work_item_id, section, **_kwargs):
        composer_calls.append(work_item_id)
        composition = validate_and_build_composition(
            section=section,
            choices=(
                CompositionChoice(
                    teaching_block_id=section.blocks[0].id,
                    kind="paragraph",
                    semantic_role="explanation",
                ),
            ),
            tasks=(),
        )
        item = await session.get(GenerationWorkItemModel, work_item_id)
        payload = composition.model_dump(mode="json")
        item.status = "ready"
        item.output_json = payload
        item.output_hash = content_hash(payload)
        return composition

    async def write(jobs):
        assert len({id(job.session) for job in jobs}) == len(jobs)
        outcomes = []
        for job in jobs:
            writer_calls.append(job.work_item_id)
            item = await job.session.get(GenerationWorkItemModel, job.work_item_id)
            item.status = "ready"
            item.output_json = {"section_slot_id": job.request.section.slot_id}
            item.output_hash = content_hash(item.output_json)
            outcomes.append(SectionWriterOutcome(work_item_id=job.work_item_id, result=object()))
        return tuple(outcomes)

    monkeypatch.setattr(section_dispatcher, "compose_section_work_item", compose)
    monkeypatch.setattr(section_dispatcher, "write_section_work_items", write)
    dispatcher = _dispatcher(db_session_factory)

    result = await dispatcher.run_one(
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
        session=db_session,
    )

    assert result.run_id == run_id
    assert result.composer_dispatched == 2
    assert result.writer_dispatched == 2
    assert len(composer_calls) == len(writer_calls) == 2
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(GenerationRunModel)
            .where(GenerationRunModel.id == run_id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_missing_composer_output_blocks_writer_admission(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source, _sourcebook = await _seed_run(db_session)
    writer_called = False

    async def compose_without_output(*_args, **_kwargs):
        return None

    async def writer_admission(*_args, **_kwargs):
        nonlocal writer_called
        writer_called = True
        raise AssertionError("writers must not be admitted before every composer is ready")

    monkeypatch.setattr(section_dispatcher, "compose_section_work_item", compose_without_output)
    monkeypatch.setattr(section_dispatcher, "admit_writer_work_items", writer_admission)
    dispatcher = _dispatcher(db_session_factory)

    result = await dispatcher.run_one(
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
        session=db_session,
    )

    assert result.blocked is True
    assert writer_called is False


@pytest.mark.asyncio
async def test_composer_failure_is_persisted_and_ready_sibling_is_preserved(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source, _sourcebook = await _seed_run(db_session)

    async def compose_with_one_failure(session, *, work_item_id, section, **_kwargs):
        item = await session.get(GenerationWorkItemModel, work_item_id)
        if section.slot_id == "orient":
            item.status = "failed_recoverable"
            item.error_code = "provider_output"
            item.error_class = "provider_output"
            item.error_summary = "deliberate provider failure"
            item.recovery_action = "retry"
            raise RuntimeError("deliberate provider failure")
        composition = validate_and_build_composition(
            section=section,
            choices=(
                CompositionChoice(
                    teaching_block_id=section.blocks[0].id,
                    kind="paragraph",
                    semantic_role="explanation",
                ),
            ),
            tasks=(),
        )
        payload = composition.model_dump(mode="json")
        item.status = "ready"
        item.output_json = payload
        item.output_hash = content_hash(payload)
        return composition

    monkeypatch.setattr(section_dispatcher, "compose_section_work_item", compose_with_one_failure)
    dispatcher = _dispatcher(db_session_factory)

    result = await dispatcher.run_one(
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
        session=db_session,
    )
    assert result.blocked is True
    orient = await db_session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.item_key == "compose:orient",
        )
    )
    explain = await db_session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.item_key == "compose:explain",
        )
    )
    assert orient is not None and orient.status == "failed_recoverable"
    assert explain is not None and explain.status == "ready"


@pytest.mark.asyncio
async def test_stale_composer_claim_rolls_back_without_terminalizing_the_item(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source, _sourcebook = await _seed_run(db_session)

    async def stale_claim(*_args, **_kwargs):
        raise WorkItemUnavailable("stale composer claim")

    monkeypatch.setattr(section_dispatcher, "compose_section_work_item", stale_claim)
    dispatcher = _dispatcher(db_session_factory)

    result = await dispatcher.run_one(
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
        session=db_session,
    )
    assert result.blocked is True
    rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.item_key.like("compose:%"),
                )
            )
        ).all()
    )
    assert rows
    assert all(row.status == "queued" for row in rows)


@pytest.mark.asyncio
async def test_duplicate_dispatch_preserves_ready_siblings_without_new_work(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    writer_admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    for admission in writer_admissions:
        item = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert item is not None
        item.status = "ready"
        item.output_json = {"ready": admission.section.slot_id}
        item.output_hash = content_hash(item.output_json)
    await db_session.commit()

    calls = 0

    async def write(_jobs):
        nonlocal calls
        calls += 1
        return ()

    monkeypatch.setattr(section_dispatcher, "write_section_work_items", write)
    monkeypatch.setattr(section_dispatcher, "admit_composer_work_items", lambda *_a, **_k: _noop())
    monkeypatch.setattr(
        section_dispatcher, "admit_writer_work_items", lambda *_a, **_k: _ready(writer_admissions)
    )
    dispatcher = _dispatcher(db_session_factory)

    async def ready_run(_session, **_kwargs):
        return await db_session.get(GenerationRunModel, run_id)

    monkeypatch.setattr(section_dispatcher, "get_run_status", ready_run)
    current = datetime.now(UTC).replace(tzinfo=None)
    first = await dispatcher._dispatch_writers(writer_admissions, source=source, now=current)
    second = await dispatcher._dispatch_writers(writer_admissions, source=source, now=current)
    assert first[1] == second[1] == 2
    assert calls == 0


async def _noop():
    return ()


async def _ready(value):
    return value


@pytest.mark.asyncio
async def test_writer_batch_keeps_four_call_cap_and_isolates_sibling_failure(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    writer_admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    await db_session.commit()
    active = 0
    peak = 0

    async def write(jobs):
        nonlocal active, peak

        async def one(job):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            if job.work_item_id == jobs[0].work_item_id:
                return SectionWriterOutcome(
                    work_item_id=job.work_item_id,
                    error=RuntimeError("one sibling failed"),
                )
            return SectionWriterOutcome(work_item_id=job.work_item_id, result=object())

        return tuple(await asyncio.gather(*(one(job) for job in jobs)))

    monkeypatch.setattr(section_dispatcher, "write_section_work_items", write)
    dispatcher = _dispatcher(db_session_factory)
    dispatched, preserved = await dispatcher._dispatch_writers(
        writer_admissions,
        source=source,
        now=datetime.now(UTC).replace(tzinfo=None),
    )
    assert peak <= 4
    assert dispatched == 1
    assert preserved == 0

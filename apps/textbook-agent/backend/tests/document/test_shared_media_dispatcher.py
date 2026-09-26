from __future__ import annotations

from types import SimpleNamespace

import pytest
from test_shared_lesson_media import _section, _source

from document.shared_lesson import media_dispatcher
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.models import ParagraphNode
from document.shared_lesson.work_item_inputs import SharedLessonInputError


def _accepted(*, figures: bool = True):
    sections = (
        _section("section-a", 0) if figures else _paragraph_section("section-a", 0),
        _section("section-b", 1) if figures else _paragraph_section("section-b", 1),
    )
    compositions = tuple(
        SectionCompositionPlan(
            section_slot_id=section.id,
            items=(
                CompositionItem(
                    id=("figure-a" if section.id == "section-a" else "figure-b")
                    if figures
                    else f"paragraph-{section.id}",
                    kind="figure" if figures else "paragraph",
                    teaching_block_id=("block-a" if section.id == "section-a" else "block-b"),
                    semantic_role="visual_model" if figures else "explanation",
                ),
            ),
        )
        for section in sections
    )
    return SimpleNamespace(sections=sections, compositions=compositions)


def _paragraph_section(section_id: str, position: int):
    return type(_section(section_id, position))(
        id=section_id,
        title="The energy source" if section_id == "section-a" else "The process",
        position=position,
        nodes=(
            ParagraphNode(
                id=f"paragraph-{section_id}",
                teaching_block_id="block-a" if section_id == "section-a" else "block-b",
                display={"text": "The approved explanation."},
            ),
        ),
    )


def _semantic(source):
    return SimpleNamespace(
        source=source,
        tasks=(),
        sourcebook=SimpleNamespace(
            entries=(SimpleNamespace(id="fact-leaf", content={"text": "Approved fact."}),)
        ),
    )


def _bind(monkeypatch, *, accepted, source, readiness=None):
    async def semantic(*_args, **_kwargs):
        return _semantic(source)

    async def accepted_loader(*_args, **_kwargs):
        return accepted

    async def verifier(_session, requested):
        return requested

    monkeypatch.setattr(media_dispatcher, "load_verified_semantic_inputs", semantic)
    monkeypatch.setattr(media_dispatcher, "load_verified_shared_lesson_inputs", accepted_loader)
    monkeypatch.setattr(media_dispatcher, "build_section_sources", lambda *_args: ())
    monkeypatch.setattr(media_dispatcher, "project_media_readiness", lambda *_a, **_k: readiness)
    return verifier


@pytest.mark.asyncio
async def test_zero_figure_lesson_returns_ready_projection(
    db_session, db_session_factory, monkeypatch
):
    source = _source()
    accepted = _accepted(figures=False)
    readiness = media_dispatcher.MediaReadiness(ready=True, required_count=0, ready_count=0)
    verifier = _bind(monkeypatch, accepted=accepted, source=source, readiness=readiness)
    admissions = []
    monkeypatch.setattr(
        media_dispatcher,
        "admit_figure_media_work_item",
        lambda *_a, **_k: admissions.append(True),
    )
    dispatcher = media_dispatcher.SharedMediaDispatcher(
        db_session_factory,
        worker_id="media-zero",
        executor=SimpleNamespace(),
    )
    result = await dispatcher.run_one(
        session=db_session,
        run_id="media-run",
        owner_user_id="media-owner",
        source=source,
        source_verifier=verifier,
    )
    assert result.readiness.ready is True
    assert result.readiness.required_count == 0
    assert admissions == []


@pytest.mark.asyncio
async def test_missing_writer_inputs_blocks_before_media_admission(
    db_session, db_session_factory, monkeypatch
):
    source = _source()
    verifier = _bind(monkeypatch, accepted=_accepted(), source=source)

    async def stale(*_args, **_kwargs):
        raise SharedLessonInputError("writer output is stale")

    monkeypatch.setattr(media_dispatcher, "load_verified_shared_lesson_inputs", stale)
    called = []
    monkeypatch.setattr(
        media_dispatcher, "admit_figure_media_work_item", lambda *_a, **_k: called.append(True)
    )
    dispatcher = media_dispatcher.SharedMediaDispatcher(
        db_session_factory,
        worker_id="media-stale",
        executor=SimpleNamespace(),
    )
    with pytest.raises(SharedLessonInputError):
        await dispatcher.run_one(
            session=db_session,
            run_id="media-run",
            owner_user_id="media-owner",
            source=source,
            source_verifier=verifier,
        )
    assert called == []


@pytest.mark.asyncio
async def test_required_failure_preserves_healthy_figure_sibling(
    db_session, db_session_factory, monkeypatch
):
    source = _source()
    accepted = _accepted()
    readiness = media_dispatcher.MediaReadiness(
        ready=False,
        required_count=2,
        ready_count=1,
        failed_required_work_item_ids=("media-a",),
    )
    verifier = _bind(monkeypatch, accepted=accepted, source=source, readiness=readiness)
    records = []

    async def admit(*_args, **kwargs):
        record = SimpleNamespace(
            id=f"media-{kwargs['work'].figure_node_id}",
            status="queued",
            lease_expires_at=None,
        )
        records.append(record.id)
        return SimpleNamespace(record=record)

    async def execute(jobs, **_kwargs):
        return tuple(
            media_dispatcher.MediaRuntimeOutcome(
                work_item_id=job.work_item_id,
                error_code="media_executor_failure" if job.work_item_id.endswith("a") else None,
                error_summary="failed" if job.work_item_id.endswith("a") else None,
                preserved_ready=job.work_item_id.endswith("b"),
            )
            for job in jobs
        )

    monkeypatch.setattr(media_dispatcher, "admit_figure_media_work_item", admit)
    monkeypatch.setattr(media_dispatcher, "execute_figure_media_work_items", execute)
    dispatcher = media_dispatcher.SharedMediaDispatcher(
        db_session_factory,
        worker_id="media-failure",
        executor=SimpleNamespace(),
    )
    result = await dispatcher.run_one(
        session=db_session,
        run_id="media-run",
        owner_user_id="media-owner",
        source=source,
        source_verifier=verifier,
    )
    assert records == ["media-figure-a", "media-figure-b"]
    assert result.readiness.ready is False
    assert result.readiness.failed_required_work_item_ids == ("media-a",)


@pytest.mark.asyncio
async def test_duplicate_admission_reuses_frozen_figure_identity(
    db_session, db_session_factory, monkeypatch
):
    source = _source()
    accepted = _accepted()
    readiness = media_dispatcher.MediaReadiness(ready=False, required_count=2, ready_count=0)
    verifier = _bind(monkeypatch, accepted=accepted, source=source, readiness=readiness)
    calls = []

    async def admit(*_args, **kwargs):
        identity = kwargs["work"].work_order.work_order_id
        calls.append(identity)
        return SimpleNamespace(
            record=SimpleNamespace(id=f"id-{identity}", status="queued", lease_expires_at=None)
        )

    async def execute(jobs, **_kwargs):
        return tuple(
            media_dispatcher.MediaRuntimeOutcome(work_item_id=job.work_item_id) for job in jobs
        )

    monkeypatch.setattr(media_dispatcher, "admit_figure_media_work_item", admit)
    monkeypatch.setattr(media_dispatcher, "execute_figure_media_work_items", execute)
    dispatcher = media_dispatcher.SharedMediaDispatcher(
        db_session_factory,
        worker_id="media-duplicate",
        executor=SimpleNamespace(),
    )
    await dispatcher.run_one(
        session=db_session,
        run_id="media-run",
        owner_user_id="media-owner",
        source=source,
        source_verifier=verifier,
    )
    first = tuple(calls)
    await dispatcher.run_one(
        session=db_session,
        run_id="media-run",
        owner_user_id="media-owner",
        source=source,
        source_verifier=verifier,
    )
    assert tuple(calls) == first + first

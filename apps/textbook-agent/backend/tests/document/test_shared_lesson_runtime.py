from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode
from document.shared_lesson.runtime import (
    MAX_CONCURRENT_SECTION_WRITERS,
    SectionRuntimeError,
    TeachingPlanSource,
    admit_section_run,
    admit_writer_work_item,
    bounded_section_provider,
    cancel_section_run,
    make_writer_provider_semaphore,
    restart_section_run,
    retry_failed_section,
    verify_teaching_plan_source,
    verify_writer_checkpoint_payload,
    write_section_work_item,
)
from document.shared_lesson.writer import SectionWriteResult, SectionWriterRequest
from infra.generation_runtime import LeaseLostError


def _source() -> TeachingPlanSource:
    plan = TeachingPlan(
        arc="Teach a simple idea",
        teaching_plan_id="tp-approved-1",
        revision=3,
        sections=[],
    )
    return TeachingPlanSource(
        plan=plan,
        id="tp-approved-1",
        revision=3,
        content_hash=teaching_plan_content_hash(plan),
    )


@pytest.mark.asyncio
async def test_admission_uses_generic_repository_records(monkeypatch) -> None:
    section = TeachingPlanSection(slot_id="orient")
    plan = TeachingPlan(
        arc="Teach a simple idea",
        teaching_plan_id="tp-approved-1",
        revision=3,
        sections=[section],
    )
    source = TeachingPlanSource(
        plan=plan,
        id="tp-approved-1",
        revision=3,
        content_hash=teaching_plan_content_hash(plan),
    )
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
    item = await admit_writer_work_item(
        "session", run_id="run-1", section=section, request=request
    )

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


@pytest.mark.asyncio
async def test_provider_dispatches_are_capped_at_four_across_sections() -> None:
    active = 0
    peak = 0

    async def fake_provider(_payload: dict[str, object]) -> dict[str, object]:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1
        return {"ok": True}

    provider = bounded_section_provider(fake_provider, make_writer_provider_semaphore())
    await asyncio.gather(*(provider({"section": index}) for index in range(12)))

    assert MAX_CONCURRENT_SECTION_WRITERS == 4
    assert peak == MAX_CONCURRENT_SECTION_WRITERS


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
    result = await retry_failed_section("session", work_item_id="write:orient", owner_user_id="teacher")

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
    source = TeachingPlanSource(
        plan=plan,
        id="tp-approved-1",
        revision=3,
        content_hash=teaching_plan_content_hash(plan),
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
    calls = []

    async def fake_claim(*_args, **_kwargs):
        return SimpleNamespace(lease_token=9)

    async def fake_load(*_args, **_kwargs):
        return None

    async def fake_persist(*_args, **_kwargs):
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
                    display=ParagraphDisplay(text="A material can be identified by its properties."),
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
        await write_section_work_item(
            "session",
            work_item_id="write:orient",
            worker_id="worker-1",
            source=source,
            request=request,
            provider=provider,
            provider_semaphore=make_writer_provider_semaphore(),
        )
    assert calls == ["fenced"]

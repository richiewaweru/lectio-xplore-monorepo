"""Phase 8: the staged teaching planner as preparation work items.

``teaching_spine`` -> ``teaching_section:{slot}`` x N -> ``teaching_plan`` on the
PreparationWorker, the progress fields, and the draft endpoint. Stage runners and
the planner's model calls are always fakes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson import staged_teaching_planner as stp
from application.unit_lesson.preparation_runs import load_teaching_draft
from core.entities.user import User
from curriculum.models import PreparationProgressDTO
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from infra.config import settings
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from print.generation.whole_lesson.repository import PageDocumentRepository
from tests.application.test_3a_preparation_runs import (
    _admit,
    _Calls,
    _drain,
    _run,
    _seed,
    _teaching_plan,
    _tick,
    _worker,
    _workspace,
)
from tests.planning.test_staged_assembly import SLOTS, Harness, _snapshot
from tests.planning.test_staged_sections import _good
from tests.planning.test_staged_spine import _packet


class StagedCalls:
    """Fake staged stage runners backed by the planner with fake model calls."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.finished_hash: str | None = None

    async def spine(self, session, generation_id, *, require_items=True, **_):  # noqa: ANN001
        self.events.append("spine")
        result = await stp.run_spine_stage(
            _packet(), _snapshot(), trace_id="t", generation_id=generation_id
        )
        return stp.spine_result_to_json(result)

    async def section(self, session, generation_id, *, spine_json, slot_id, **_):  # noqa: ANN001
        self.events.append(f"section:{slot_id}")
        spine = stp.spine_result_from_json(spine_json).spine
        result = await stp.run_section_stage(
            spine, slot_id, _packet(), _snapshot(), trace_id="t", generation_id=generation_id
        )
        return stp.section_result_to_json(result)

    async def finish(self, session, generation_id, *, spine_json, section_jsons, **_):  # noqa: ANN001
        self.events.append("finish")
        assert set(section_jsons) == set(SLOTS)
        sections = {k: stp.section_result_from_json(v) for k, v in section_jsons.items()}
        result = await stp.finish_staged_plan(
            _packet(),
            _snapshot(),
            stp.spine_result_from_json(spine_json),
            sections,
            trace_id="t",
            generation_id=generation_id,
        )
        self.finished_hash = teaching_plan_content_hash(result.plan)
        plan = _teaching_plan()
        await PageDocumentRepository(session, generation_id).save_teaching_plan(
            plan=plan, validation={}, qc=[]
        )
        return {"teaching_plan": plan}

    def runners(self) -> dict[str, Any]:
        return {"spine": self.spine, "section": self.section, "finish": self.finish}


@pytest.fixture
def staged_mode(monkeypatch):
    monkeypatch.setattr(settings, "teaching_planner_mode", "staged")
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")


async def _keys(factory) -> dict[str, GenerationWorkItemModel]:
    async with factory() as session:
        rows = (await session.scalars(select(GenerationWorkItemModel))).all()
        session.expunge_all()
        return {r.item_key: r for r in rows}


async def test_staged_worker_admits_spine_then_sections_then_plan_and_finalizes(
    db_session: AsyncSession, db_session_factory, staged_mode, monkeypatch
) -> None:
    Harness(monkeypatch)
    user_id = "p8-flow"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    staged = StagedCalls()
    worker = _worker(db_session_factory, _Calls(), staged_runners=staged.runners())

    # backbone, then the single card.
    assert await _tick(worker, db_session_factory)
    assert await _tick(worker, db_session_factory)
    keys = await _keys(db_session_factory)
    assert "teaching_spine" in keys and "teaching_plan" not in keys
    assert not any(k.startswith("teaching_section:") for k in keys)
    progress = (await _workspace(db_session_factory, prep_id)).progress
    assert (progress.teaching_spine, progress.teaching_sections_total) == ("queued", 0)
    async with db_session_factory() as session:
        assert (await load_teaching_draft(session, generation_id=prep_id))["status"] == "none"

    assert await _tick(worker, db_session_factory)  # spine
    assert staged.events == ["spine"]
    keys = await _keys(db_session_factory)
    assert {k for k in keys if k.startswith("teaching_section:")} == {
        f"teaching_section:{s}" for s in SLOTS
    }
    assert "teaching_plan" not in keys
    progress = (await _workspace(db_session_factory, prep_id)).progress
    assert (
        progress.teaching_spine,
        progress.teaching_sections_total,
        progress.teaching_sections_ready,
        progress.teaching_plan,
    ) == ("ready", 3, 0, "not_started")
    async with db_session_factory() as session:
        draft = await load_teaching_draft(session, generation_id=prep_id)
    assert draft["status"] == "draft" and draft["total_sections"] == 3
    assert [s["slot_id"] for s in draft["spine"]["sections"]] == SLOTS
    assert draft["spine"]["learner_title"] and draft["spine"]["arc"]
    assert draft["sections"] == {} and draft["ready_sections"] == []
    assert (await _workspace(db_session_factory, prep_id)).state == "planning"

    assert await _tick(worker, db_session_factory)  # first section
    progress = (await _workspace(db_session_factory, prep_id)).progress
    assert progress.teaching_sections_ready == 1
    async with db_session_factory() as session:
        draft = await load_teaching_draft(session, generation_id=prep_id)
    assert len(draft["ready_sections"]) == 1
    ready = draft["ready_sections"][0]
    block = draft["sections"][ready]["blocks"][0]
    assert set(block) == {"intent", "brief", "task_mode", "has_visual"}
    assert draft["sections"][ready]["unresolved"] is False

    assert await _tick(worker, db_session_factory)
    assert "teaching_plan" not in await _keys(db_session_factory)
    assert await _tick(worker, db_session_factory)  # last section admits teaching_plan
    keys = await _keys(db_session_factory)
    assert keys["teaching_plan"].status == "queued"
    assert (await _workspace(db_session_factory, prep_id)).progress.teaching_sections_ready == 3

    await _drain(worker, db_session_factory)
    assert staged.events[0] == "spine" and staged.events[-1] == "finish"
    assert sorted(staged.events[1:-1]) == sorted(f"section:{s}" for s in SLOTS)
    assert staged.finished_hash  # assembled + reviewed from the stored outputs
    run = await _run(db_session_factory, prep_id)
    assert run.status == "ready" and run.output_artifact_type == "teaching_plan_revision"
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "awaiting_review"
    assert workspace.progress.teaching_plan == "ready"


async def _events(factory, generation_id: str) -> list[dict[str, Any]]:
    async with factory() as session:
        state = await PageDocumentRepository(session, generation_id).load_page_generation_state()
    return list(state.get("events") or [])


async def test_staged_plan_definition_and_inputs_differ_from_single(
    db_session: AsyncSession, db_session_factory, monkeypatch
) -> None:
    """The mode is baked into the teaching_plan hashes."""
    monkeypatch.setattr(settings, "teaching_planner_mode", "single")
    single_def = content_hash({"definition": "preparation-teaching-plan", "version": "preparation-v2"})
    user_id = "p8-single"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)
    keys = await _keys(db_session_factory)
    assert set(keys) == {"backbone", f"items:{user_id}-c1", "teaching_plan"}
    assert keys["teaching_plan"].definition_hash == single_def
    progress = (await _workspace(db_session_factory, prep_id)).progress
    assert (progress.teaching_spine, progress.teaching_sections_total) == ("not_started", 0)
    async with db_session_factory() as session:
        assert (await load_teaching_draft(session, generation_id=prep_id))["status"] == "none"

    monkeypatch.setattr(settings, "teaching_planner_mode", "staged")
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")
    Harness(monkeypatch)
    user2 = "p8-staged-hash"
    _lesson2, prep2 = await _seed(db_session, user_id=user2)
    await _admit(db_session, prep2, user2)
    staged = StagedCalls()
    worker2 = _worker(db_session_factory, _Calls(), worker_id="w2", staged_runners=staged.runners())
    await _drain(worker2, db_session_factory)
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.item_key == "teaching_plan",
                GenerationWorkItemModel.definition_hash != single_def,
            )
        )
    assert item is not None and item.status == "ready"


async def test_run_stays_staged_when_setting_flips_after_the_spine(
    db_session: AsyncSession, db_session_factory, staged_mode, monkeypatch
) -> None:
    Harness(monkeypatch)
    user_id = "p8-sticky"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    staged = StagedCalls()
    worker = _worker(db_session_factory, _Calls(), staged_runners=staged.runners())
    for _ in range(3):  # backbone, card, spine
        await _tick(worker, db_session_factory)
    assert staged.events == ["spine"]
    monkeypatch.setattr(settings, "teaching_planner_mode", "single")
    await _drain(worker, db_session_factory)
    assert staged.events[-1] == "finish"
    assert (await _run(db_session_factory, prep_id)).status == "ready"


async def test_stage_json_round_trip_and_finish_matches_in_process(monkeypatch) -> None:
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")
    Harness(monkeypatch)
    packet, snapshot = _packet(), _snapshot()
    spine_result = await stp.run_spine_stage(packet, snapshot, trace_id="t", generation_id="g")
    restored = stp.spine_result_from_json(stp.spine_result_to_json(spine_result))
    assert restored.spine == spine_result.spine and restored.draft == spine_result.draft
    assert [a.raw_response for a in restored.attempts] == [
        a.raw_response for a in spine_result.attempts
    ]
    sections = {}
    for slot in SLOTS:
        result = await stp.run_section_stage(
            spine_result.spine, slot, packet, snapshot, trace_id="t", generation_id="g"
        )
        again = stp.section_result_from_json(stp.section_result_to_json(result))
        assert again.blocks == result.blocks and again.flags == result.flags
        assert again.draft == result.draft and again.unresolved is result.unresolved
        sections[slot] = again
    staged_result = await stp.finish_staged_plan(
        packet, snapshot, restored, sections, trace_id="t", generation_id="g"
    )
    in_process = await stp.run_staged_teaching_planner(
        packet, legality=snapshot, trace_id="t", generation_id="g"
    )
    assert teaching_plan_content_hash(staged_result.plan) == teaching_plan_content_hash(
        in_process.plan
    )


def test_progress_dto_defaults_keep_single_mode_shape() -> None:
    dto = PreparationProgressDTO()
    assert dto.teaching_spine == "not_started"
    assert (dto.teaching_sections_total, dto.teaching_sections_ready) == (0, 0)


async def test_draft_endpoint_reads_ready_items_for_the_owner(
    db_session: AsyncSession, db_session_factory, staged_mode, monkeypatch
) -> None:
    import application.unit_lesson.native_http as native_http

    Harness(monkeypatch)
    user_id = "p8-http"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    monkeypatch.setattr(native_http, "async_session_factory", db_session_factory)
    monkeypatch.setattr(native_http, "_load_owned_generation", AsyncMock(return_value=None))
    user = User(
        id=user_id,
        email="p8@example.invalid",
        name="P8",
        created_at="2026-09-22T00:00:00Z",
        updated_at="2026-09-22T00:00:00Z",
    )
    assert (await native_http.get_lesson_approach_draft(prep_id, user))["status"] == "none"

    staged = StagedCalls()
    worker = _worker(db_session_factory, _Calls(), staged_runners=staged.runners())
    for _ in range(3):
        await _tick(worker, db_session_factory)
    body = await native_http.get_lesson_approach_draft(prep_id, user)
    assert body["status"] == "draft" and body["sections"] == {}
    assert body["total_sections"] == 3 and body["ready_sections"] == []
    await _tick(worker, db_session_factory)
    body = await native_http.get_lesson_approach_draft(prep_id, user)
    assert len(body["ready_sections"]) == 1
    assert set(body["sections"]) == set(body["ready_sections"])


async def test_default_staged_runners_persist_events_and_the_draft_revision(
    db_session: AsyncSession, db_session_factory, staged_mode, monkeypatch
) -> None:
    """Real service stages (only the model calls and packet build are fakes)."""
    from application.unit_lesson import teaching_plan_service as service

    Harness(monkeypatch)

    async def fake_prepare(session, generation_id, *, require_items=True, worker_id=None,
                           lease_token=None):  # noqa: ANN001
        repo = PageDocumentRepository(session, generation_id)
        await repo.append_event({"event": "teaching_plan_started"})
        packet, legality = _packet(), _snapshot()
        await repo.save_lesson_packet(packet.model_dump(mode="json"))
        await repo.save_lesson_legality(legality.model_dump(mode="json"))
        return packet, legality

    monkeypatch.setattr(service, "prepare_teaching_inputs", fake_prepare)
    user_id = "p8-real"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    worker = _worker(db_session_factory, _Calls())  # default staged runners
    await _drain(worker, db_session_factory, max_ticks=24)

    run = await _run(db_session_factory, prep_id)
    assert run.status == "ready" and run.output_artifact_type == "teaching_plan_revision"
    names = [e.get("event") or e.get("type") for e in await _events(db_session_factory, prep_id)]
    assert names.count("teaching_spine_ready") == 1
    assert names.count("teaching_section_ready") == 3
    assert names.index("teaching_spine_ready") < names.index("teaching_section_ready")
    assert names.index("teaching_plan_ready") > max(
        i for i, n in enumerate(names) if n == "teaching_section_ready"
    )
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "awaiting_review" and workspace.progress.teaching_plan == "ready"


async def test_stage_path_respects_review_settings_and_empty_sections(monkeypatch) -> None:
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")
    monkeypatch.setattr(settings, "staged_section_review", False)
    monkeypatch.setattr(settings, "staged_lesson_review", False)
    scripts = {slot: [_good(slot)] for slot in SLOTS}
    scripts["orient"] = [ValueError("not json")]  # no usable output: empty flagged section
    h = Harness(monkeypatch, scripts=scripts)
    packet, snapshot = _packet(), _snapshot()
    spine_result = await stp.run_spine_stage(packet, snapshot, trace_id="t", generation_id="g")
    sections = {}
    for slot in SLOTS:
        result = await stp.run_section_stage(
            spine_result.spine, slot, packet, snapshot, trace_id="t", generation_id="g"
        )
        sections[slot] = stp.section_result_from_json(stp.section_result_to_json(result))
    assert sections["orient"].unresolved and sections["orient"].blocks == []
    assert sections["orient"].draft is None
    result = await stp.finish_staged_plan(
        packet, snapshot, spine_result, sections, trace_id="t", generation_id="g"
    )
    assert h.section_review_calls == 0 and h.lesson_review_calls == 0
    assert result.semantic_review is None
    assert result.plan.sections[0].blocks == []
    assert "TEACHING_SECTION_UNRESOLVED" in {f["code"] for f in result.flags}

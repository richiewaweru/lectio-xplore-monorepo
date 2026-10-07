"""Option D 3A: plan generation (per-card items + V2 Teaching Plan) on the shared runtime.

Covers Run admission (idempotent, one ``backbone`` item first, shared Build),
the PreparationWorker (backbone, then per-card items, then ``teaching_plan``;
runs admitted before the backbone stage still complete), finalization and the
projection, typed failure + retry/regenerate, lease reclaim, the legacy state,
and Build reuse by the SharedDocument Run.  Providers are always stubbed.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _prepared_lesson

from app import app
from application.unit_lesson.preparation_runs import (
    MAX_ATTEMPTS,
    PreparationRunError,
    admit_preparation_run,
    latest_preparation_run,
    load_current_source,
    load_preparation_run_views,
    preparation_request_key,
)
from application.unit_lesson.preparation_worker import PreparationWorker
from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LessonProvenanceModel,
    PackItemModel,
)
from core.entities.user import User
from curriculum.backbone.errors import BackboneOutputInvalidError
from curriculum.backbone.models import LessonBackbone, backbone_hash
from curriculum.backbone.persistence import load_backbone, store_backbone
from curriculum.backbone.writer import BackboneRun
from curriculum.items.diagnostics import attempt_record
from curriculum.items.generator import ItemBackboneRef, ItemGenerationResult, ItemGenerationRun
from curriculum.planning.models import (
    AnchorSpec,
    ItemOption,
    LessonIntent,
    QuestionBrief,
    StructuralPlan,
)
from curriculum.planning.persistence import load_chunked_state
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import teaching_plan_review_identity
from curriculum.workspace_projection import project_lesson_workspace, workspace_state_from_layers
from document.shared_lesson.approved_source import load_current_approved_teaching_plan_source
from document.shared_lesson.realization_source import ensure_shared_document_run
from infra.auth.middleware import get_current_user
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.database.session import get_async_session
from infra.generation_runtime import claim_work_item, retry_work_item
from print.generation.whole_lesson.repository import PageDocumentRepository


def _user(user_id: str) -> User:
    now = _naive_now()
    return User(
        id=user_id,
        email=f"{user_id}@example.invalid",
        name=user_id,
        created_at=now,
        updated_at=now,
    )


def _naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _structural_plan() -> dict[str, Any]:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(goal="Explain how water moves.", structure_rationale="Concrete."),
        anchor=AnchorSpec(example="a covered leaf", reuse_scope="throughout"),
        prior_knowledge=[],
        sections=[],
        question_plan=[],
        answer_key_style="brief_explanations",
    ).model_dump(mode="json")


def _context() -> dict[str, Any]:
    return {
        "signals": {
            "topic": "water",
            "prior_knowledge": [],
            "learner_needs": [],
            "teacher_goal": "Explain how water moves.",
            "inferred_lesson_mode": "first_exposure",
            "lesson_mode_confidence": "high",
        },
        "form": {
            "grade_level": "Grade 4",
            "subject": "Science",
            "duration_minutes": 45,
            "resource_type": "lesson",
            "topic": "water",
            "outcome": "Explain how water moves.",
        },
        "resource_spec": {},
        "shared_preparation": True,
    }


def _result(card_id: str, *, with_refs: bool = False) -> ItemGenerationResult:
    return ItemGenerationResult(
        card_id=card_id,
        backbone_refs=(
            {f"{card_id}-q{i}": ItemBackboneRef(target="anchor-1", figure_id="fig-1") for i in range(1, 6)}
            if with_refs
            else {}
        ),
        items=[
            QuestionBrief(
                question_id=f"{card_id}-q{i}",
                prompt_text=f"Stem {i}",
                options=[
                    ItemOption(key="A", text="right", correct=True, diagnoses=None),
                    ItemOption(key="B", text="wrong", correct=False, diagnoses="m1"),
                    ItemOption(key="C", text="other", correct=False, diagnoses=None),
                    ItemOption(key="D", text="other2", correct=False, diagnoses=None),
                ],
                expected_answer="right",
            )
            for i in range(1, 6)
        ],
    )


def _backbone() -> LessonBackbone:
    return LessonBackbone.model_validate(
        {
            "anchor": {
                "id": "anchor-1",
                "story": "A covered leaf loses 12 mL of water in 3 hours.",
                "data": {"water_lost_ml": 12, "hours": 3},
                "answer": "4 mL per hour",
                "figure_ids": ["fig-1"],
            },
            "variants": [
                {"id": "v1", "change": "other numbers", "data": {"water_lost_ml": 20, "hours": 4}}
            ],
            "figures": [
                {
                    "id": "fig-1",
                    "purpose": "Show the leaf setup",
                    "must_show": ["leaf", "bag"],
                    "labels_required": ["12 mL"],
                }
            ],
        }
    )


class _Calls:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.stage_events: list[str] = []
        self.fail: dict[str, BaseException] = {}
        self.item_backbones: list[LessonBackbone | None] = []

    async def backbone_runner(self, inputs, *, generation_id, max_attempts=2):  # noqa: ANN001
        self.events.append("backbone")
        exc = self.fail.get("backbone")
        if exc is not None:
            raise exc
        return BackboneRun(
            backbone=_backbone(),
            attempts=[
                attempt_record(
                    correlation_id=f"backbone:{generation_id}",
                    card_id="backbone",
                    attempt=1,
                    started_at=time.perf_counter(),
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"backbone:{generation_id}",
        )

    async def item_runner(self, card, *, generation_id, max_attempts=3, backbone=None):  # noqa: ANN001
        self.events.append(f"items:{card.id}")
        self.item_backbones.append(backbone)
        exc = self.fail.get(card.id)
        if exc is not None:
            raise exc
        return ItemGenerationRun(
            result=_result(card.id, with_refs=backbone is not None),
            attempts=[
                attempt_record(
                    correlation_id=f"item:{generation_id}:{card.id}",
                    card_id=card.id,
                    attempt=1,
                    started_at=time.perf_counter(),
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=f"item:{generation_id}:{card.id}",
        )

    async def teaching_runner(self, session, generation_id, *, require_items=True, **_):  # noqa: ANN001
        self.events.append("teaching_plan")
        exc = self.fail.get("teaching_plan")
        if exc is not None:
            raise exc
        plan = _teaching_plan()
        repo = PageDocumentRepository(session, generation_id)
        await repo.save_lesson_packet(
            {"lesson": {"path_lesson_id": "fixture", "objective": "Fixture"}, "approved_items": []}
        )
        await repo.save_lesson_legality({"resource_id": "lesson", "catalogue_hash": "fixture"})
        await repo.save_teaching_plan(plan=plan, validation={}, qc=[])
        return {"teaching_plan": plan}

    # Staged stage runners (the only planner): cheap fakes around the same plan stub.
    # They log to ``stage_events``; ``events`` keeps the single "teaching_plan" entry
    # of the finish stage so tests that read ``events`` are unchanged.

    async def spine_runner(self, session, generation_id, *, require_items=True, **_):  # noqa: ANN001
        self.stage_events.append("spine")
        exc = self.fail.get("teaching_spine")
        if exc is not None:
            raise exc
        slots = [s["slot_id"] for s in _teaching_plan()["sections"]]
        return {"spine": {"sections": [{"slot_id": slot} for slot in slots]}}

    async def section_runner(self, session, generation_id, *, spine_json, slot_id, **_):  # noqa: ANN001
        self.stage_events.append(f"section:{slot_id}")
        exc = self.fail.get(f"teaching_section:{slot_id}")
        if exc is not None:
            raise exc
        return {"slot_id": slot_id, "blocks": [], "unresolved": False}

    async def finish_runner(self, session, generation_id, *, spine_json, section_jsons, **_):  # noqa: ANN001
        self.stage_events.append("finish")
        return await self.teaching_runner(session, generation_id)

    def staged_runners(self) -> dict[str, Any]:
        return {
            "spine": self.spine_runner,
            "section": self.section_runner,
            "finish": self.finish_runner,
        }


def _teaching_plan() -> dict[str, Any]:
    return TeachingPlan(
        teaching_plan_id="tp-stub",
        revision=1,
        preparation_hash="input-stub",
        contract_version=2,
        learner_title="How water moves through a plant",
        starting_state=["Learner has observed a covered leaf."],
        target_state=["Learner can trace water movement through a plant."],
        arc="Trace how water moves through a plant.",
        sections=[
            {
                "slot_id": "orient",
                "specific_purpose": "Connect an observation to the investigation.",
                "display_title": "Orient",
                "entry_state": ["Learner has observed a covered leaf."],
                "must_establish": ["Water moves through a plant."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learner can trace water movement through a plant."],
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Observe a covered leaf.",
                        "evidence": "A relevant observation.",
                    }
                ],
            }
        ],
    ).model_dump(mode="json")


async def _seed(db_session: AsyncSession, *, user_id: str, cards: tuple[str, ...] = ("c1",)):
    """A prepared lesson awaiting structural review with concept cards."""
    lesson = await _prepared_lesson(db_session, user_id=user_id)
    prep_id = str(lesson.pack_id)
    generation = await db_session.get(GenerationModel, prep_id)
    assert generation is not None
    plan = _structural_plan()
    generation.status = "awaiting_review"
    generation.planning_spec_json = "{}"
    generation.chunked_state_json = {
        "stage": "awaiting_review",
        "structure_review_open": True,
        "path_prepared": True,
        "shared_preparation": True,
        "structural_plan": plan,
        "context": _context(),
    }
    for card_id in cards:
        db_session.add(
            ConceptCardModel(
                id=f"{user_id}-{card_id}",
                pack_id=prep_id,
                slug=f"science.{card_id}",
                title=f"Card {card_id}",
                objective="Explain how water moves",
                prereqs=[],
                misconceptions=[{"id": "m1", "description": "Plants eat soil", "source": "drafted"}],
            )
        )
    await db_session.commit()
    return lesson, prep_id


def _worker(factory, calls: _Calls, worker_id: str = "prep-w1", **kwargs) -> PreparationWorker:
    kwargs.setdefault("staged_runners", calls.staged_runners())
    return PreparationWorker(
        factory,
        worker_id=worker_id,
        item_runner=calls.item_runner,
        teaching_runner=calls.teaching_runner,
        backbone_runner=calls.backbone_runner,
        **kwargs,
    )


async def _tick(worker: PreparationWorker, factory, *, now: datetime | None = None) -> bool:
    async with factory() as session:
        progressed = await worker.run_one(session, now=now)
        await session.commit()
    return progressed


async def _drain(worker, factory, *, max_ticks: int = 16) -> None:
    for _ in range(max_ticks):
        if not await _tick(worker, factory):
            return


async def _run(factory, prep_id: str) -> GenerationRunModel:
    async with factory() as session:
        run = await latest_preparation_run(session, generation_id=prep_id)
        assert run is not None
        session.expunge_all()
        return run


async def _admit(db_session: AsyncSession, prep_id: str, user_id: str, **kwargs):
    admission = await admit_preparation_run(
        db_session, generation_id=prep_id, owner_user_id=user_id, **kwargs
    )
    await db_session.commit()
    return admission


async def _workspace(factory, prep_id: str):
    async with factory() as session:
        generation = await session.get(GenerationModel, prep_id)
        views = await load_preparation_run_views(session, generation_ids=[prep_id])
        state = workspace_state_from_layers(await load_chunked_state(prep_id, session), None)
        assert generation is not None
        return project_lesson_workspace(
            generation_id=prep_id, state=state, preparation_run=views.get(prep_id)
        ).preparation


# --------------------------------------------------------------------- admission


@pytest.mark.asyncio
async def test_admission_is_idempotent_and_admits_only_the_backbone_item(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-admit"
    lesson, prep_id = await _seed(db_session, user_id=user_id, cards=("c1", "c2"))

    first = await _admit(db_session, prep_id, user_id)
    second = await _admit(db_session, prep_id, user_id)

    assert first.created is True and second.created is False
    assert first.run.id == second.run.id and first.attempt == 1
    run = await _run(db_session_factory, prep_id)
    source = await load_current_source(db_session, generation_id=prep_id)
    assert run.run_type == "preparation" and run.status == "queued"
    assert (run.source_artifact_type, run.source_artifact_id) == (
        "lesson_structural_plan",
        prep_id,
    )
    assert run.source_revision == lesson.revision
    assert run.source_hash == source.source_hash
    assert run.request_key == f"preparation:{prep_id}:{source.source_hash}"
    async with db_session_factory() as session:
        keys = sorted(
            (
                await session.scalars(
                    select(GenerationWorkItemModel.item_key).where(
                        GenerationWorkItemModel.run_id == run.id
                    )
                )
            ).all()
        )
        builds = await session.scalar(select(func.count()).select_from(GenerationBuildModel))
        build = await session.get(GenerationBuildModel, run.build_id)
    assert keys == ["backbone"]  # items:* are admitted by the worker once it is ready
    assert builds == 1 and build is not None and build.path_lesson_id == lesson.id
    # Compatibility stamps: the structural review is closed; the Run is the status.
    state = await load_chunked_state(prep_id, db_session)
    assert state["structure_review_open"] is False


@pytest.mark.asyncio
async def test_admission_checks_owner_current_prep_and_precondition(
    db_session: AsyncSession,
) -> None:
    user_id = "3a-guard"
    lesson, prep_id = await _seed(db_session, user_id=user_id)
    with pytest.raises(PreparationRunError) as foreign:
        await admit_preparation_run(db_session, generation_id=prep_id, owner_user_id="someone-else")
    assert foreign.value.status_code == 404

    generation = await db_session.get(GenerationModel, prep_id)
    state = dict(generation.chunked_state_json)
    state.update(stage="complete", structure_review_open=False)
    generation.chunked_state_json = state
    await db_session.commit()
    with pytest.raises(PreparationRunError) as not_awaiting:
        await admit_preparation_run(db_session, generation_id=prep_id, owner_user_id=user_id)
    assert not_awaiting.value.code == "PREPARATION_NOT_AWAITING_APPROVAL"

    state.update(stage="awaiting_review", structure_review_open=True)
    generation.chunked_state_json = state
    provenance = await db_session.get(LessonProvenanceModel, prep_id)
    provenance.invalidated_at = _naive_now()
    await db_session.commit()
    with pytest.raises(PreparationRunError) as stale:
        await admit_preparation_run(db_session, generation_id=prep_id, owner_user_id=user_id)
    assert stale.value.code == "PREPARATION_STALE"

    provenance.invalidated_at = None
    lesson.pack_id = "some-newer-prep"
    await db_session.commit()
    with pytest.raises(PreparationRunError) as not_current:
        await admit_preparation_run(db_session, generation_id=prep_id, owner_user_id=user_id)
    assert not_current.value.code == "PREPARATION_NOT_CURRENT"


@pytest.mark.asyncio
async def test_http_plan_admission_and_regenerate_routes(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-http"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: _user(user_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post(f"/api/v1/preparations/{prep_id}/plan", json={})
            second = await client.post(f"/api/v1/preparations/{prep_id}/plan")
            regen = await client.post(f"/api/v1/preparations/{prep_id}/plan:regenerate")
            app.dependency_overrides[get_current_user] = lambda: _user("intruder")
            foreign = await client.post(f"/api/v1/preparations/{prep_id}/plan")
    finally:
        app.dependency_overrides.pop(get_async_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["run_id"] == second.json()["run_id"]
    assert first.json()["created"] is True and second.json()["created"] is False
    assert regen.status_code == 409
    assert regen.json()["detail"]["code"] == "PREPARATION_NOT_REGENERATABLE"
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_http_structure_preview_is_owner_scoped(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3d-structure"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: _user(user_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ok = await client.get(f"/api/v1/preparations/{prep_id}/structure")
            app.dependency_overrides[get_current_user] = lambda: _user("intruder")
            foreign = await client.get(f"/api/v1/preparations/{prep_id}/structure")
    finally:
        app.dependency_overrides.pop(get_async_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert ok.status_code == 200
    assert ok.json()["generation_id"] == prep_id
    assert ok.json()["structural_plan"] == _structural_plan()
    assert foreign.status_code == 404


# ------------------------------------------------------------------------ worker


@pytest.mark.asyncio
async def test_worker_runs_backbone_then_items_then_teaching_plan_and_finalizes_ready(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-flow"
    _lesson, prep_id = await _seed(db_session, user_id=user_id, cards=("c1", "c2"))
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    worker = _worker(db_session_factory, calls)

    first = (await _workspace(db_session_factory, prep_id)).progress
    assert (first.backbone, first.items_total, first.teaching_plan) == ("queued", 0, "not_started")

    assert await _tick(worker, db_session_factory) is True  # backbone (+ admits items:*)
    assert calls.events == ["backbone"]
    progress = (await _workspace(db_session_factory, prep_id)).progress
    assert (progress.backbone, progress.items_total, progress.items_ready) == ("ready", 2, 0)
    async with db_session_factory() as session:
        stored = await load_backbone(session, prep_id)
        state = await load_chunked_state(prep_id, session)
    assert stored == _backbone()
    assert state["backbone"]["hash"] == backbone_hash(_backbone())
    assert state["backbone_generation"]["attempts"][0]["class"] == "OK"
    assert "backbone" not in state["structural_plan"] and "backbone" not in state["context"]
    run_now = await _run(db_session_factory, prep_id)
    assert (await load_current_source(db_session, generation_id=prep_id)).source_hash == run_now.source_hash
    for item in run_now.work_items:  # items are bound to the backbone they are written against
        if item.item_key.startswith("items:"):
            from infra.execution.checkpoints import content_hash

            assert item.input_hash == content_hash(
                {
                    "card_id": item.item_key[len("items:"):],
                    "source_hash": run_now.source_hash,
                    "backbone_hash": backbone_hash(_backbone()),
                }
            )

    assert await _tick(worker, db_session_factory) is True  # card 1
    assert calls.events == ["backbone", f"items:{user_id}-c1"]
    assert (await _workspace(db_session_factory, prep_id)).state == "planning"
    assert (await _workspace(db_session_factory, prep_id)).progress.items_ready == 1

    assert await _tick(worker, db_session_factory) is True  # card 2 (+ admits teaching_spine)
    assert calls.events == ["backbone", f"items:{user_id}-c1", f"items:{user_id}-c2"]
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.item_key == "teaching_spine")
        )
        assert item is not None and item.status == "queued"

    assert await _tick(worker, db_session_factory) is True  # spine (+ admits one item per section)
    section_count = len(_teaching_plan()["sections"])
    for _ in range(section_count):
        assert await _tick(worker, db_session_factory) is True  # one section each
    assert calls.stage_events[0] == "spine" and len(calls.stage_events) == 1 + section_count
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.item_key == "teaching_plan")
        )
        assert item is not None and item.status == "queued"

    assert await _tick(worker, db_session_factory) is True  # teaching plan + finalize
    assert calls.events[-1] == "teaching_plan"
    assert calls.events.count("teaching_plan") == 1
    assert await _tick(worker, db_session_factory) is False  # nothing left to do

    run = await _run(db_session_factory, prep_id)
    assert run.status == "ready"
    assert run.output_artifact_type == "teaching_plan_revision"
    assert run.output_revision == 1 and run.output_hash
    async with db_session_factory() as session:
        rows = await session.scalar(
            select(func.count()).select_from(PackItemModel).where(PackItemModel.pack_id == prep_id)
        )
        generation = await session.get(GenerationModel, prep_id)
    assert rows == 10
    assert calls.item_backbones == [_backbone(), _backbone()]  # items are written against it
    async with db_session_factory() as session:
        stored_rows = list(
            (await session.scalars(select(PackItemModel).where(PackItemModel.pack_id == prep_id))).all()
        )
    assert {
        (row.backbone_ref["target"], row.backbone_ref["figure_id"], row.backbone_ref["backbone_hash"])
        for row in stored_rows
    } == {("anchor-1", "fig-1", backbone_hash(_backbone()))}
    assert generation.status == "awaiting_teaching_approval"  # written by save_teaching_plan

    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "awaiting_review" and workspace.review_kind == "teaching_plan"
    assert workspace.run_id == run.id
    assert workspace.progress.items_total == 2 and workspace.progress.teaching_plan == "ready"
    assert workspace.progress.backbone == "ready"
    assert workspace.recovery_action == "review"


@pytest.mark.asyncio
async def test_approval_then_document_run_reuses_the_preparation_build(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-approve"
    lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    await _drain(_worker(db_session_factory, calls), db_session_factory)
    prep_run = await _run(db_session_factory, prep_id)
    assert prep_run.status == "ready"

    async with db_session_factory() as session:
        repo = PageDocumentRepository(session, prep_id)
        state = await repo.load_page_generation_state()
        identity = teaching_plan_review_identity(state)
        assert identity["pending_hash_verified"] is True
        await repo.save_teaching_review(
            status="approved",
            expected_revision=identity["revision"],
            expected_content_hash=identity["pending_content_hash"],
            reviewed_by=user_id,
            queue=False,
        )
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "approved" and workspace.approved_snapshot_verified is True

    async with db_session_factory() as session:
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=user_id,
            path_lesson_id=lesson.id,
            preparation_generation_id=prep_id,
        )
        assert source.revision == 1
        doc_run = await ensure_shared_document_run(
            session, owner_user_id=user_id, path_lesson_id=lesson.id
        )
        await session.commit()
    assert doc_run.run_type == "shared_document"
    assert doc_run.build_id == prep_run.build_id  # one timeline
    async with db_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(GenerationBuildModel)) == 1


@pytest.mark.asyncio
async def test_recoverable_card_failure_isolates_the_card_and_retries_to_ready(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-retry"
    _lesson, prep_id = await _seed(db_session, user_id=user_id, cards=("c1", "c2"))
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    calls.fail[f"{user_id}-c2"] = TimeoutError("provider timed out")
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)

    run = await _run(db_session_factory, prep_id)
    assert run.status == "failed_recoverable"
    assert "teaching_plan" not in calls.events  # not admitted while a card is failed
    async with db_session_factory() as session:
        items = {
            i.item_key: i
            for i in (
                await session.scalars(
                    select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run.id)
                )
            ).all()
        }
        packs = list(
            (await session.scalars(select(PackItemModel.card_id).where(PackItemModel.pack_id == prep_id))).all()
        )
    good, bad = items[f"items:{user_id}-c1"], items[f"items:{user_id}-c2"]
    assert good.status == "ready" and len(packs) == 5  # sibling unaffected
    assert bad.status == "failed_recoverable" and bad.recovery_action == "retry"
    assert bad.error_class == "provider_transport"

    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_recoverable" and workspace.retryable is True
    assert workspace.recovery_action == "retry" and workspace.run_id == run.id
    assert workspace.progress.items_ready == 1 and workspace.progress.items_failed == 1
    assert workspace.progress.failed_work_item_ids == [bad.id]

    # Generic runtime retry of the one card; the worker picks it up.
    del calls.fail[f"{user_id}-c2"]
    async with db_session_factory() as session:
        await retry_work_item(session, work_item_id=bad.id, owner_user_id=user_id)
        await session.commit()
    await _drain(worker, db_session_factory)
    assert (await _run(db_session_factory, prep_id)).status == "ready"
    assert calls.events.count("teaching_plan") == 1


@pytest.mark.asyncio
async def test_teaching_plan_failure_is_typed_and_retryable(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-teach-fail"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    calls.fail["teaching_plan"] = TimeoutError("planner timed out")
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)

    run = await _run(db_session_factory, prep_id)
    assert run.status == "failed_recoverable"
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_recoverable" and workspace.retryable is True
    assert workspace.progress.teaching_plan == "failed"
    teaching_item = next(i for i in run.work_items if i.item_key == "teaching_plan")
    assert workspace.progress.failed_work_item_ids == [teaching_item.id]
    assert workspace.error is not None and workspace.error.work_item_id == teaching_item.id
    assert calls.events.count(f"items:{user_id}-c1") == 1  # items are not redone

    del calls.fail["teaching_plan"]
    async with db_session_factory() as session:
        await retry_work_item(session, work_item_id=teaching_item.id, owner_user_id=user_id)
        await session.commit()
    await _drain(worker, db_session_factory)
    assert (await _run(db_session_factory, prep_id)).status == "ready"
    assert calls.events.count(f"items:{user_id}-c1") == 1


@pytest.mark.asyncio
async def test_terminal_failure_regenerates_attempts_bounded_at_three(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-regen"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    first = await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    calls.fail[f"{user_id}-c1"] = ValueError("item contract violated")
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)

    run1 = await _run(db_session_factory, prep_id)
    assert run1.id == first.run.id and run1.status == "failed_terminal"
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_terminal" and workspace.recovery_action == "regenerate"
    assert workspace.retryable is not True

    source = await load_current_source(db_session, generation_id=prep_id)
    attempts = [run1]
    for attempt in range(2, MAX_ATTEMPTS + 1):
        admission = await _admit(db_session, prep_id, user_id, regenerate=True)
        assert admission.created is True and admission.attempt == attempt
        assert admission.run.request_key == preparation_request_key(
            prep_id, source.source_hash, attempt
        )
        assert admission.run.build_id == run1.build_id
        await _drain(worker, db_session_factory)
        attempts.append(await _run(db_session_factory, prep_id))
        assert attempts[-1].status == "failed_terminal"
    with pytest.raises(PreparationRunError) as exhausted:
        await admit_preparation_run(
            db_session, generation_id=prep_id, owner_user_id=user_id, regenerate=True
        )
    assert exhausted.value.code == "PREPARATION_ATTEMPTS_EXHAUSTED" and exhausted.value.status_code == 409
    assert len({run.id for run in attempts}) == 3


@pytest.mark.asyncio
async def test_rejected_plan_regenerates_and_ready_run_cannot_regenerate_while_pending(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-reject"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)
    with pytest.raises(PreparationRunError) as pending:
        await admit_preparation_run(
            db_session, generation_id=prep_id, owner_user_id=user_id, regenerate=True
        )
    assert pending.value.code == "PREPARATION_NOT_REGENERATABLE"
    await db_session.rollback()

    async with db_session_factory() as session:
        await PageDocumentRepository(session, prep_id).save_teaching_review(
            status="rejected", expected_revision=1, reviewed_by=user_id
        )
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_terminal" and workspace.recovery_action == "regenerate"

    admission = await _admit(db_session, prep_id, user_id, regenerate=True)
    assert admission.attempt == 2
    await _drain(worker, db_session_factory)
    assert (await _run(db_session_factory, prep_id)).status == "ready"
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "awaiting_review"  # a fresh pending draft replaces the rejection
    # Items were not regenerated for the new attempt (fresh rows already exist),
    # and the same-input backbone they were written against is reused.
    assert calls.events.count(f"items:{user_id}-c1") == 1
    assert calls.events.count("backbone") == 1
    new_run = await _run(db_session_factory, prep_id)
    assert {i.item_key for i in new_run.work_items} >= {"backbone", f"items:{user_id}-c1"}
    async with db_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(PackItemModel).where(PackItemModel.pack_id == prep_id)
            )
            == 5
        )


@pytest.mark.asyncio
async def test_expired_lease_is_reclaimed_by_a_second_worker(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-lease"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    long_ago = _naive_now() - timedelta(hours=1)
    source = await load_current_source(db_session, generation_id=prep_id)
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.item_key == "backbone")
        )
        claimed = await claim_work_item(
            session,
            work_item_id=item.id,
            worker_id="dead-worker",
            source=source,
            lease_seconds=30,
            now=long_ago,
        )
        await session.commit()
        assert claimed.status == "running" and claimed.lease_owner == "dead-worker"

    calls = _Calls()
    live = _worker(db_session_factory, calls, worker_id="live-worker")
    await _drain(live, db_session_factory)
    async with db_session_factory() as session:
        item = await session.scalar(
            select(GenerationWorkItemModel).where(GenerationWorkItemModel.item_key == "backbone")
        )
    assert item.status == "ready" and item.lease_owner == "live-worker" and item.attempt == 2
    assert (await _run(db_session_factory, prep_id)).status == "ready"


@pytest.mark.asyncio
async def test_items_are_reused_only_under_the_same_backbone_hash(
    db_session: AsyncSession, db_session_factory
) -> None:
    from application.unit_lesson.preparation_items import generate_card_items

    user_id = "3a-stale-backbone"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    calls = _Calls()
    card_id = f"{user_id}-c1"
    async with db_session_factory() as session:
        await store_backbone(session, prep_id, _backbone(), input_hash="h1")
        await session.commit()

    async def run_card() -> dict[str, Any]:
        return await generate_card_items(
            session_factory=db_session_factory,
            generation_id=prep_id,
            card_id=card_id,
            item_runner=calls.item_runner,
        )

    assert (await run_card())["skipped"] is False
    assert (await run_card())["skipped"] is True  # same backbone hash: reuse
    assert calls.events == [f"items:{card_id}"]

    changed = _backbone().model_copy(deep=True)
    changed.anchor.story = "A covered leaf loses 15 mL of water in 3 hours."
    async with db_session_factory() as session:
        await store_backbone(session, prep_id, changed, input_hash="h2")
        await session.commit()
    summary = await run_card()
    assert summary["skipped"] is False  # stale under the new backbone: regenerated
    assert calls.item_backbones[-1] == changed
    async with db_session_factory() as session:
        rows = list(
            (await session.scalars(select(PackItemModel).where(PackItemModel.pack_id == prep_id))).all()
        )
    assert len(rows) == 5
    assert {r.backbone_ref["backbone_hash"] for r in rows} == {backbone_hash(changed)}
    assert not any(r.stale for r in rows)


@pytest.mark.asyncio
async def test_lease_lost_worker_cannot_overwrite_pack_items(
    db_session: AsyncSession, db_session_factory
) -> None:
    """The fence runs before pack rows are written: a stale lease writes nothing."""
    from application.unit_lesson.preparation_items import generate_card_items
    from infra.execution.leases import LeaseLostError

    user_id = "3a-fence"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    calls = _Calls()

    async def lost() -> None:
        raise LeaseLostError("lease lost")

    with pytest.raises(LeaseLostError):
        await generate_card_items(
            session_factory=db_session_factory,
            generation_id=prep_id,
            card_id=f"{user_id}-c1",
            item_runner=calls.item_runner,
            fence=lost,
        )
    async with db_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count()).select_from(PackItemModel).where(PackItemModel.pack_id == prep_id)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_structure_edited_after_admission_fails_the_run_as_source_conflict(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-source"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    generation = await db_session.get(GenerationModel, prep_id)
    state = dict(generation.chunked_state_json)
    plan = dict(state["structural_plan"])
    plan["answer_key_style"] = "changed"
    state["structural_plan"] = plan
    generation.chunked_state_json = state
    await db_session.commit()

    calls = _Calls()
    await _drain(_worker(db_session_factory, calls), db_session_factory)
    run = await _run(db_session_factory, prep_id)
    assert run.status == "failed_terminal" and run.error_code == "preparation_source_changed"
    assert calls.events == []  # nothing was generated from a stale structure
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_terminal" and workspace.recovery_action == "regenerate"


# -------------------------------------------------------------------- projection


@pytest.mark.asyncio
async def test_projection_states_for_new_and_legacy_preparations(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-proj"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)

    # stage 1: structural review is open, no Run
    workspace = await _workspace(db_session_factory, prep_id)
    assert (workspace.state, workspace.review_kind) == ("awaiting_review", "structural")

    # queued Run
    await _admit(db_session, prep_id, user_id)
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "planning" and workspace.run_id
    assert workspace.progress.items_total == 0 and workspace.progress.items_ready == 0
    assert workspace.progress.backbone == "queued"

    # legacy: an old row with no marker, no plan and no Run (its worker stage is ignored)
    _legacy_lesson, legacy_id = await _seed(db_session, user_id="3a-proj-legacy")
    generation = await db_session.get(GenerationModel, legacy_id)
    state = dict(generation.chunked_state_json)
    state.pop("structure_review_open")
    state["stage"] = "stage2_running"
    generation.chunked_state_json = state
    await db_session.commit()
    workspace = await _workspace(db_session_factory, legacy_id)
    assert workspace.state == "legacy_unsupported"
    assert workspace.recovery_action == "regenerate"
    assert workspace.error.message == "Prepared before the planning update — re-prepare this lesson."


def test_legacy_pending_plan_without_run_stays_reviewable_and_approved_is_unaffected() -> None:
    from curriculum.teaching_plan.revisions import TeachingRevisionStore
    from print.generation.whole_lesson.repository import empty_page_document_state

    plan = TeachingPlan.model_validate(_teaching_plan())
    page = empty_page_document_state()
    store = TeachingRevisionStore(page)
    store.record_draft(plan, preparation_hash="h", revision=1)
    page["teaching_plan"] = store.get_revision(1).plan
    pending = project_lesson_workspace(generation_id="g", state=page).preparation
    assert (pending.state, pending.review_kind) == ("awaiting_review", "teaching_plan")

    record = store.get_revision(1)
    store.approve(
        expected_revision=1,
        expected_content_hash=record.content_hash,
        reviewed_by="u",
        teacher_note=None,
    )
    approved = project_lesson_workspace(generation_id="g", state=page).preparation
    assert approved.state == "approved" and approved.approved_snapshot_verified is True


def test_run_view_is_the_only_status_input() -> None:
    from curriculum.workspace_projection import PreparationRunView

    for status, expected in (
        ("queued", "planning"),
        ("running", "planning"),
        ("failed_terminal", "failed_terminal"),
        ("cancelled", "failed_terminal"),
    ):
        workspace = project_lesson_workspace(
            generation_id="g",
            state={"stage": "awaiting_review", "structure_review_open": True, "structural_plan": {}},
            preparation_run=PreparationRunView(run_id="r1", status=status),
        )
        assert workspace.preparation.state == expected
        assert workspace.preparation.run_id == "r1"
    recoverable = project_lesson_workspace(
        generation_id="g",
        state={},
        preparation_run=PreparationRunView(run_id="r1", status="failed_recoverable", retryable=True),
    ).preparation
    assert (recoverable.state, recoverable.retryable, recoverable.recovery_action) == (
        "failed_recoverable",
        True,
        "retry",
    )


def test_reviewer_output_failure_is_retryable() -> None:
    from application.unit_lesson.preparation_worker import classify_failure
    from curriculum.teaching_plan.semantic_review import TeachingPlanSemanticReviewError

    failure = classify_failure(
        TeachingPlanSemanticReviewError("TEACHING_SEMANTIC_REVIEW_FAILED", "reviewer failed")
    )
    assert failure.recovery_action == "retry"
    assert failure.error_code == "preparation_reviewer_output_invalid"


# --------------------------------------------------------------------- backbone


@pytest.mark.asyncio
async def test_backbone_failure_is_typed_isolated_and_retries_to_ready(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-bb-fail"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    calls.fail["backbone"] = BackboneOutputInvalidError(
        attempt_count=2, details=["anchor.figure_ids: unknown figure"]
    )
    worker = _worker(db_session_factory, calls)
    await _drain(worker, db_session_factory)

    run = await _run(db_session_factory, prep_id)
    assert run.status == "failed_recoverable"
    assert calls.events == ["backbone"]  # no items or plan before the backbone exists
    item = next(i for i in run.work_items if i.item_key == "backbone")
    assert item.status == "failed_recoverable" and item.error_code == "backbone_invalid"
    assert item.error_class == "provider_output" and item.recovery_action == "retry"
    assert "scenario" in item.error_summary

    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.state == "failed_recoverable" and workspace.retryable is True
    assert workspace.progress.backbone == "failed" and workspace.progress.items_total == 0
    assert workspace.progress.failed_work_item_ids == [item.id]
    assert workspace.error is not None and workspace.error.code == "backbone_invalid"

    del calls.fail["backbone"]
    async with db_session_factory() as session:
        await retry_work_item(session, work_item_id=item.id, owner_user_id=user_id)
        await session.commit()
    await _drain(worker, db_session_factory)
    assert (await _run(db_session_factory, prep_id)).status == "ready"
    assert calls.events[:2] == ["backbone", "backbone"]
    assert calls.events.count(f"items:{user_id}-c1") == 1


@pytest.mark.asyncio
async def test_backbone_provider_timeout_uses_provider_mapping(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-bb-timeout"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)
    await _admit(db_session, prep_id, user_id)
    calls = _Calls()
    calls.fail["backbone"] = TimeoutError("provider timed out")
    await _drain(_worker(db_session_factory, calls), db_session_factory)
    run = await _run(db_session_factory, prep_id)
    item = next(i for i in run.work_items if i.item_key == "backbone")
    assert item.error_class == "provider_transport" and item.recovery_action == "retry"
    assert item.error_code != "backbone_invalid"


@pytest.mark.asyncio
async def test_legacy_run_without_backbone_item_still_completes(
    db_session: AsyncSession, db_session_factory
) -> None:
    """A run admitted before the backbone stage (items:* from the start) is unchanged."""
    from application.unit_lesson.preparation_runs import (
        LEGACY_DEFINITION_VERSION,
        add_card_items,
    )
    from infra.generation_runtime import SourceIdentity

    user_id = "3a-legacy-run"
    _lesson, prep_id = await _seed(db_session, user_id=user_id, cards=("c1", "c2"))
    admission = await _admit(db_session, prep_id, user_id)
    # Rewrite the run into its pre-backbone shape.
    async with db_session_factory() as session:
        backbone_item = await session.scalar(
            select(GenerationWorkItemModel).where(
                GenerationWorkItemModel.run_id == admission.run.id,
                GenerationWorkItemModel.item_key == "backbone",
            )
        )
        await session.delete(backbone_item)
        run = await session.get(GenerationRunModel, admission.run.id)
        generation = await session.get(GenerationModel, prep_id)
        await add_card_items(
            session,
            run=run,
            generation=generation,
            source=SourceIdentity(
                source_artifact_type=run.source_artifact_type,
                source_artifact_id=run.source_artifact_id,
                source_revision=run.source_revision,
                source_hash=run.source_hash,
            ),
            definition_version=LEGACY_DEFINITION_VERSION,
        )
        await session.commit()

    calls = _Calls()
    await _drain(_worker(db_session_factory, calls), db_session_factory)
    assert "backbone" not in calls.events
    assert calls.events == [f"items:{user_id}-c1", f"items:{user_id}-c2", "teaching_plan"]
    assert (await _run(db_session_factory, prep_id)).status == "ready"
    workspace = await _workspace(db_session_factory, prep_id)
    assert workspace.progress.backbone == "not_started" and workspace.progress.items_total == 2
    assert workspace.progress.teaching_plan == "ready"


@pytest.mark.asyncio
async def test_http_backbone_is_owner_scoped_and_404_until_ready(
    db_session: AsyncSession, db_session_factory
) -> None:
    user_id = "3a-bb-http"
    _lesson, prep_id = await _seed(db_session, user_id=user_id)

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: _user(user_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            before = await client.get(f"/api/v1/preparations/{prep_id}/backbone")
            await _admit(db_session, prep_id, user_id)
            await _tick(_worker(db_session_factory, _Calls()), db_session_factory)
            ok = await client.get(f"/api/v1/preparations/{prep_id}/backbone")
            app.dependency_overrides[get_current_user] = lambda: _user("intruder")
            foreign = await client.get(f"/api/v1/preparations/{prep_id}/backbone")
    finally:
        app.dependency_overrides.pop(get_async_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert before.status_code == 404
    assert ok.status_code == 200
    assert ok.json() == {
        "backbone": _backbone().model_dump(mode="json"),
        "hash": backbone_hash(_backbone()),
    }
    assert foreign.status_code == 404

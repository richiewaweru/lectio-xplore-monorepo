from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_shared_document_full_run import (
    _admit,
    _advance_semantic_worker,
)
from test_shared_lesson_approved_source import _prepared

from core.database.models import (
    ConceptModel,
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from curriculum.planning.objective_ownership import hash_path_objective
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.http import (
    ReviewDraftRevisionRequest,
    ReviewDraftSubmitRequest,
    ReviewDraftTextEdit,
    get_shared_document_review_draft,
    post_shared_document_review_draft_revision,
    post_shared_document_review_draft_submit,
)
from document.shared_lesson.models import build_shared_lesson_document
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from document.shared_lesson.repository import save_shared_lesson_document
from document.shared_lesson.runtime import TeachingPlanSource
from infra.config import settings
from infra.database.models import GenerationEventModel, GenerationRunModel, GenerationWorkItemModel
from infra.generation_runtime import active_work_items
from media.generation.contracts import GeneratedVisualBlock


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _figure_plan(*, plan_id: str = "plan-figure") -> TeachingPlan:
    return TeachingPlan(
        contract_version=2,
        teaching_plan_id=plan_id,
        revision=1,
        preparation_hash="preparation-hash",
        approval_status="pending",
        learner_title="How water reaches a leaf",
        arc="Trace water movement from roots to leaves.",
        starting_state=["Learner can name a root."],
        target_state=["Learner can explain water movement."],
        sections=[
            {
                "slot_id": "orient",
                "display_title": "Start with the root",
                "specific_purpose": "Connect the observation to the question.",
                "entry_state": ["Learner can name a root."],
                "must_establish": ["Roots take in water."],
                "avoid_repeating": [],
                "bridge_from_previous": None,
                "exit_state": ["Learner can describe root uptake."],
                "blocks": [
                    {
                        "id": "orient-callout",
                        "position": 0,
                        "intent": "Address a common misconception about roots.",
                        "brief": "Warn learners about a common misconception on water uptake.",
                        "evidence": "Learner avoids the misconception.",
                        "source_question_ids": [],
                        "task_mode": "none",
                    },
                    {
                        "id": "orient-figure",
                        "position": 1,
                        "intent": "Show a diagram of the root structure.",
                        "brief": "Show a diagram of the root hairs taking in water.",
                        "evidence": "Learner interprets the diagram.",
                        "source_question_ids": [],
                        "task_mode": "none",
                    },
                ],
            }
        ],
    )


async def _prepared_with_figure(db_session, *, user_id: str = "source-owner"):
    """Same shape as ``_prepared`` but with a section holding a callout + figure."""
    user = UserModel(id=user_id, email=f"{user_id}@example.invalid", name=user_id)
    unit = UnitModel(
        id=f"unit-{user_id}",
        owner_id=user_id,
        title="Water movement",
        topic="Plants",
        subject="Science",
        grade_level="4",
        destination_objective="Explain water movement.",
    )
    concept = ConceptModel(
        id=f"concept-{user_id}",
        canonical_slug=f"water-{user_id}",
        subject="Science",
        title="Water movement",
        created_by=user_id,
    )
    version = PathVersionModel(
        id=f"version-{user_id}",
        unit_id=unit.id,
        version=1,
        source_plan_json={"lessons": []},
        status="approved",
    )
    lesson = PathLessonModel(
        id=f"lesson-{user_id}",
        path_version_id=version.id,
        concept_id=concept.id,
        concept_slug="water-movement",
        title="Water movement",
        objective="Explain how water reaches a leaf.",
        objective_hash=hash_path_objective("Explain how water reaches a leaf."),
        primary_knowledge_type="conceptual",
        position=0,
        revision=3,
    )
    plan = _figure_plan(plan_id=f"plan-{user_id}")
    page_state: dict[str, object] = {}
    store = TeachingRevisionStore(page_state)
    store.record_draft(plan, preparation_hash="preparation-hash", revision=1)
    record = store.approve(
        expected_revision=1,
        expected_content_hash=teaching_plan_content_hash(plan),
        reviewed_by=user_id,
    )
    generation_id = f"prep-{user_id}"
    generation = GenerationModel(
        id=generation_id,
        user_id=user_id,
        subject="Science",
        context="shared preparation",
        status="awaiting_review",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=_now(),
        chunked_state_json={"page_document_v2": page_state},
    )
    lesson.pack_id = generation_id
    provenance = LessonProvenanceModel(
        pack_id=generation_id,
        path_version_id=version.id,
        path_lesson_id=lesson.id,
        objective_hash=lesson.objective_hash,
        path_lesson_revision=lesson.revision,
    )
    db_session.add_all([user, unit, concept, version, lesson, generation, provenance])
    await db_session.flush()
    source = TeachingPlanSource(
        plan=TeachingPlan.model_validate(record.plan),
        revision_record=record,
        id=record.teaching_plan_id,
        revision=record.revision,
        content_hash=record.content_hash or "",
    )
    return generation, lesson, provenance, source


def _figure_composer_provider(calls: list[dict]):
    async def provide(payload):
        calls.append(payload)
        blocks = payload["section"]["blocks"]
        callout_block = next(b for b in blocks if b["id"] == "orient-callout")
        figure_block = next(b for b in blocks if b["id"] == "orient-figure")
        return {
            "items": [
                {
                    "teaching_block_id": callout_block["id"],
                    "kind": "callout",
                    "semantic_role": "misconception",
                },
                {
                    "teaching_block_id": figure_block["id"],
                    "kind": "figure",
                    "semantic_role": "visual_model",
                },
            ]
        }

    return provide


def _figure_writer_provider(calls: list[dict]):
    async def provide(payload):
        calls.append(payload)
        items = payload["composition_plan"]
        callout_item = next(i for i in items if i["kind"] == "callout")
        figure_item = next(i for i in items if i["kind"] == "figure")
        return {
            "nodes": [
                {
                    "id": callout_item["id"],
                    "kind": "callout",
                    "teaching_block_id": callout_item["teaching_block_id"],
                    "display": {
                        "tone": "note",
                        "title": "Common misconception",
                        "body": (
                            "Some learners think leaves absorb water directly, but roots "
                            "take in water through tiny root hairs."
                        ),
                    },
                },
                {
                    "id": figure_item["id"],
                    "kind": "figure",
                    "teaching_block_id": figure_item["teaching_block_id"],
                    "display": {"caption": "Root hairs absorbing water"},
                    "accessibility": {
                        "alt_text": (
                            "Learner can describe root uptake using this diagram of root hairs."
                        )
                    },
                },
            ]
        }

    return provide


async def _advance_figure_semantic_worker(db_session, db_session_factory, *, generation, lesson):
    from document.shared_lesson.worker import SharedDocumentWorker

    class _Sourcebook:
        def __init__(self):
            self.calls = []

        async def invoke(self, call):
            self.calls.append(call)
            return {"entries": []}

    sourcebook = _Sourcebook()
    composer_calls: list[dict] = []
    writer_calls: list[dict] = []
    worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="figure-run-worker",
        provider=sourcebook,
        composer_provider=_figure_composer_provider(composer_calls),
        writer_provider=_figure_writer_provider(writer_calls),
    )
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await worker.run_one(session)
            await session.commit()
        if not progressed:
            break
    return sourcebook, composer_calls, writer_calls


class _FakeFigureExecutor:
    """A durable, deterministic media executor stub for tests."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = 0

    async def execute_figure(self, order):
        self.calls += 1
        if self.fail:
            return [
                GeneratedVisualBlock(
                    visual_id=order.visual.id,
                    attaches_to=order.visual.attaches_to,
                    mode=order.visual.mode,
                    image_url=None,
                    caption=order.visual.purpose,
                    alt_text=order.visual.purpose,
                    source_work_order_id=order.work_order_id,
                    status="failed",
                    error_message="image_generation_api_call failed (RuntimeError): dead image API",
                )
            ]
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                mode=order.visual.mode,
                image_url=f"https://cdn.example.test/{order.visual.id}.png",
                caption=order.visual.purpose,
                alt_text=order.visual.purpose,
                source_work_order_id=order.work_order_id,
                status="ready",
            )
        ]


async def _issue_on_callout_then_edit(db_session, db_session_factory):
    """Bring a figure-containing Run to a saved review draft that edits the callout."""
    generation, lesson, _provenance, _source = await _prepared_with_figure(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_figure_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "The callout assumes an unapproved fact.",
                    "required_correction": "Repair the callout text.",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        media_executor=_FakeFigureExecutor(),
        qa_semantic_validator=issue_once,
        worker_id="figure-review-issue",
    )
    assert outcome.state == "blocked", outcome.error
    assert outcome.stage in {"finalization", "qa_handoff"}

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"
        draft = await get_shared_document_review_draft(
            run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    callout_section = draft["document"]["sections"][0]
    callout_node = next(node for node in callout_section["nodes"] if node["kind"] == "callout")

    async with db_session_factory() as session:
        edited = await post_shared_document_review_draft_revision(
            run.id,
            ReviewDraftRevisionRequest(
                expected_revision=draft["draft"]["revision"],
                expected_hash=draft["draft"]["hash"],
                edits=(
                    ReviewDraftTextEdit(
                        section_id=callout_section["id"],
                        node_id=callout_node["id"],
                        field="callout_body",
                        value=(
                            "Roots take in water through tiny root hairs, not through leaves "
                            "as some learners first assume."
                        ),
                    ),
                ),
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert edited["draft"]["revision"] == draft["draft"]["revision"] + 1
    return admission, generation, lesson, edited


async def _active_media_items(db_session_factory, *, run_id: str):
    async with db_session_factory() as session:
        rows = list(
            (
                await session.scalars(
                    select(GenerationWorkItemModel).where(
                        GenerationWorkItemModel.run_id == run_id,
                        GenerationWorkItemModel.stage == "media_generation",
                    )
                )
            ).all()
        )
    return rows, active_work_items(rows)


@pytest.mark.asyncio
async def test_review_submit_regenerates_figure_media_for_edited_figure_section(
    db_session, db_session_factory
):
    admission, generation, lesson, edited = await _issue_on_callout_then_edit(
        db_session, db_session_factory
    )

    _all_media_before, active_media_before = await _active_media_items(
        db_session_factory, run_id=admission.run.id
    )
    assert len(active_media_before) == 1
    original_media_item = active_media_before[0]
    assert original_media_item.status == "ready"

    async with db_session_factory() as session:
        submit_outcome = await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert submit_outcome["document_revision"] == edited["draft"]["revision"]

    all_media_after, active_media_after = await _active_media_items(
        db_session_factory, run_id=admission.run.id
    )
    # A brand-new linked replacement media WorkItem was admitted, and it is
    # not a reuse of the original figure's stale (pre-edit) frozen identity.
    assert len(all_media_after) == 2
    assert len(active_media_after) == 1
    replacement_media_item = active_media_after[0]
    assert replacement_media_item.id != original_media_item.id
    assert replacement_media_item.replaces_work_item_id == original_media_item.id
    assert replacement_media_item.status == "queued"
    assert replacement_media_item.item_key != original_media_item.item_key

    async def pass_qa(_request):
        return DocumentSemanticVerdict(status="pass")

    executor = _FakeFigureExecutor()
    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        media_executor=executor,
        qa_semantic_validator=pass_qa,
        worker_id="figure-review-pass",
    )
    assert outcome.state == "ready", outcome.error
    assert executor.calls == 1  # only the stale figure's replacement is regenerated

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "ready"
        assert run.output_revision == edited["draft"]["revision"]

    _final_all, final_active = await _active_media_items(
        db_session_factory, run_id=admission.run.id
    )
    assert len(final_active) == 1
    assert final_active[0].id == replacement_media_item.id
    assert final_active[0].status == "ready"


@pytest.mark.asyncio
async def test_review_submit_figure_media_failure_blocks_ready_without_media_optional(
    db_session, db_session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "shared_document_media_optional", False)
    admission, generation, lesson, edited = await _issue_on_callout_then_edit(
        db_session, db_session_factory
    )
    async with db_session_factory() as session:
        await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()

    async def pass_qa(_request):
        raise AssertionError("media failure must stop before semantic QA")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        media_executor=_FakeFigureExecutor(fail=True),
        qa_semantic_validator=pass_qa,
        worker_id="figure-review-media-fail",
    )
    assert outcome.state == "blocked"
    assert outcome.stage == "media"

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status != "ready"


@pytest.mark.asyncio
async def test_review_submit_figure_media_failure_defers_when_media_optional_is_on(
    db_session, db_session_factory, monkeypatch
):
    monkeypatch.setattr(settings, "shared_document_media_optional", True)
    admission, generation, lesson, edited = await _issue_on_callout_then_edit(
        db_session, db_session_factory
    )
    async with db_session_factory() as session:
        await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()

    async def pass_qa(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        media_executor=_FakeFigureExecutor(fail=True),
        qa_semantic_validator=pass_qa,
        worker_id="figure-review-media-deferred",
    )
    assert outcome.state == "ready", outcome.error

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "ready"


async def _issue_then_edit(db_session, db_session_factory, monkeypatch):
    """Bring a Run to a saved (revision-2) review draft awaiting submission."""
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson, monkeypatch=monkeypatch
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "The section assumes an unapproved fact.",
                    "required_correction": "Repair the affected section input.",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_once,
        worker_id="review-submit-issue",
    )
    assert outcome.state == "blocked"
    assert outcome.stage == "finalization" or outcome.stage == "qa_handoff"

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"

        draft = await get_shared_document_review_draft(
            run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    section = draft["document"]["sections"][0]
    node = section["nodes"][0]
    assert node["kind"] == "paragraph"

    async with db_session_factory() as session:
        edited = await post_shared_document_review_draft_revision(
            run.id,
            ReviewDraftRevisionRequest(
                expected_revision=draft["draft"]["revision"],
                expected_hash=draft["draft"]["hash"],
                edits=(
                    ReviewDraftTextEdit(
                        section_id=section["id"],
                        node_id=node["id"],
                        field="text",
                        value="Roots take in water through tiny root hairs.",
                    ),
                ),
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert edited["draft"]["revision"] == draft["draft"]["revision"] + 1
    return admission, generation, lesson, edited


@pytest.mark.asyncio
async def test_review_submit_happy_path_promotes_edited_revision(
    db_session, db_session_factory, monkeypatch
):
    admission, generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )

    async with db_session_factory() as session:
        submit_outcome = await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert submit_outcome["document_revision"] == edited["draft"]["revision"]

    async def pass_qa(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=pass_qa,
        worker_id="review-submit-pass",
    )
    assert outcome.state == "ready", outcome.error

    async with db_session_factory() as verify:
        run = await verify.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "ready"
        assert run.output_revision == edited["draft"]["revision"]
        assert run.output_hash

        events = list(
            (
                await verify.scalars(
                    select(GenerationEventModel).where(
                        GenerationEventModel.run_id == admission.run.id,
                        GenerationEventModel.event_type == "review_revision_promoted",
                    )
                )
            ).all()
        )
        assert len(events) == 1
        assert events[0].safe_payload_json["document_revision"] == edited["draft"]["revision"]


@pytest.mark.asyncio
async def test_review_submit_rejects_stale_expected_hash(
    db_session, db_session_factory, monkeypatch
):
    admission, _generation, _lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=edited["draft"]["revision"],
                    expected_hash="0" * 64,
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_review_submit_rejects_no_edit(db_session, db_session_factory, monkeypatch):
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson, monkeypatch=monkeypatch
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "unapproved fact",
                    "required_correction": "repair",
                },
            ),
        )

    await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_once,
        worker_id="review-submit-no-edit",
    )
    async with db_session_factory() as session:
        draft = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=draft["draft"]["revision"],
                    expected_hash=draft["draft"]["hash"],
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_review_submit_rejects_forged_structural_edit(
    db_session, db_session_factory, monkeypatch
):
    admission, _generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        current = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    payload = current["document"]
    # Forge a structural change (drop a node) bypassing the proof normally
    # enforced by ``post_shared_document_review_draft_revision``.
    payload["revision"] = current["draft"]["revision"] + 1
    payload["sections"][0]["nodes"] = payload["sections"][0]["nodes"][1:]
    payload.pop("content_hash", None)
    forged = build_shared_lesson_document(payload)
    async with db_session_factory() as session:
        await save_shared_lesson_document(
            session, path_lesson_id=lesson.id, document=forged
        )
        await session.commit()

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=forged.revision,
                    expected_hash=forged.content_hash,
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 422


@pytest.mark.asyncio
async def test_review_submit_rejects_foreign_owner(db_session, db_session_factory, monkeypatch):
    admission, _generation, _lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_submit(
                admission.run.id,
                ReviewDraftSubmitRequest(
                    expected_revision=edited["draft"]["revision"],
                    expected_hash=edited["draft"]["hash"],
                ),
                current_user=SimpleNamespace(id="someone-else"),
                session=session,
            )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_review_submit_issue_again_keeps_edited_revision_as_latest_draft(
    db_session, db_session_factory, monkeypatch
):
    admission, generation, lesson, edited = await _issue_then_edit(
        db_session, db_session_factory, monkeypatch
    )
    async with db_session_factory() as session:
        await post_shared_document_review_draft_submit(
            admission.run.id,
            ReviewDraftSubmitRequest(
                expected_revision=edited["draft"]["revision"],
                expected_hash=edited["draft"]["hash"],
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()

    async def issue_again(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "still unapproved",
                    "required_correction": "repair again",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_again,
        worker_id="review-submit-issue-again",
    )
    assert outcome.state == "blocked"

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"
        latest = await get_shared_document_review_draft(
            admission.run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    assert latest["draft"]["revision"] == edited["draft"]["revision"]
    assert latest["draft"]["hash"] == edited["draft"]["hash"]


@pytest.mark.asyncio
async def test_review_submit_accepts_accessibility_description_edit_on_ordinary_node(
    db_session, db_session_factory, monkeypatch
):
    """A reviewer can correct an ordinary node's accessibility.description.

    Regression for the live gap where a reviewer rewrote a paragraph's
    display.text but the node's accessibility.description still described
    the removed example, and document QA flagged unsupported_claim -- the
    review allowlist only let reviewers edit accessibility on figures.
    """
    generation, lesson, _provenance, _source = await _prepared(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson, monkeypatch=monkeypatch
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_claim",
                    "affected_section_id": "orient",
                    "explanation": (
                        "The paragraph's accessibility description still references "
                        "a removed example."
                    ),
                    "required_correction": "Correct the accessibility description.",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        qa_semantic_validator=issue_once,
        worker_id="review-submit-accessibility",
    )
    assert outcome.state == "blocked"

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        assert run.status == "failed_recoverable"
        draft = await get_shared_document_review_draft(
            run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    section = draft["document"]["sections"][0]
    node = section["nodes"][0]
    assert node["kind"] == "paragraph"

    async with db_session_factory() as session:
        edited = await post_shared_document_review_draft_revision(
            run.id,
            ReviewDraftRevisionRequest(
                expected_revision=draft["draft"]["revision"],
                expected_hash=draft["draft"]["hash"],
                edits=(
                    ReviewDraftTextEdit(
                        section_id=section["id"],
                        node_id=node["id"],
                        field="accessibility_description",
                        value="Describes the current, corrected paragraph content.",
                    ),
                ),
            ),
            current_user=SimpleNamespace(id="source-owner"),
            session=session,
        )
        await session.commit()
    assert edited["draft"]["revision"] == draft["draft"]["revision"] + 1
    edited_section = edited["document"]["sections"][0]
    edited_node = edited_section["nodes"][0]
    assert (
        edited_node["accessibility"]["description"]
        == "Describes the current, corrected paragraph content."
    )
    # The node's own display text and identity are untouched by this edit.
    assert edited_node["display"]["text"] == node["display"]["text"]
    assert edited_node["id"] == node["id"]


@pytest.mark.asyncio
async def test_review_submit_rejects_accessibility_description_on_figure_node(
    db_session, db_session_factory
):
    """accessibility_description is not allowlisted for a figure (only figure_alt_text is)."""
    generation, lesson, _provenance, _source = await _prepared_with_figure(db_session)
    admission = await _admit(db_session, generation=generation, lesson=lesson)
    await _advance_figure_semantic_worker(
        db_session, db_session_factory, generation=generation, lesson=lesson
    )

    async def issue_once(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "unsupported_assumption",
                    "affected_section_id": "orient",
                    "explanation": "The callout assumes an unapproved fact.",
                    "required_correction": "Repair the callout text.",
                },
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=admission.run.id,
        owner_user_id="source-owner",
        path_lesson_id=lesson.id,
        preparation_generation_id=generation.id,
        media_executor=_FakeFigureExecutor(),
        qa_semantic_validator=issue_once,
        worker_id="figure-review-accessibility-reject",
    )
    assert outcome.state == "blocked", outcome.error

    async with db_session_factory() as session:
        run = await session.get(GenerationRunModel, admission.run.id)
        assert run is not None
        draft = await get_shared_document_review_draft(
            run.id, current_user=SimpleNamespace(id="source-owner"), session=session
        )
    section = draft["document"]["sections"][0]
    figure_node = next(node for node in section["nodes"] if node["kind"] == "figure")

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as excinfo:
            await post_shared_document_review_draft_revision(
                run.id,
                ReviewDraftRevisionRequest(
                    expected_revision=draft["draft"]["revision"],
                    expected_hash=draft["draft"]["hash"],
                    edits=(
                        ReviewDraftTextEdit(
                            section_id=section["id"],
                            node_id=figure_node["id"],
                            field="accessibility_description",
                            value="Forged description on a figure",
                        ),
                    ),
                ),
                current_user=SimpleNamespace(id="source-owner"),
                session=session,
            )
    assert excinfo.value.status_code == 422

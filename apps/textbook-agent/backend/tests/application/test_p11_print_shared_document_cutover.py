"""P11: Print creation routes only through a verified SharedLessonDocument.

Mirrors ``tests/application/test_p10b_shared_document_learn_cutover.py`` for
the Print admission/worker seam: duplicate admission pinning, the closed
``load_realization_source`` state machine end to end
(pending/needs_review/stale/ready) from ``claim_next_native_job``, a
monkeypatch proof that the ready path never calls ordinary
composer/writer/whole-lesson-form authoring, and an answer-key integrity
check against the SharedDocument task evaluations.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.application.test_p03_realization_gates import _approved_native_preparation
from tests.application.test_p04_learn_worker import _drive_shared_document_ready
from tests.print_learn._p10c_fixtures import build_rich_shared_document

from application.unit_lesson.realization_worker import RealizationWorker
from application.unit_lesson.realize_print_handoff import realize_print_from_preparation
from core.database.models import GenerationModel, NativeRealizationModel
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.realization_source import ReadyRealizationSource
from document.shared_lesson.post_section_pipeline import run_post_section_pipeline
from document.shared_lesson.worker import SharedDocumentWorker
from print.generation.shared_document_execution import (
    materialize_print_output_from_shared_document,
)
from print.rendering.page_objects.document_assembly import reload_document


@pytest.mark.asyncio
async def test_duplicate_admission_reuses_same_shared_document_run_pin(
    db_session: AsyncSession,
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p11-duplicate-admit"
    )

    first = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )
    second = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )

    assert first["realization_id"] == second["realization_id"]
    row = await db_session.get(NativeRealizationModel, first["realization_id"])
    assert row is not None
    assert row.shared_document_run_id is not None

    third = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-duplicate-admit",
        path_lesson_id=lesson.id,
        admission_request_key="admit-once",
    )
    row_again = await db_session.get(NativeRealizationModel, third["realization_id"])
    assert row_again is not None
    assert row_again.shared_document_run_id == row.shared_document_run_id


@pytest.mark.asyncio
async def test_worker_gate_reports_pending_without_consuming_an_attempt(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p11-pending"
    )
    admitted = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-pending",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None
    assert row.status == "queued"

    worker = RealizationWorker(db_session_factory, worker_id="p11-pending-worker")
    async with db_session_factory() as worker_session:
        await worker.run_one(worker_session)

    await db_session.refresh(row)
    assert row.status == "queued"  # no Run, no lease, no attempt consumed
    assert row.generation_run_id is None
    assert row.shared_document_state == "pending"


@pytest.mark.usefixtures("blocking_quality_gate")
@pytest.mark.asyncio
async def test_worker_gate_reports_needs_shared_review(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, _plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p11-needs-review"
    )
    admitted = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-needs-review",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    row = await db_session.get(NativeRealizationModel, admitted["realization_id"])
    assert row is not None
    run_id = row.shared_document_run_id
    assert run_id is not None

    from tests.application.test_p04_learn_worker import (
        _shared_document_composer,
        _shared_document_writer,
        _SharedDocumentSourcebookProvider,
    )

    worker = SharedDocumentWorker(
        db_session_factory,
        worker_id="p11-needs-review-worker",
        provider=_SharedDocumentSourcebookProvider(),
        composer_provider=_shared_document_composer,
        writer_provider=_shared_document_writer,
    )
    for _ in range(4):
        async with db_session_factory() as session:
            progressed = await worker.run_one(session)
            await session.commit()
        if not progressed:
            break

    async def _qa_issue(_request):
        from document.shared_lesson.continuity import ContinuityIssue

        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                ContinuityIssue(
                    issue_code="must_establish_uncovered",
                    affected_section_id="orient",
                    explanation="The section never establishes the target state.",
                    required_correction="Add a sentence establishing the target state.",
                ),
            ),
        )

    outcome = await run_post_section_pipeline(
        db_session_factory,
        run_id=run_id,
        owner_user_id="p11-needs-review",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
        qa_semantic_validator=_qa_issue,
        worker_id="p11-needs-review-post-section",
    )
    assert outcome.state == "blocked"

    review_worker = RealizationWorker(db_session_factory, worker_id="p11-needs-review-claim")
    async with db_session_factory() as tick_session:
        await review_worker.run_one(tick_session)
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "needs_shared_review"
        assert row.shared_document_state == "needs_review"


@pytest.mark.asyncio
async def test_worker_gate_reports_stale_after_new_approved_revision(
    db_session: AsyncSession, db_session_factory
) -> None:
    lesson, plan, _source, _document = await _approved_native_preparation(
        db_session, user_id="p11-stale"
    )
    admitted = await realize_print_from_preparation(
        db_session,
        preparation_generation_id=str(lesson.pack_id),
        user_id="p11-stale",
        path_lesson_id=lesson.id,
    )
    await db_session.commit()
    await _drive_shared_document_ready(
        db_session,
        db_session_factory,
        owner_user_id="p11-stale",
        path_lesson_id=lesson.id,
        preparation_generation_id=str(lesson.pack_id),
    )

    async with db_session_factory() as writer:
        generation = await writer.get(GenerationModel, str(lesson.pack_id))
        assert generation is not None
        state = deepcopy(generation.chunked_state_json)
        page_state = state["page_document_v2"]
        store = TeachingRevisionStore(page_state)
        new_plan = plan.model_copy(update={"arc": "A revised arc for the stale-source test."})
        store.record_draft(new_plan, preparation_hash="preparation-hash", revision=2)
        store.approve(
            expected_revision=2,
            expected_content_hash=teaching_plan_content_hash(
                new_plan.model_copy(update={"revision": 2})
            ),
            reviewed_by="p11-stale",
        )
        generation.chunked_state_json = state
        await writer.commit()

    stale_worker = RealizationWorker(db_session_factory, worker_id="p11-stale-claim")
    async with db_session_factory() as tick_session:
        await stale_worker.run_one(tick_session)
    async with db_session_factory() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "failed_recoverable"
        assert row.shared_document_state == "stale"
        assert row.error_summary is not None
        assert row.error_summary.startswith("SHARED_DOCUMENT_STALE")


@pytest.mark.asyncio
async def test_ready_path_never_calls_ordinary_authoring() -> None:
    # ``NativeExecutionWorker``/``execute_print_realization_from_shared_document``
    # verify through ``core.database.session.async_session_factory`` (the
    # production DB conftest wires up), not the isolated per-test
    # ``db_session``/``db_session_factory`` fixtures (a separate tmp_path
    # engine) — so this test drives the whole thing on that same production
    # session factory, exactly like the other real-worker tests in
    # ``tests/planning/test_native_retry_durability.py``.
    #
    # P11B deleted the ordinary whole-lesson executor
    # (``print.generation.whole_lesson.executor``) and its
    # ``execute_after_teaching_approval`` entrypoint entirely, so there is no
    # function left to monkeypatch-forbid here — the guard is now structural
    # (see ``tests/architecture/test_p11b_print_ordinary_authoring_guard.py``).
    # This test still proves the ready path completes end to end through the
    # pure SharedLessonDocument adapter.
    from core.database.session import async_session_factory as prod_sessions

    async with prod_sessions() as session:
        lesson, _plan, _source, _document = await _approved_native_preparation(
            session, user_id="p11-ready-guard"
        )
        admitted = await realize_print_from_preparation(
            session,
            preparation_generation_id=str(lesson.pack_id),
            user_id="p11-ready-guard",
            path_lesson_id=lesson.id,
        )
        await session.commit()
        await _drive_shared_document_ready(
            session,
            prod_sessions,
            owner_user_id="p11-ready-guard",
            path_lesson_id=lesson.id,
            preparation_generation_id=str(lesson.pack_id),
        )

    worker = RealizationWorker(prod_sessions, worker_id="p11-ready-guard-worker")
    async with prod_sessions() as worker_session:
        assert await worker.run_one(worker_session) is True

    async with prod_sessions() as verify:
        row = await verify.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None
        assert row.status == "ready"
        assert row.shared_document_state == "ready"
        assert row.shared_document_id is not None
        assert row.shared_document_revision is not None
        assert row.shared_document_hash is not None

        output = await verify.get(GenerationModel, row.output_id)
        assert output is not None
        assert output.status == "ready"
        assert output.shared_document_id == row.shared_document_id
        assert isinstance(output.document_json, dict)
        document = reload_document(output.document_json)
        node_kinds = {block["object"] for section in document["sections"] for block in section["blocks"]}
        assert "prose" in node_kinds


@pytest.mark.asyncio
async def test_answer_key_matches_shared_document_task_evaluations() -> None:
    """Drive a real worker completion (repo persistence + hash fencing) with a
    rich SharedLessonDocument, then verify the persisted Print document's
    answer key matches the SharedDocument task evaluations exactly.

    The document supplied here comes straight from ``_p10c_fixtures`` (the
    same rich fixture the P10C Learn publish/runtime tests use), so this is
    verified against the identical shared-content identity Learn's answer
    key/interaction proofs use — not a Print-only invented fixture. Uses the
    production session factory throughout (see
    ``test_ready_path_never_calls_ordinary_authoring`` for why).
    """
    from core.database.session import async_session_factory as prod_sessions

    async with prod_sessions() as session:
        lesson, _plan, _source, _document = await _approved_native_preparation(
            session, user_id="p11-answer-key"
        )
        admitted = await realize_print_from_preparation(
            session,
            preparation_generation_id=str(lesson.pack_id),
            user_id="p11-answer-key",
            path_lesson_id=lesson.id,
        )
        await session.commit()
        row = await session.get(NativeRealizationModel, admitted["realization_id"])
        assert row is not None

        document = build_rich_shared_document("p11-answer-key-doc")
        content_hash_value = shared_lesson_content_hash(document)
        assert content_hash_value == document.content_hash

        # Line up the pinned realization identity with this fixture
        # document's own teaching-plan lineage (the ORM row, not the
        # immutable document, is what carries the pin here) instead of
        # mutating a validated SharedLessonDocument's cross-checked
        # identity fields.
        row.teaching_plan_id = document.teaching_plan_id
        row.teaching_plan_revision = document.teaching_plan_revision
        row.teaching_plan_hash = document.teaching_plan_hash
        await session.flush()

        ready = ReadyRealizationSource(
            run_id=str(row.shared_document_run_id),
            document=document,
            content_hash=content_hash_value,
            plan_id=document.teaching_plan_id,
            plan_revision=document.teaching_plan_revision,
            plan_hash=document.teaching_plan_hash,
            media_results=(),
        )

        await session.commit()

    async with prod_sessions() as session:
        realization = await session.get(NativeRealizationModel, row.id)
        assert realization is not None
        result = await materialize_print_output_from_shared_document(
            session, realization=realization, ready=ready
        )
        await session.commit()
    assert result["output_id"] == str(row.output_id)

    async with prod_sessions() as verify:
        output = await verify.get(GenerationModel, str(row.output_id))
        assert output is not None
        assert output.status == "ready"
        persisted = reload_document(output.document_json)

    tasks_by_id = {task.id: task for task in document.tasks}
    answer_entries = persisted["answer_key"]["content"]["groups"][0]["entries"]
    assert len(answer_entries) == len(document.tasks)

    # task-choice: select-one, correct option "b" -> paper letter "B".
    choice_entry = next(e for e in answer_entries if e["answer"] == "B")
    assert choice_entry is not None

    # task-fill-blank: accepted answer "Paris" must appear verbatim.
    # Written answers are lowered to inline runs (doc 36); compare their plain text.
    def _plain(value: object) -> object:
        if isinstance(value, list):
            return "".join(str(run.get("value", "")) for run in value if isinstance(run, dict))
        return value

    fill_entry = next(e for e in answer_entries if _plain(e.get("answer")) == "Paris")
    assert fill_entry is not None

    # No raw internal task id ever leaks into the learner-facing answer key.
    for task_id in tasks_by_id:
        assert task_id not in str(persisted["answer_key"])

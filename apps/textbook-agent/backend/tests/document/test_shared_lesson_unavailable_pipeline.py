"""Terminal figure failure ships the lesson with a durable unavailable outcome.

Covers the runtime recording rule, readiness, every durable media reader and
the deterministic QA classification.  A figure with no media outcome at all
must stay a hard failure.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from document.shared_lesson import media_runtime
from document.shared_lesson.finalization_dispatcher import (
    SharedLessonFinalizationDispatchError,
    _durable_media_results,
)
from document.shared_lesson.finalizer import (
    SharedLessonFinalizationError,
    _verify_media_matches_work_items,
)
from document.shared_lesson.handoff_dispatcher import (
    SharedDocumentHandoffDispatchError,
    _verify_media as handoff_verify_media,
)
from document.shared_lesson.media import (
    BoundUnavailableFigureMedia,
    FigureMediaResult,
    bind_durable_media_outcome,
    bind_generated_figure,
    unavailable_figure_result,
)
from document.shared_lesson.media_runtime import (
    MediaWorkItemJob,
    admit_figure_media_work_item,
    execute_figure_media_work_item,
    project_media_readiness,
)
from document.shared_lesson.qa import qa_shared_lesson_document, split_media_outcomes
from document.shared_lesson.realization_source import (
    _document_media_results,
    load_run_figure_qc,
)
from document.shared_lesson.repository import (
    SharedLessonDocumentReadinessError,
    _validate_required_media,
)
from infra.database.models import GenerationEventModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import retry_work_item
from media.generation.contracts import GeneratedVisualBlock
from tests.document.test_shared_lesson_media import _block, _document, _shape, _source, _work
from tests.document.test_shared_lesson_media_runtime import (
    SOURCE,
    _accepted_for,
    _failed_provider_block,
    _seed_run,
)
from tests.document.test_shared_lesson_media_runtime import _work as runtime_work

REASON = "Figure drawing failed: the figure description could not be made consistent."


class _FailingExecutor:
    def __init__(self, work, *, error_code: str | None = None) -> None:
        self.work = work
        self.error_code = error_code
        self.calls = 0

    async def execute_figure(self, _order):
        self.calls += 1
        block = _failed_provider_block(self.work)
        if self.error_code:
            block = GeneratedVisualBlock(**{**block.model_dump(), "error_code": self.error_code})
        return [block]


async def _admit(db_session, *, suffix: str = "a"):
    owner, run_id = await _seed_run(db_session, suffix=suffix)
    work = runtime_work(suffix=suffix)
    admitted = await admit_figure_media_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
    )
    return owner, run_id, work, admitted.record.id


def _job(db_session, item_id, work, executor, worker="w"):
    return MediaWorkItemJob(
        session=db_session,
        work_item_id=item_id,
        worker_id=worker,
        source=SOURCE,
        work=work,
        accepted_section=_accepted_for(work),
        executor=executor,
    )


async def _rows(db_session, run_id):
    return list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    )


@pytest.mark.asyncio
async def test_exhausted_attempts_complete_the_leaf_as_unavailable(db_session) -> None:
    owner, run_id, work, item_id = await _admit(db_session)
    executor = _FailingExecutor(work)

    for attempt in (1, 2):
        outcome = await execute_figure_media_work_item(_job(db_session, item_id, work, executor))
        assert outcome.unavailable is None
        row = await db_session.get(GenerationWorkItemModel, item_id)
        assert row is not None and row.status == "failed_recoverable"
        readiness = project_media_readiness(await _rows(db_session, run_id), {item_id: work})
        # (c) retryable failure with attempts left: not ready, not settled.
        assert not readiness.ready
        assert readiness.failed_required_work_item_ids == (item_id,)
        assert row.attempt == attempt
        await retry_work_item(db_session, work_item_id=item_id, owner_user_id=owner)

    final = await execute_figure_media_work_item(_job(db_session, item_id, work, executor))
    assert final.unavailable is not None
    assert final.unavailable.attempts == 3
    assert final.unavailable.error_code == "provider_error"
    row = await db_session.get(GenerationWorkItemModel, item_id)
    assert row is not None
    assert row.status == "ready"
    assert row.output_json["status"] == "unavailable"
    assert row.output_hash == content_hash(row.output_json)
    # No raw provider text is ever persisted.
    assert "dead image API" not in str(row.output_json)

    readiness = project_media_readiness(await _rows(db_session, run_id), {item_id: work})
    assert readiness.ready
    assert readiness.ready_count == 1
    assert readiness.failed_required_work_item_ids == ()

    events = (
        await db_session.scalars(
            select(GenerationEventModel).where(GenerationEventModel.work_item_id == item_id)
        )
    ).all()
    assert any(event.event_type == "media_provider_failure_diagnostic" for event in events)


@pytest.mark.asyncio
async def test_non_retryable_provider_code_is_unavailable_on_the_first_attempt(
    db_session,
) -> None:
    _owner, run_id, work, item_id = await _admit(db_session, suffix="auth")
    outcome = await execute_figure_media_work_item(
        _job(db_session, item_id, work, _FailingExecutor(work, error_code="provider_http_403"))
    )
    assert outcome.unavailable is not None
    assert outcome.unavailable.error_code == "provider_http_403"
    assert outcome.unavailable.attempts == 1
    row = await db_session.get(GenerationWorkItemModel, item_id)
    assert row is not None and row.status == "ready"
    assert project_media_readiness(await _rows(db_session, run_id), {item_id: work}).ready

    records = await load_run_figure_qc_for_rows(db_session, run_id)
    assert records == ("unavailable", True)


async def load_run_figure_qc_for_rows(db_session, run_id):
    owner = "media-owner-auth"
    records = await load_run_figure_qc(db_session, run_id=run_id, owner_user_id=owner)
    assert len(records) == 1
    return records[0].qc_state, records[0].failed


@pytest.mark.asyncio
async def test_integrity_failure_at_the_last_attempt_stays_a_hard_failure(db_session) -> None:
    owner, run_id, work, item_id = await _admit(db_session, suffix="hard")

    class Misconfigured:
        async def execute_figure(self, _order):
            raise PermissionError("credentials rejected")

    for _ in range(2):
        await execute_figure_media_work_item(_job(db_session, item_id, work, _FailingExecutor(work)))
        await retry_work_item(db_session, work_item_id=item_id, owner_user_id=owner)
    outcome = await execute_figure_media_work_item(_job(db_session, item_id, work, Misconfigured()))
    assert outcome.unavailable is None
    assert outcome.error_code == "media_executor_configuration"
    row = await db_session.get(GenerationWorkItemModel, item_id)
    assert row is not None and row.status == "failed_terminal"
    assert not project_media_readiness(await _rows(db_session, run_id), {item_id: work}).ready


def test_terminal_rule_only_applies_to_retry_class_failures() -> None:
    from infra.generation_runtime import ErrorClass, RecoveryAction, WorkItemFailure

    def failure(code, action):
        return WorkItemFailure(
            error_code=code,
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="x",
            recovery_action=action,
        )

    rule = media_runtime._is_terminal_figure_failure
    assert rule(failure("provider_error", RecoveryAction.RETRY), attempt=3, max_attempts=3)
    assert not rule(failure("provider_error", RecoveryAction.RETRY), attempt=2, max_attempts=3)
    assert rule(failure("provider_http_401", RecoveryAction.RETRY), attempt=1, max_attempts=3)
    assert not rule(failure("provider_http_429", RecoveryAction.RETRY), attempt=1, max_attempts=3)
    assert not rule(
        failure("media_checkpoint_integrity", RecoveryAction.NONE), attempt=3, max_attempts=3
    )


def _unavailable_payload(work):
    return unavailable_figure_result(
        work, error_code="render_spec_invalid", reason=REASON, attempts=3
    ).model_dump(mode="json")


def _items():
    """Figure A unavailable, figure B ready, as durable ready WorkItems."""
    work_a, work_b = _work("section-a"), _work("section-b")
    payloads = [
        (work_a, _unavailable_payload(work_a)),
        (work_b, bind_generated_figure(work_b, [_block(work_b)]).model_dump(mode="json")),
    ]
    return [
        SimpleNamespace(
            id=f"item-{index}",
            stage="media_generation",
            item_key=f"media:{work.work_order.work_order_id}",
            status="ready",
            output_json=payload,
            output_hash=content_hash(payload),
        )
        for index, (work, payload) in enumerate(payloads)
    ]


def test_durable_readers_accept_unavailable_outcomes() -> None:
    document = _document()
    items = _items()
    results, required = _durable_media_results(document=document, active_items=items)
    assert required == {"section-a": ("figure-a",), "section-b": ("figure-b",)}
    assert isinstance(results[0], BoundUnavailableFigureMedia)
    assert isinstance(results[1], FigureMediaResult)

    assert isinstance(_document_media_results(document, items)[0], BoundUnavailableFigureMedia)

    ready_ids, unavailable = split_media_outcomes(results)
    assert ready_ids == ("figure-b",)
    assert unavailable == {"figure-a": REASON}

    # handoff + persistence boundaries
    assert handoff_verify_media(document, required, results) == (("figure-b",), unavailable)
    _validate_required_media(
        document=document, required_media_by_section=required, media_results=results
    )

    loaded = [SimpleNamespace(work_item_id=item.id, output_json=item.output_json) for item in items]
    _verify_media_matches_work_items(
        document=document, media_results=results, active_items=items, loaded_outputs=loaded
    )


def test_finalizer_rejects_a_bound_outcome_that_differs_from_its_durable_output() -> None:
    document = _document()
    items = _items()
    results, _required = _durable_media_results(document=document, active_items=items)
    forged = results[0].model_copy(update={"reason": "Something else entirely."})
    loaded = [SimpleNamespace(work_item_id=item.id, output_json=item.output_json) for item in items]
    with pytest.raises(SharedLessonFinalizationError, match="reason"):
        _verify_media_matches_work_items(
            document=document,
            media_results=[forged, results[1]],
            active_items=items,
            loaded_outputs=loaded,
        )


def test_declared_figure_with_no_media_outcome_is_still_hard() -> None:
    document = _document()
    items = _items()[:1]  # figure B has no media WorkItem at all
    with pytest.raises(SharedLessonFinalizationDispatchError):
        _durable_media_results(document=document, active_items=items)

    results = (bind_durable_media_outcome(items[0].output_json, document),)
    required = {"section-a": ("figure-a",), "section-b": ("figure-b",)}
    with pytest.raises(SharedLessonDocumentReadinessError, match="not ready"):
        _validate_required_media(
            document=document, required_media_by_section=required, media_results=results
        )
    with pytest.raises(SharedDocumentHandoffDispatchError):
        handoff_verify_media(document, required, results)


def _qa(**media):
    source = _source()
    return qa_shared_lesson_document(
        document=_document(),
        teaching_plan_sections=tuple(source.plan.sections),
        expected_shapes={"section-a": _shape("section-a"), "section-b": _shape("section-b")},
        expected_title=source.plan.learner_title,
        required_media_by_section={"section-a": ["figure-a"], "section-b": ["figure-b"]},
        **media,
    )


def test_unavailable_figure_is_an_advisory_qa_issue_and_missing_stays_hard() -> None:
    result = _qa(available_media_ids=("figure-b",), unavailable_media={"figure-a": REASON})
    advisory = [issue for issue in result.advisory_issues if issue.issue_code == "figure_media_unavailable"]
    assert len(advisory) == 1
    assert advisory[0].affected_node_ids == ("figure-a",)
    assert advisory[0].explanation == REASON
    assert "figure_media_unavailable" not in {issue.issue_code for issue in result.issues}
    assert "required_media_missing" not in {issue.issue_code for issue in result.issues}

    missing = _qa(available_media_ids=("figure-b",))
    codes = {issue.issue_code for issue in missing.issues}
    assert "required_media_missing" in codes
    assert not missing.advisory_issues or all(
        issue.issue_code != "figure_media_unavailable" for issue in missing.advisory_issues
    )

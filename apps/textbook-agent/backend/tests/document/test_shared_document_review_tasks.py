"""Review-path task wording edits and SharedDocument regeneration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from document.shared_lesson.http import (
    ReviewDraftTextEdit,
    _apply_task_text_edit,
    post_shared_document_regenerate,
)
from document.shared_lesson.qa_runtime import (
    DocumentQAWorkItemJob,
    admit_document_qa_work_item,
    execute_document_qa_work_item,
)
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from infra.database.models import GenerationRunModel


def _choice_task() -> dict:
    return {
        "id": "task-1",
        "prompt": "On that belief, how wide a band would you expect?",
        "response": {
            "type": "single_choice",
            "options": [{"id": "a", "text": "Narrow"}, {"id": "b", "text": "Wide"}],
        },
        "evaluation": {"type": "choice_keys", "correct_keys": ["b"]},
        "feedback": {"correct": "Yes.", "by_option": {"a": "Look again."}},
    }


def _edit(**fields) -> ReviewDraftTextEdit:
    return ReviewDraftTextEdit(section_id="s", node_id="anchor", value="New wording", **fields)


def test_task_prompt_option_and_feedback_edits_apply_without_touching_the_key() -> None:
    task = _choice_task()
    assert _apply_task_text_edit(task, _edit(field="task_prompt"))
    assert _apply_task_text_edit(task, _edit(field="task_option_text", option_id="a"))
    assert _apply_task_text_edit(task, _edit(field="task_feedback_text", feedback_key="by_option.a"))
    assert _apply_task_text_edit(task, _edit(field="task_feedback_text", feedback_key="correct"))

    assert task["prompt"] == "New wording"
    assert task["response"]["options"][0] == {"id": "a", "text": "New wording"}
    assert task["feedback"] == {"correct": "New wording", "by_option": {"a": "New wording"}}
    assert task["evaluation"] == {"type": "choice_keys", "correct_keys": ["b"]}


def test_task_edits_with_missing_targets_are_rejected() -> None:
    task = _choice_task()
    assert not _apply_task_text_edit(task, _edit(field="task_option_text", option_id="z"))
    assert not _apply_task_text_edit(task, _edit(field="task_feedback_text", feedback_key="partial"))
    no_options = {**_choice_task(), "response": {"type": "text"}}
    assert not _apply_task_text_edit(no_options, _edit(field="task_option_text", option_id="a"))


def test_task_edit_target_fields_are_validated() -> None:
    with pytest.raises(ValidationError):
        _edit(field="task_option_text")
    with pytest.raises(ValidationError):
        _edit(field="task_prompt", option_id="a")
    with pytest.raises(ValidationError):
        _edit(field="task_feedback_text")
    with pytest.raises(ValidationError):
        _edit(field="text", feedback_key="correct")


async def _flagged_run(db_session):
    from test_shared_qa_runtime import _deterministic, _seed_run, _source_and_document

    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="regen")
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=_deterministic(document),
    )

    async def issue(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                {
                    "issue_code": "answer_leakage",
                    "affected_section_id": document.sections[0].id,
                    "explanation": "The task key contradicts its prompt.",
                    "required_correction": "Regenerate the task.",
                },
            ),
        )

    await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=admitted.record.id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=_deterministic(document),
            semantic_validator=issue,
        )
    )
    return owner, run_id


@pytest.mark.asyncio
async def test_regenerate_cancels_flagged_run_and_admits_next_attempt(
    db_session, monkeypatch
) -> None:
    import document.shared_lesson.realization_source as realization_source

    owner, run_id = await _flagged_run(db_session)
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None and run.status == "failed_recoverable"

    calls: list[str] = []

    async def fake_ensure(session, *, owner_user_id, path_lesson_id):
        calls.append(path_lesson_id)
        return SimpleNamespace(id="replacement-run", status="queued")

    monkeypatch.setattr(realization_source, "ensure_shared_document_run", fake_ensure)
    result = await post_shared_document_regenerate(
        run_id, current_user=SimpleNamespace(id=owner), session=db_session
    )

    assert result["replaced_run_id"] == run_id
    assert result["run_id"] == "replacement-run"
    assert len(calls) == 1
    await db_session.refresh(run)
    assert run.status == "cancelled"


@pytest.mark.asyncio
async def test_regenerate_refuses_active_or_foreign_runs(db_session) -> None:
    from test_shared_qa_runtime import _seed_run, _source_and_document

    source, _document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix="regen-active")

    with pytest.raises(HTTPException) as active:
        await post_shared_document_regenerate(
            run_id, current_user=SimpleNamespace(id=owner), session=db_session
        )
    assert active.value.status_code == 409

    with pytest.raises(HTTPException) as foreign:
        await post_shared_document_regenerate(
            run_id, current_user=SimpleNamespace(id="someone-else"), session=db_session
        )
    assert foreign.value.status_code == 404

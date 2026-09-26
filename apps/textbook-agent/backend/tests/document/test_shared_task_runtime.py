from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from curriculum.lesson_sourcebook.models import LessonSourcebook, SourcebookEntry
from curriculum.shared_task_authoring import (
    ApprovedItemSnapshot,
    approved_item_snapshot_hash,
)
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import task_runtime
from document.shared_lesson.runtime import TeachingPlanSource
from infra.authoring import AuthoringProviderCall, AuthoringProviderTerminalError
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import LeaseLostError


def _source() -> TeachingPlanSource:
    plan = TeachingPlan(
        contract_version=2,
        learner_title="A shared task lesson",
        arc="Explain and check one idea",
        starting_state=["Learner has a question"],
        target_state=["Learner can identify the idea"],
        teaching_plan_id="shared-task-runtime-plan",
        revision=4,
        approval_status="approved",
        sections=[
            TeachingPlanSection(
                slot_id="check",
                display_title="Check",
                specific_purpose="Check the idea.",
                entry_state=["Learner has a question"],
                must_establish=["The idea is clear"],
                avoid_repeating=[],
                bridge_from_previous=None,
                exit_state=["Learner can identify the idea"],
                blocks=[
                    TeachingPlanBlock(
                        id="check-block",
                        position=0,
                        intent="Check the idea",
                        brief="Ask the learner to choose the correct idea.",
                        evidence="Learner selects the correct idea.",
                        sourcebook_needs=["definition"],
                        sourcebook_refs=["source-a"],
                        source_question_ids=["item-a"],
                        task_mode="assessment",
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="the idea",
                            purpose="Check understanding",
                            expected_evidence="Learner selects the correct idea.",
                            difficulty="guided",
                        ),
                    )
                ],
            )
        ],
    )
    digest = teaching_plan_content_hash(plan)
    snapshot = ApprovedItemSnapshot(
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision or 0,
        teaching_plan_hash=digest,
        items={
            "item-a": {
                "id": "item-a",
                "card_id": "card-a",
                "stem": "Approved question",
                "options": [{"key": "A", "text": "Correct"}],
                "correct_key": "A",
                "diagnoses": {},
            }
        },
    ).model_dump(mode="json")
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision or 0,
        status="approved",
        preparation_hash="p" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-25T00:00:00Z",
        approved_at="2026-09-25T00:00:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
        approved_item_snapshot=snapshot,
        approved_item_snapshot_hash=approved_item_snapshot_hash(
            ApprovedItemSnapshot.model_validate(snapshot)
        ),
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision or 0,
        content_hash=digest,
    )


def _sourcebook(source: TeachingPlanSource) -> LessonSourcebook:
    return LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=[
            SourcebookEntry(
                id="source-a",
                type="definition",
                purpose="Support the task.",
                content={"text": "The approved fact."},
                provenance_refs=["fact:1"],
            )
        ],
    )


def _snapshot(source: TeachingPlanSource) -> ApprovedItemSnapshot:
    return ApprovedItemSnapshot.model_validate(source.revision_record.approved_item_snapshot)


def _provider_task(prompt: str = "Choose the correct idea.") -> dict[str, Any]:
    return {
        "tasks": [
            {
                "prompt": prompt,
                "response": {
                    "type": "single_choice",
                    "options": [
                        {"id": "a", "text": "Correct"},
                        {"id": "b", "text": "Other"},
                    ],
                },
                "evaluation": {"type": "exact_match", "correct_option_id": "a"},
                "feedback": {"correct": "Good."},
                "expected_evidence": "Learner selects the correct idea.",
                "difficulty": "guided",
            }
        ]
    }


class _Provider:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class _Session:
    async def commit(self) -> None:
        return None


@pytest.fixture
def runtime_mocks(monkeypatch):
    source = _source()
    sourcebook = _sourcebook(source)
    snapshot = _snapshot(source)
    sourcebook_hash = content_hash(sourcebook.model_dump(mode="json"))
    item = SimpleNamespace(
        id="shared-task-item",
        run_id="shared-task-run",
        item_key=task_runtime.TASK_ITEM_KEY,
        stage=task_runtime.TASK_STAGE,
        input_hash=task_runtime._task_input_hash(
            source,
            sourcebook_hash,
            approved_item_snapshot_hash(snapshot),
        ),
        definition_hash=task_runtime._definition_hash(),
        composition_identity=sourcebook_hash,
        lease_token=1,
        status="running",
        output_json=None,
        output_hash=None,
    )
    failures: list[Any] = []
    completed: list[Any] = []
    checkpoints: list[Any] = []
    events: list[Any] = []

    async def claim(*_args, **_kwargs):
        return item

    async def load_checkpoint(*_args, **_kwargs):
        return checkpoints[0] if checkpoints else None

    async def persist_checkpoint(*_args, **kwargs):
        checkpoints.append(SimpleNamespace(payload=kwargs["payload"]))

    async def complete(*_args, **kwargs):
        completed.append(kwargs)

    async def fail(*_args, **kwargs):
        failures.append(kwargs["failure"])

    async def append(*_args, **kwargs):
        events.append(kwargs)

    async def load_sourcebook(*_args, **_kwargs):
        return SimpleNamespace(sourcebook=sourcebook, sourcebook_output_hash=sourcebook_hash)

    async def load_item_run_id(*_args, **_kwargs):
        return item.run_id

    async def snapshot_loader(_session, _owner, requested_source, _identity):
        assert requested_source == source
        return snapshot

    monkeypatch.setattr(task_runtime, "claim_work_item", claim)
    monkeypatch.setattr(task_runtime, "load_compatible_checkpoint", load_checkpoint)
    monkeypatch.setattr(task_runtime, "persist_checkpoint", persist_checkpoint)
    monkeypatch.setattr(task_runtime, "complete_work_item", complete)
    monkeypatch.setattr(task_runtime, "fail_work_item", fail)
    monkeypatch.setattr(task_runtime, "append_event", append)
    monkeypatch.setattr(task_runtime, "load_verified_sourcebook_input", load_sourcebook)
    monkeypatch.setattr(task_runtime, "_load_item_run_id", load_item_run_id)

    return SimpleNamespace(
        source=source,
        sourcebook=sourcebook,
        snapshot=snapshot,
        item=item,
        sourcebook_hash=sourcebook_hash,
        snapshot_hash=approved_item_snapshot_hash(snapshot),
        failures=failures,
        events=events,
        completed=completed,
        checkpoints=checkpoints,
        snapshot_loader=snapshot_loader,
        source_verifier=lambda _session, requested: requested,
    )


def _job(mocks, provider) -> task_runtime.SharedTaskWorkItemJob:
    return task_runtime.SharedTaskWorkItemJob(
        session=_Session(),
        work_item_id=mocks.item.id,
        worker_id="worker-1",
        source=mocks.source,
        owner_user_id="owner-1",
        approved_item_snapshot_loader=mocks.snapshot_loader,
        provider=provider,
        source_verifier=mocks.source_verifier,
    )


@pytest.mark.asyncio
async def test_executes_admitted_task_and_fences_output(runtime_mocks):
    provider = _Provider(_provider_task())

    outcome = await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert outcome.tasks is not None
    assert [task.id for task in outcome.tasks] == ["task-check-block"]
    assert len(provider.calls) == 1
    assert runtime_mocks.failures == []
    assert runtime_mocks.completed[0]["output_hash"] == content_hash(
        runtime_mocks.completed[0]["output_json"]
    )


@pytest.mark.asyncio
async def test_invalid_provider_response_is_bounded_and_recoverable(runtime_mocks):
    provider = _Provider({"tasks": []}, _provider_task("Repaired task."))

    outcome = await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert outcome.tasks is not None
    assert outcome.tasks[0].prompt == "Repaired task."
    assert len(provider.calls) == 2
    assert runtime_mocks.failures == []


@pytest.mark.asyncio
async def test_repair_exhaustion_persists_only_redacted_validation_diagnostics(runtime_mocks):
    sensitive_values = (
        "PRIVATE_LEARNER_RESPONSE",
        "PRIVATE_APPROVED_TEXT",
        "secret-api-key-value",
    )
    malformed = {
        "tasks": [
            {
                "prompt": sensitive_values[0],
                "response": {
                    "type": "single_choice",
                    "options": [{"id": sensitive_values[1], "text": sensitive_values[2]}],
                },
                "evaluation": {
                    "type": "exact_match",
                    "correct_option_id": sensitive_values[1],
                },
                "expected_evidence": "Learner selects the correct idea.",
                "difficulty": "guided",
            }
        ]
    }
    provider = _Provider(malformed, malformed)

    outcome = await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert outcome.error_code == "shared_task_invalid_output"
    assert len(provider.calls) == 2
    assert len(runtime_mocks.events) == 1
    event = runtime_mocks.events[0]
    assert event["event_type"] == "shared_task_validation_failed"
    assert event["error_code"] == "REPAIR_EXHAUSTED"
    diagnostics = str(event["safe_payload"])
    assert "validation_paths" in diagnostics
    assert "tasks" in diagnostics
    assert all(value not in diagnostics for value in sensitive_values)
    assert "message" not in event["safe_payload"]
    assert runtime_mocks.failures[0].error_code == "shared_task_invalid_output"
    assert runtime_mocks.failures[0].recovery_action == "retry"


@pytest.mark.asyncio
async def test_stale_sourcebook_fails_before_completion(runtime_mocks, monkeypatch):
    calls = 0

    async def changing_sourcebook(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        sourcebook = runtime_mocks.sourcebook.model_copy(
            update={
                "entries": [
                    runtime_mocks.sourcebook.entries[0].model_copy(update={"purpose": "Changed"})
                ]
            }
        )
        return SimpleNamespace(
            sourcebook=sourcebook,
            sourcebook_output_hash=content_hash(sourcebook.model_dump(mode="json")),
        )

    monkeypatch.setattr(task_runtime, "load_verified_sourcebook_input", changing_sourcebook)
    outcome = await task_runtime.execute_shared_task_work_item(
        _job(runtime_mocks, _Provider(_provider_task()))
    )

    assert calls == 1
    assert outcome.error_code == "shared_task_source_conflict"
    assert runtime_mocks.completed == []
    assert runtime_mocks.failures[0].recovery_action == "none"


@pytest.mark.asyncio
async def test_tampered_snapshot_is_rejected_before_claim(runtime_mocks, monkeypatch):
    tampered = runtime_mocks.snapshot.model_copy(
        update={
            "items": {
                "item-a": {
                    **runtime_mocks.snapshot.items["item-a"],
                    "stem": "Tampered",
                }
            }
        }
    )

    async def tampered_loader(*_args, **_kwargs):
        return tampered

    monkeypatch.setattr(runtime_mocks, "snapshot_loader", tampered_loader)
    provider = _Provider(_provider_task())

    with pytest.raises(task_runtime.SharedTaskSourceConflict):
        await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert provider.calls == []
    assert runtime_mocks.failures == []


@pytest.mark.asyncio
async def test_checkpoint_mismatch_is_terminal_and_skips_provider(runtime_mocks):
    runtime_mocks.checkpoints.append(SimpleNamespace(payload={"kind": "stale"}))
    provider = _Provider(_provider_task())

    outcome = await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert outcome.error_code == "shared_task_checkpoint_integrity"
    assert provider.calls == []
    assert runtime_mocks.failures[0].recovery_action == "none"


@pytest.mark.asyncio
async def test_lease_loss_is_not_reclassified_and_ready_siblings_are_untouched(
    runtime_mocks, monkeypatch
):
    async def stale_complete(*_args, **_kwargs):
        raise LeaseLostError("newer worker owns the fence")

    monkeypatch.setattr(task_runtime, "complete_work_item", stale_complete)
    provider = _Provider(_provider_task())

    with pytest.raises(LeaseLostError):
        await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert runtime_mocks.failures == []
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_provider_authentication_failure_is_terminal(runtime_mocks):
    provider = _Provider(AuthoringProviderTerminalError("authentication", "API key rejected"))

    outcome = await task_runtime.execute_shared_task_work_item(_job(runtime_mocks, provider))

    assert outcome.error_code == "shared_task_provider_terminal"
    assert runtime_mocks.failures[0].recovery_action == "none"
    assert len(provider.calls) == 1

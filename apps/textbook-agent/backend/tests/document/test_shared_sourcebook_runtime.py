from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from curriculum.lesson_sourcebook import LessonSourcebook, SourcebookEntry
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import sourcebook_runtime
from document.shared_lesson.runtime import TeachingPlanSource
from infra.authoring import AuthoringProviderCall, AuthoringProviderTerminalError
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import LeaseLostError, SourceIdentity


def _source() -> TeachingPlanSource:
    plan = TeachingPlan(
        contract_version=2,
        learner_title="A sourcebook lesson",
        arc="Build one stable explanation",
        starting_state=["Learner has a question"],
        target_state=["Learner can explain the idea"],
        teaching_plan_id="sourcebook-runtime-plan",
        revision=2,
        approval_status="approved",
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                display_title="Explain",
                specific_purpose="Establish the idea.",
                entry_state=["Learner has a question"],
                must_establish=["The idea is clear"],
                avoid_repeating=[],
                bridge_from_previous=None,
                exit_state=["Learner can explain the idea"],
                blocks=[
                    TeachingPlanBlock(
                        id="explain-block",
                        position=0,
                        intent="Explain the idea",
                        brief="Explain the idea clearly.",
                        evidence="Learner explains the idea.",
                        sourcebook_needs=["definition"],
                        sourcebook_refs=["definition-main"],
                    )
                ],
            )
        ],
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash="p" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-25T00:00:00Z",
        approved_at="2026-09-25T00:00:00Z",
        reviewed_by="teacher",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )


def _source_with_empty_sourcebook() -> TeachingPlanSource:
    source = _source()
    original_section = source.plan.sections[0]
    original_block = original_section.blocks[0]
    block = original_block.model_copy(
        update={"sourcebook_needs": [], "sourcebook_refs": []}
    )
    section = original_section.model_copy(update={"blocks": [block]})
    plan = source.plan.model_copy(update={"sections": [section]})
    digest = teaching_plan_content_hash(plan)
    record = source.revision_record.model_copy(
        update={"content_hash": digest, "plan": plan.model_dump(mode="json")}
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=source.id,
        revision=source.revision,
        content_hash=digest,
    )


def _source_with_unbound_sourcebook_need() -> TeachingPlanSource:
    source = _source()
    original_section = source.plan.sections[0]
    original_block = original_section.blocks[0]
    block = original_block.model_copy(update={"sourcebook_refs": []})
    section = original_section.model_copy(update={"blocks": [block]})
    plan = source.plan.model_copy(update={"sections": [section]})
    digest = teaching_plan_content_hash(plan)
    record = source.revision_record.model_copy(
        update={"content_hash": digest, "plan": plan.model_dump(mode="json")}
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=source.id,
        revision=source.revision,
        content_hash=digest,
    )


def _item(source: TeachingPlanSource) -> SimpleNamespace:
    return SimpleNamespace(
        id="sourcebook-item",
        run_id="sourcebook-run",
        item_key=sourcebook_runtime.SOURCEBOOK_ITEM_KEY,
        stage=sourcebook_runtime.SOURCEBOOK_STAGE,
        input_hash=sourcebook_runtime._sourcebook_input_hash(source),
        definition_hash=sourcebook_runtime._definition_hash(),
        composition_identity=None,
        lease_token=1,
        status="running",
        output_json=None,
        output_hash=None,
    )


def _payload() -> dict[str, Any]:
    return {
        "entries": [
            {
                "approved_ref_id": "definition-main",
                "type": "definition",
                "purpose": "Define the idea.",
                "content": {"text": "A stable definition."},
                "provenance_refs": ["fact:definition-main"],
            }
        ]
    }


class _Provider:
    def __init__(self, response: Any):
        self.response = response
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class _Session:
    async def commit(self) -> None:
        return None


@pytest.fixture
def runtime_mocks(monkeypatch):
    item: SimpleNamespace | None = None
    failures: list[Any] = []
    completed: list[Any] = []

    async def claim(*_args, **_kwargs):
        assert item is not None
        return item

    async def load_checkpoint(*_args, **_kwargs):
        return None

    async def persist_checkpoint(*_args, **_kwargs):
        return None

    async def complete(*_args, **kwargs):
        completed.append(kwargs)

    async def fail(*_args, **kwargs):
        failures.append(kwargs["failure"])

    def _set_item(value):
        nonlocal item
        item = value

    monkeypatch.setattr(sourcebook_runtime, "claim_work_item", claim)
    monkeypatch.setattr(sourcebook_runtime, "load_compatible_checkpoint", load_checkpoint)
    monkeypatch.setattr(sourcebook_runtime, "persist_checkpoint", persist_checkpoint)
    monkeypatch.setattr(sourcebook_runtime, "complete_work_item", complete)
    monkeypatch.setattr(sourcebook_runtime, "fail_work_item", fail)
    return SimpleNamespace(
        set_item=lambda value: _set_item(value), failures=failures, completed=completed
    )


@pytest.mark.asyncio
async def test_executes_admitted_sourcebook_with_source_verification_and_fenced_commit(
    runtime_mocks,
):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider(_payload())
    verified_calls: list[SourceIdentity] = []

    async def verifier(_session, requested):
        verified_calls.append(requested)
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-1",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.sourcebook is not None
    assert outcome.sourcebook.teaching_plan_hash == source.content_hash
    assert len(provider.calls) == 1
    assert len(verified_calls) == 3
    assert runtime_mocks.completed[0]["output_hash"] == content_hash(
        runtime_mocks.completed[0]["output_json"]
    )
    assert runtime_mocks.failures == []


@pytest.mark.asyncio
async def test_invalid_provider_output_is_recoverable_and_uses_bounded_repair(
    runtime_mocks,
):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider({"entries": []})

    async def verifier(_session, requested):
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-1",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.error_code == "sourcebook_invalid_output"
    assert runtime_mocks.failures[0].error_class == "provider_output"
    assert runtime_mocks.failures[0].recovery_action == "retry"
    assert len(provider.calls) == 2
    assert runtime_mocks.completed == []


@pytest.mark.asyncio
async def test_authentication_failure_is_terminal_without_semantic_fallback(runtime_mocks):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider(AuthoringProviderTerminalError("authentication", "API key rejected"))

    async def verifier(_session, requested):
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-1",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.error_code == "sourcebook_provider_terminal"
    assert runtime_mocks.failures[0].recovery_action == "none"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_empty_approved_sourcebook_completes_fenced_item_without_provider_call(
    runtime_mocks,
):
    source = _source_with_empty_sourcebook()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider({"entries": []})

    async def verifier(_session, requested):
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-empty",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.sourcebook is not None
    assert outcome.sourcebook.entries == []
    assert outcome.error_code is None
    assert provider.calls == []
    assert runtime_mocks.failures == []
    output = runtime_mocks.completed[0]["output_json"]
    assert output["teaching_plan_id"] == source.id
    assert output["teaching_plan_revision"] == source.revision
    assert output["teaching_plan_hash"] == source.content_hash
    assert output["entries"] == []
    assert runtime_mocks.completed[0]["output_hash"] == content_hash(output)


@pytest.mark.asyncio
async def test_unbound_sourcebook_need_fails_closed_without_provider_call(runtime_mocks):
    source = _source_with_unbound_sourcebook_need()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider({"entries": []})

    async def verifier(_session, requested):
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-unbound",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.error_code == "sourcebook_plan_contract"
    assert runtime_mocks.failures[0].error_class == "unsupported_contract"
    assert runtime_mocks.failures[0].recovery_action == "none"
    assert runtime_mocks.completed == []
    assert provider.calls == []


@pytest.mark.asyncio
async def test_source_verifier_mismatch_stops_before_provider_and_rejects_source(runtime_mocks):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider(_payload())
    other = SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision + 1,
        source_hash=source.content_hash,
    )

    async def verifier(_session, _requested):
        return other

    with pytest.raises(sourcebook_runtime.SourcebookSourceConflict):
        await sourcebook_runtime.execute_sourcebook_work_item(
            sourcebook_runtime.SourcebookWorkItemJob(
                session=object(),
                work_item_id=item.id,
                worker_id="worker-1",
                source=source,
                provider=provider,
                source_verifier=verifier,
            )
        )
    assert provider.calls == []
    assert runtime_mocks.failures == []


@pytest.mark.asyncio
async def test_source_change_after_provider_is_terminal_before_commit(runtime_mocks):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider(_payload())
    replacement = SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash="f" * 64,
    )
    calls = 0

    async def verifier(_session, requested):
        nonlocal calls
        calls += 1
        return replacement if calls == 3 else requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=_Session(),
            work_item_id=item.id,
            worker_id="worker-1",
            source=source,
            provider=provider,
            source_verifier=verifier,
        )
    )

    assert outcome.error_code == "sourcebook_source_conflict"
    assert len(provider.calls) == 1
    assert runtime_mocks.completed == []
    assert runtime_mocks.failures[0].error_class == "source_conflict"


@pytest.mark.asyncio
async def test_stale_fence_is_rejected_and_not_reclassified_as_provider_failure(
    runtime_mocks, monkeypatch
):
    source = _source()
    item = _item(source)
    runtime_mocks.set_item(item)
    provider = _Provider(_payload())

    async def verifier(_session, requested):
        return requested

    async def stale_complete(*_args, **_kwargs):
        raise LeaseLostError("newer worker owns the fence")

    monkeypatch.setattr(sourcebook_runtime, "complete_work_item", stale_complete)
    with pytest.raises(LeaseLostError):
        await sourcebook_runtime.execute_sourcebook_work_item(
            sourcebook_runtime.SourcebookWorkItemJob(
                session=_Session(),
                work_item_id=item.id,
                worker_id="worker-1",
                source=source,
                provider=provider,
                source_verifier=verifier,
            )
        )
    assert runtime_mocks.failures == []


@pytest.mark.asyncio
async def test_ready_item_is_preserved_without_provider_call(runtime_mocks):
    source = _source()
    provider = _Provider(_payload())
    output = LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=[
            SourcebookEntry(
                id="definition-main",
                type="definition",
                purpose="Define the idea.",
                content={"text": "A stable definition."},
                provenance_refs=["fact:definition-main"],
            )
        ],
    ).model_dump(mode="json")
    persisted = _item(source)
    persisted.status = "ready"
    persisted.output_json = output
    persisted.output_hash = content_hash(output)
    run = SimpleNamespace(
        run_type="shared_document",
        owner_user_id="owner-1",
        source_artifact_type="teaching_plan",
        source_artifact_id=source.id,
        source_revision=source.revision,
        source_hash=source.content_hash,
    )

    class Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            return persisted if self.calls == 1 else run

    async def verifier(_session, requested):
        return requested

    outcome = await sourcebook_runtime.execute_sourcebook_work_item(
        sourcebook_runtime.SourcebookWorkItemJob(
            session=Session(),
            work_item_id=persisted.id,
            worker_id="worker-1",
            source=source,
            provider=provider,
            source_verifier=verifier,
            status="ready",
        )
    )
    assert outcome.preserved_ready is True
    assert provider.calls == []

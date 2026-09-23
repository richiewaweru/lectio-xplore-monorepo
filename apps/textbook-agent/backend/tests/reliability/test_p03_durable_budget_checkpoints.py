"""P03 scaffolding: durable call budget, checkpoints, Learn fencing (G09–G15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel, UserModel
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from document.composer import DocumentComposerError, compose_document_plan
from document.writer import DocumentWriterError, write_document_primitive
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProviderCall,
    AuthoringRequest,
    AuthoringTransportError,
)
from infra.authoring.engine import AuthoringRegistry
from infra.execution.call_budget import (
    BudgetExhaustedError,
    CallBudgetLedger,
)
from infra.execution.checkpoints import (
    CheckpointCompatibility,
    CheckpointStore,
    IncompatibleCheckpointError,
    content_hash,
)
from infra.execution.error_policy import classify_provider_error, honor_retry_after
from infra.execution.leases import ResumeDecision
from infra.execution.resource_limits import ResourceLimitError, ResourceLimits
from learn.generation.fencing import (
    LearnCancelledError,
    LearnFenceError,
    assert_learn_commit_allowed,
    cancel_learn_execution,
    claim_learn_execution,
    commit_learn_checkpoint,
    empty_learn_execution_meta,
    write_learn_execution,
)


class FakeProvider:
    """Scripted provider with optional crash injection around dispatch."""

    def __init__(self, *script: Any) -> None:
        self.script = list(script)
        self.dispatches = 0
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        if not self.script:
            raise AssertionError("fake provider exhausted")
        step = self.script.pop(0)
        if step == "crash_before_call":
            # Simulate crash after reserve, before HTTP dispatch.
            raise _CrashBeforeCall()
        self.dispatches += 1
        if step == "crash_after_call":
            # Dispatch happened; commit did not.
            raise _CrashAfterCall()
        if isinstance(step, BaseException):
            raise step
        return step


class _CrashBeforeCall(RuntimeError):
    pass


class _CrashAfterCall(RuntimeError):
    pass


def _noop(*_a: Any, **_k: Any) -> list[Any]:
    return []


def _definition() -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id="p03-demo",
        native_path="document",
        modes=("generate",),
        instructions="Return a tiny payload.",
        payload_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "text"],
            "properties": {
                "kind": {"const": "paragraph"},
                "text": {"type": "string", "minLength": 1},
            },
        },
        required_inputs=("brief",),
        validator_refs=("p03.ok",),
        definition_hash="p03-def",
    )


def _request(work_order_id: str = "wi-p03") -> AuthoringRequest:
    return AuthoringRequest(
        work_order_id=work_order_id,
        definition=_definition(),
        scoped_request={"stage": "p03"},
        inputs={"brief": "Explain light."},
        teaching_revision=1,
        source_identities=("b1",),
        mode="generate",
    )


def _plan() -> TeachingPlan:
    return TeachingPlan(
        arc="P03",
        teaching_plan_id="tp-p03",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                blocks=[
                    TeachingPlanBlock(
                        id="b1",
                        position=0,
                        intent="explain",
                        brief="Explain why leaves need light.",
                        evidence="Learner names light as energy source.",
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_g11_call_budget_caps_nested_repairs_and_survives_resume() -> None:
    ledger = CallBudgetLedger()
    provider = FakeProvider(
        {"kind": "paragraph", "text": ""},  # invalid → repair
        {"kind": "paragraph", "text": ""},  # invalid → repair
        {"kind": "paragraph", "text": ""},  # would be 4th — must not dispatch
        {"kind": "paragraph", "text": "ok"},
    )
    engine = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("p03.ok", _noop),
        provider=provider,
        max_repair_attempts=5,  # soft cap higher than durable budget
        max_transport_attempts=1,
        budget_ledger=ledger,
        max_provider_calls=3,
    )

    with pytest.raises(AuthoringEngineError) as caught:
        await engine.execute(_request("wi-budget"))
    assert caught.value.code in {"REPAIR_EXHAUSTED", "BUDGET_EXHAUSTED", "INVALID_PAYLOAD"}
    assert provider.dispatches <= 3

    # Resume must not reset the counter.
    resumed = ledger.get_or_create("wi-budget", max_calls=3)
    assert resumed.consumed == 3
    with pytest.raises(BudgetExhaustedError):
        resumed.reserve()
    assert provider.dispatches <= 3


@pytest.mark.asyncio
async def test_g09_g11_crash_injection_before_after_commit() -> None:
    ledger = CallBudgetLedger()
    store = CheckpointStore()
    compat = CheckpointCompatibility(
        teaching_revision=1,
        input_hash=content_hash({"brief": "Explain light."}),
        definition_hash="p03-def",
        composition_identity="wi-crash",
    )

    # --- crash before call: reservation becomes ambiguous; no exact-once claim ---
    provider = FakeProvider("crash_before_call", {"kind": "paragraph", "text": "after resume"})
    engine = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("p03.ok", _noop),
        provider=provider,
        budget_ledger=ledger,
        max_provider_calls=3,
        max_repair_attempts=0,
        max_transport_attempts=1,
    )
    store.begin("node:wi-crash", compatibility=compat)
    with pytest.raises(_CrashBeforeCall):
        await engine.execute(_request("wi-crash"))
    budget = ledger.get_or_create("wi-crash")
    assert budget.consumed >= 1
    assert budget.ambiguous_count >= 1
    assert provider.dispatches == 0
    amb = store.mark_ambiguous("node:wi-crash")
    assert amb is not None and amb.status == "ambiguous"
    decision = store.decide_resume("node:wi-crash", compatibility=compat)
    assert decision == ResumeDecision.RETRY_ABANDONED  # not SKIP_READY / exactly-once

    # --- crash after call before commit ---
    provider2 = FakeProvider("crash_after_call")
    engine2 = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("p03.ok", _noop),
        provider=provider2,
        budget_ledger=ledger,
        max_provider_calls=3,
        max_repair_attempts=0,
        max_transport_attempts=1,
    )
    with pytest.raises(_CrashAfterCall):
        await engine2.execute(_request("wi-crash"))
    budget = ledger.get_or_create("wi-crash")
    assert provider2.dispatches == 1
    assert budget.dispatched_count + budget.ambiguous_count >= 2

    # --- successful commit then crash-after-commit reuse ---
    provider3 = FakeProvider({"kind": "paragraph", "text": "committed text"})
    engine3 = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("p03.ok", _noop),
        provider=provider3,
        budget_ledger=ledger,
        max_provider_calls=3,
        max_repair_attempts=0,
        max_transport_attempts=1,
    )
    result = await engine3.execute(_request("wi-crash"))
    committed = store.commit(
        "node:wi-crash",
        payload=result.payload,
        compatibility=compat,
    )
    before_hash = committed.content_hash
    assert store.decide_resume("node:wi-crash", compatibility=compat) == ResumeDecision.SKIP_READY

    # Resume: no new dispatch when checkpoint ready.
    prior_dispatches = provider3.dispatches
    reused = store.get("node:wi-crash")
    assert reused is not None and reused.payload == result.payload
    again = store.commit(
        "node:wi-crash",
        payload=result.payload,
        compatibility=compat,
    )
    assert again.content_hash == before_hash
    assert provider3.dispatches == prior_dispatches


@pytest.mark.asyncio
async def test_g10_selective_recovery_skips_ready_sibling() -> None:
    store = CheckpointStore()
    ledger = CallBudgetLedger()
    compat_a = CheckpointCompatibility(1, content_hash("a"), "def", composition_identity="a")
    compat_b = CheckpointCompatibility(1, content_hash("b"), "def", composition_identity="b")
    store.commit("node:a", payload={"id": "a", "text": "done"}, compatibility=compat_a)
    store.begin("node:b", compatibility=compat_b)

    assert store.decide_resume("node:a", compatibility=compat_a) == ResumeDecision.SKIP_READY
    assert store.decide_resume("node:b", compatibility=compat_b) == ResumeDecision.RETRY_ABANDONED

    provider = FakeProvider({"kind": "paragraph", "text": "only b"})
    node = await write_document_primitive(
        kind="paragraph",
        brief="Write about leaf light.",
        teaching_block={"id": "b", "brief": "Write about leaf light."},
        lesson_context={"teaching_plan_revision": 1},
        provider=provider,
        work_order_id="b",
        budget_ledger=ledger,
        checkpoint_store=store,
        node_id="node-b",
    )
    assert node["text"] == "only b"
    assert provider.dispatches == 1
    # Sibling A unchanged.
    ready_a = store.get("node:a")
    assert ready_a is not None
    assert ready_a.payload == {"id": "a", "text": "done"}


@pytest.mark.asyncio
async def test_document_quality_failure_repairs_in_engine_and_only_then_commits() -> None:
    brief = "Explain why leaves need light."
    provider = FakeProvider(
        {"kind": "paragraph", "text": brief},
        {"kind": "paragraph", "text": "Light supplies energy for photosynthesis."},
    )
    ledger = CallBudgetLedger()
    store = CheckpointStore()
    node = await write_document_primitive(
        kind="paragraph",
        brief=brief,
        teaching_block={"id": "quality-block", "brief": brief},
        provider=provider,
        work_order_id="node-quality-repair",
        budget_ledger=ledger,
        checkpoint_store=store,
    )

    assert node["text"] == "Light supplies energy for photosynthesis."
    assert [call.is_repair for call in provider.calls] == [False, True]
    budget = ledger.get_or_create("node-quality-repair")
    assert budget.consumed == budget.dispatched_count == 2
    checkpoint = store.get("node:node-quality-repair")
    assert checkpoint is not None and checkpoint.status == "ready"


@pytest.mark.asyncio
async def test_document_quality_repair_exhaustion_never_commits_ready_checkpoint() -> None:
    brief = "Explain why leaves need light."
    provider = FakeProvider(
        {"kind": "paragraph", "text": brief},
        {"kind": "paragraph", "text": brief},
        {"kind": "paragraph", "text": brief},
    )
    store = CheckpointStore()
    with pytest.raises(DocumentWriterError) as caught:
        await write_document_primitive(
            kind="paragraph",
            brief=brief,
            teaching_block={"id": "quality-block", "brief": brief},
            provider=provider,
            work_order_id="node-quality-exhausted",
            checkpoint_store=store,
        )
    assert caught.value.code == "REPAIR_EXHAUSTED"
    assert len(provider.calls) == 3
    checkpoint = store.get("node:node-quality-exhausted")
    assert checkpoint is not None and checkpoint.status != "ready"


def test_g10_media_assembly_export_selective_recovery() -> None:
    from infra.execution.checkpoints import selective_recovery_keys

    all_keys = {
        "composition:plan",
        "node:n1",
        "interaction:i1",
        "media:m1",
        "assembly:doc",
        "export:pdf",
    }
    ready = {
        "composition:plan",
        "node:n1",
        "interaction:i1",
        "media:m1",
    }
    # Media failed after siblings ready: rerun media + downstream only.
    must = selective_recovery_keys(
        failed_stage="media",
        ready_keys=ready - {"media:m1"},
        all_keys=all_keys,
    )
    assert "media:m1" in must
    assert "assembly:doc" in must
    assert "export:pdf" in must
    assert "node:n1" not in must
    assert "composition:plan" not in must
    assert "interaction:i1" not in must

    # Assembly failure leaves upstream ready siblings untouched.
    must_asm = selective_recovery_keys(
        failed_stage="assembly",
        ready_keys=ready | {"media:m1"},
        all_keys=all_keys,
    )
    assert must_asm == {"assembly:doc", "export:pdf"}


@pytest.mark.asyncio
async def test_g12_error_policy_retry_after_and_deadline() -> None:
    classified = classify_provider_error(
        RuntimeError("rate limit — Retry-After: 2"),
        status_code=429,
    )
    assert classified.retryable is True
    assert classified.error_class == "retryable_rate_limit"
    assert classified.retry_after_seconds == 2.0

    permanent = classify_provider_error(RuntimeError("invalid api key"), status_code=401)
    assert permanent.retryable is False

    stream = classify_provider_error(
        RuntimeError("stream interrupted after HTTP 200"),
        status_code=200,
    )
    assert stream.retryable is True

    deadline = datetime.now(UTC) + timedelta(seconds=30)
    delay = honor_retry_after(classified, deadline_at=deadline)
    assert delay == 2.0
    past = datetime.now(UTC) - timedelta(seconds=1)
    assert honor_retry_after(classified, deadline_at=past) is None


def test_g14_resource_limits_concurrency_and_cost() -> None:
    limits = ResourceLimits(max_concurrency=1, max_cost_units=10.0)
    limits.reserve_slot()
    with pytest.raises(ResourceLimitError):
        limits.reserve_slot()
    limits.release_slot()
    limits.reserve_cost(4.0)
    limits.reserve_cost(None)  # unknown usage stays explicit
    assert limits.unknown_usage is True
    with pytest.raises(ResourceLimitError):
        limits.reserve_cost(7.0)
    snap = limits.snapshot()
    restored = ResourceLimits.from_snapshot(snap)
    assert restored.reserved_cost_units == 4.0
    assert restored.unknown_usage is True


@pytest.mark.asyncio
async def test_g15_incompatible_checkpoint_and_budgeted_heuristic_fallback() -> None:
    store = CheckpointStore()
    compat = CheckpointCompatibility(1, "in", "def", schema_version=1)
    store.commit("composition:x", payload={"composition_mode": "llm"}, compatibility=compat)
    with pytest.raises(IncompatibleCheckpointError):
        store.decide_resume(
            "composition:x",
            compatibility=CheckpointCompatibility(1, "in", "def", schema_version=2),
        )

    ledger = CallBudgetLedger()
    invalid_semantic = {
        "nodes": [
            {
                "id": "unknown-node",
                "teaching_block_id": "unknown-block",
                "kind": "paragraph",
                "reason": "unknown block is a semantic defect",
            }
        ]
    }
    provider = FakeProvider(invalid_semantic, invalid_semantic)
    plan = await compose_document_plan(
        _plan(),
        path="learn",
        provider=provider,
        allow_heuristic_fallback=True,
        work_order_id="compose-fallback",
        budget_ledger=ledger,
        checkpoint_store=store,
    )
    assert plan.composition_mode == "heuristic_fallback"
    resumed = ledger.get_or_create("compose-fallback")
    assert resumed.fallback_declared is True
    assert resumed.consumed == 3
    assert provider.dispatches == 2

    # Exhausted budget is visible and never converted into another fallback.
    with pytest.raises(DocumentComposerError) as caught:
        await compose_document_plan(
            _plan(),
            path="learn",
            provider=FakeProvider(AuthoringTransportError("still down")),
            allow_heuristic_fallback=True,
            work_order_id="compose-fallback",
            budget_ledger=ledger,
        )
    assert caught.value.code == "BUDGET_EXHAUSTED"


@pytest.mark.asyncio
async def test_composer_transport_and_missing_provider_never_use_quality_fallback() -> None:
    ledger = CallBudgetLedger()
    provider = FakeProvider(AuthoringTransportError("composer down"))
    with pytest.raises(DocumentComposerError) as caught:
        await compose_document_plan(
            _plan(),
            path="learn",
            provider=provider,
            allow_heuristic_fallback=True,
            work_order_id="compose-transport",
            budget_ledger=ledger,
        )
    assert caught.value.code == "PROVIDER_TRANSPORT_EXHAUSTED"
    budget = ledger.get_or_create("compose-transport")
    assert budget.consumed == 1
    assert budget.fallback_declared is False

    with pytest.raises(DocumentComposerError) as missing:
        await compose_document_plan(
            _plan(),
            path="learn",
            provider=None,
            allow_heuristic_fallback=True,
            work_order_id="compose-no-provider",
            budget_ledger=ledger,
        )
    assert missing.value.code == "NO_PROVIDER"
    assert ledger.get_or_create("compose-no-provider").consumed == 0


@pytest.mark.asyncio
async def test_g13_learn_fencing_expired_and_cancel(db_session: AsyncSession) -> None:
    user = UserModel(id="u-p03", email="u-p03@example.invalid", name="p03")
    db_session.add(user)
    gid = "learn-fence-1"
    generation = GenerationModel(
        id=gid,
        user_id=user.id,
        subject="science",
        context="fence",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(generation)
    await db_session.flush()

    lease = await claim_learn_execution(db_session, generation_id=gid, worker_id="w1")
    assert lease is not None

    # Competing worker cannot claim while lease is fresh.
    assert await claim_learn_execution(db_session, generation_id=gid, worker_id="w2") is None

    # Expire heartbeat → reclaim.
    generation = await db_session.get(GenerationModel, gid)
    assert generation is not None
    execution = empty_learn_execution_meta()
    execution.update(
        {
            "worker_id": "w1",
            "lease_token": lease.lease_token,
            "heartbeat_at": (datetime.now(UTC) - timedelta(seconds=500)).isoformat().replace(
                "+00:00", "Z"
            ),
            "lease_seconds": 90,
            "status": "running",
        }
    )
    write_learn_execution(generation, execution)
    await db_session.flush()

    with pytest.raises(LearnFenceError):
        assert_learn_commit_allowed(
            execution, worker_id="w1", lease_token=lease.lease_token
        )

    lease2 = await claim_learn_execution(db_session, generation_id=gid, worker_id="w2")
    assert lease2 is not None and lease2.worker_id == "w2"

    await commit_learn_checkpoint(
        db_session,
        generation_id=gid,
        worker_id="w2",
        lease_token=lease2.lease_token,
        checkpoint_key="composition",
        checkpoint_payload={"content_hash": "abc", "payload": {"ok": True}},
    )
    # Stale w1 cannot commit after reclaim.
    with pytest.raises(LearnFenceError):
        await commit_learn_checkpoint(
            db_session,
            generation_id=gid,
            worker_id="w1",
            lease_token=lease.lease_token,
            checkpoint_key="composition",
            checkpoint_payload={"content_hash": "evil", "payload": {"ok": False}},
        )

    await cancel_learn_execution(db_session, generation_id=gid)
    with pytest.raises(LearnCancelledError):
        assert_learn_commit_allowed(
            empty_learn_execution_meta() | {"cancelled": True, "status": "cancelled"},
            worker_id="w2",
            lease_token=lease2.lease_token,
        )
    assert await claim_learn_execution(db_session, generation_id=gid, worker_id="w3") is None

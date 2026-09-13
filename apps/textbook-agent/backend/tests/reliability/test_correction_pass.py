"""Correction-pass regressions and durability proofs (C01–C04 / T-shaped)."""

from __future__ import annotations

from typing import Any

import pytest

from document.writer import write_document_primitive
from infra.authoring import AuthoringDefinition, AuthoringProviderCall, AuthoringRegistry
from infra.authoring.engine import AuthoringEngine
from infra.execution.call_budget import BudgetExhaustedError, CallBudgetLedger
from infra.execution.checkpoints import (
    CheckpointCompatibility,
    CheckpointStore,
    IncompatibleCheckpointError,
    content_hash,
)
from learn.generation.native_production import _assert_unique_node_ids


class CountingProvider:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.dispatches = 0
        self.payload = payload or {"kind": "paragraph", "text": "Stable sentence."}

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.dispatches += 1
        return dict(self.payload)


def _authoring_engine(
    provider: CountingProvider, ledger: CallBudgetLedger | None = None
) -> AuthoringEngine:
    return AuthoringEngine(
        registry=AuthoringRegistry().with_validator(
            "document.writer_schema", lambda *_a, **_k: []
        ),
        provider=provider,
        max_repair_attempts=0,
        max_transport_attempts=1,
        budget_ledger=ledger,
    )


async def _seed_learn_generation(
    db_session,
    *,
    user_id: str,
    email: str,
    generation_id: str,
    name: str = "Corr",
):
    """Insert UserModel + GenerationModel with empty learn_execution meta."""
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import empty_learn_execution_meta

    user = UserModel(
        id=user_id,
        email=email,
        name=name,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id=generation_id,
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    return gen


def _paragraph_definition() -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id="document.paragraph",
        native_path="document",
        modes=("generate",),
        instructions="Write a short paragraph.",
        payload_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "text"],
            "properties": {
                "kind": {"const": "paragraph"},
                "text": {"type": "string", "minLength": 1},
            },
        },
    )


@pytest.mark.asyncio
async def test_c01_ready_payload_rejects_incompatible_inputs() -> None:
    """Writer must not return a ready checkpoint when compatibility diverged."""
    store = CheckpointStore()
    compat = CheckpointCompatibility(
        teaching_revision=1,
        input_hash=content_hash({"brief": "old"}),
        definition_hash="def-a",
        composition_identity="learn-node:b1:paragraph:0",
    )
    store.commit(
        "node:learn-node:b1:paragraph:0",
        payload={"id": "learn-node:b1:paragraph:0", "kind": "paragraph", "text": "Old"},
        compatibility=compat,
    )
    provider = CountingProvider({"kind": "paragraph", "text": "Fresh rewrite."})
    engine = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("document.writer_schema", lambda *_a, **_k: []),
        provider=provider,
        max_repair_attempts=0,
        max_transport_attempts=1,
    )
    # Monkeypatch definition hash path by forcing different brief/role into inputs.
    with pytest.raises(IncompatibleCheckpointError):
        await write_document_primitive(
            kind="paragraph",
            brief="new brief that changes input hash",
            teaching_block={"id": "b1", "intent": "explain", "brief": "new", "evidence": ""},
            lesson_context={"teaching_plan_revision": 1, "objective": "obj"},
            teaching_block_id="b1",
            role="core",
            reason="changed",
            neighbour_summaries=[{"kind": "paragraph"}],
            provider=provider,
            engine=engine,
            work_order_id="learn-node:b1:paragraph:0",
            node_id="learn-node:b1:paragraph:0",
            checkpoint_store=store,
            terminology=["stomata"],
            allowed_facts=["plants need light"],
        )
    assert provider.dispatches == 0


def test_c03_unique_node_ids_reject_collisions() -> None:
    with pytest.raises(ValueError, match="duplicate learn node id"):
        _assert_unique_node_ids(
            [
                {"id": "block:paragraph", "kind": "paragraph"},
                {"id": "block:figure", "kind": "figure"},
                {"id": "block:paragraph", "kind": "paragraph"},
            ]
        )


def test_c03_indexed_ids_are_unique_for_repeated_kinds() -> None:
    ids = [
        f"learn-node:b1:paragraph:{i}" if kind == "paragraph" else f"learn-node:b1:{kind}:{i}"
        for i, kind in enumerate(["paragraph", "figure", "paragraph", "callout"])
    ]
    nodes = [{"id": nid, "kind": nid.split(":")[2]} for nid in ids]
    _assert_unique_node_ids(nodes)
    assert len(set(ids)) == 4


@pytest.mark.asyncio
async def test_c01_compatible_ready_reuse_skips_provider() -> None:
    store = CheckpointStore()
    teaching_block = {"id": "b1", "intent": "explain", "brief": "Brief", "evidence": "Ev"}
    lesson_context = {"teaching_plan_revision": 1, "objective": "Learn light"}
    # Mirror writer definition hash by writing once first.
    provider = CountingProvider({"kind": "paragraph", "text": "First write."})
    engine = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("document.writer_schema", lambda *_a, **_k: []),
        provider=provider,
        max_repair_attempts=0,
        max_transport_attempts=1,
        budget_ledger=CallBudgetLedger(),
    )
    first = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=provider,
        engine=engine,
        work_order_id="learn-node:b1:paragraph:0",
        node_id="learn-node:b1:paragraph:0",
        checkpoint_store=store,
    )
    assert first["text"] == "First write."
    assert provider.dispatches == 1
    second = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=provider,
        engine=engine,
        work_order_id="learn-node:b1:paragraph:0",
        node_id="learn-node:b1:paragraph:0",
        checkpoint_store=store,
    )
    assert second["text"] == "First write."
    assert provider.dispatches == 1


@pytest.mark.asyncio
async def test_c02_heartbeat_renews_lease_metadata(db_session, db_session_factory) -> None:
    """Heartbeat loop must update heartbeat_at while ownership remains valid."""
    import asyncio
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import (
        claim_learn_execution,
        empty_learn_execution_meta,
        learn_execution_from_generation,
    )
    from learn.generation.reliability_persist import learn_heartbeat_loop

    user = UserModel(
        id="corr-user",
        email="corr@example.com",
        name="Corr",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-hb",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()

    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="corr-worker"
    )
    assert lease is not None
    await db_session.commit()
    before = learn_execution_from_generation(
        await db_session.get(GenerationModel, gen.id)
    )["heartbeat_at"]

    stop = asyncio.Event()
    task = asyncio.create_task(
        learn_heartbeat_loop(
            generation_id=gen.id,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            interval_seconds=0.05,
            stop_event=stop,
            session_factory=db_session_factory,
        )
    )
    await asyncio.sleep(0.2)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)

    row = await db_session.get(GenerationModel, gen.id)
    await db_session.refresh(row)
    after = learn_execution_from_generation(row)["heartbeat_at"]
    assert after is not None
    assert after >= before


@pytest.mark.asyncio
async def test_c01_second_session_sees_committed_budget(db_session, db_session_factory) -> None:
    """Independent session must observe reserved budget after durable persist."""
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import (
        claim_learn_execution,
        empty_learn_execution_meta,
    )
    from learn.generation.reliability_persist import persist_learn_reliability_state

    user = UserModel(
        id="corr-user-2",
        email="corr2@example.com",
        name="Corr2",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-budget",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="corr-worker-2"
    )
    assert lease is not None
    await db_session.commit()

    ledger = CallBudgetLedger()
    budget = ledger.get_or_create("learn-node:b1:paragraph:0", max_calls=3)
    attempt = budget.reserve()
    ledger.persist(budget)
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        renew_heartbeat=True,
        session_factory=db_session_factory,
    )

    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        stored = dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
        assert "learn-node:b1:paragraph:0" in stored
        attempts = stored["learn-node:b1:paragraph:0"]["attempts"]
        assert attempts[-1]["attempt"] == attempt
        assert attempts[-1]["status"] == "reserved"


@pytest.mark.asyncio
async def test_c02_expired_worker_cannot_persist(db_session, db_session_factory) -> None:
    from datetime import UTC, datetime, timedelta

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import (
        LearnFenceError,
        claim_learn_execution,
        empty_learn_execution_meta,
        learn_execution_from_generation,
        write_learn_execution,
    )
    from learn.generation.reliability_persist import persist_learn_reliability_state

    user = UserModel(
        id="corr-user-3",
        email="corr3@example.com",
        name="Corr3",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-expire",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    lease_a = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="worker-a"
    )
    assert lease_a is not None
    # Age heartbeat so lease A is expired, then B claims.
    row = await db_session.get(GenerationModel, gen.id)
    execution = learn_execution_from_generation(row)
    aged = (datetime.now(UTC) - timedelta(seconds=200)).replace(microsecond=0)
    execution["heartbeat_at"] = aged.isoformat().replace("+00:00", "Z")
    execution["lease_seconds"] = 90
    write_learn_execution(row, execution)
    await db_session.commit()

    lease_b = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="worker-b"
    )
    assert lease_b is not None
    await db_session.commit()

    with pytest.raises(LearnFenceError):
        await persist_learn_reliability_state(
            generation_id=gen.id,
            budget_ledger=CallBudgetLedger(),
            worker_id=lease_a.worker_id,
            lease_token=lease_a.lease_token,
            renew_heartbeat=True,
            session_factory=db_session_factory,
        )


@pytest.mark.asyncio
async def test_c02_cancel_blocks_durable_persist(db_session, db_session_factory) -> None:
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import (
        LearnCancelledError,
        cancel_learn_execution,
        claim_learn_execution,
        empty_learn_execution_meta,
    )
    from learn.generation.reliability_persist import persist_learn_reliability_state

    user = UserModel(
        id="corr-user-4",
        email="corr4@example.com",
        name="Corr4",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-cancel",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="worker-c"
    )
    assert lease is not None
    await db_session.commit()
    await cancel_learn_execution(db_session, generation_id=gen.id)
    await db_session.commit()

    with pytest.raises(LearnCancelledError):
        await persist_learn_reliability_state(
            generation_id=gen.id,
            budget_ledger=CallBudgetLedger(),
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            renew_heartbeat=True,
            session_factory=db_session_factory,
        )


@pytest.mark.asyncio
async def test_t01_fresh_process_reuses_committed_checkpoint(db_session, db_session_factory) -> None:
    """T01-shaped: committed item survives 'restart' via DB snapshot reload."""
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import claim_learn_execution, empty_learn_execution_meta
    from learn.generation.reliability_persist import persist_learn_reliability_state

    user = UserModel(
        id="corr-user-t01",
        email="t01@example.com",
        name="T01",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-t01",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t01-worker"
    )
    assert lease is not None
    await db_session.commit()

    store = CheckpointStore()
    ledger = CallBudgetLedger()
    teaching_block = {"id": "b1", "intent": "explain", "brief": "Brief", "evidence": "Ev"}
    lesson_context = {"teaching_plan_revision": 1, "objective": "obj"}
    provider = CountingProvider({"kind": "paragraph", "text": "Committed once."})
    engine = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("document.writer_schema", lambda *_a, **_k: []),
        provider=provider,
        max_repair_attempts=0,
        max_transport_attempts=1,
        budget_ledger=ledger,
    )
    first = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=provider,
        engine=engine,
        work_order_id="learn-node:b1:paragraph:0",
        node_id="learn-node:b1:paragraph:0",
        checkpoint_store=store,
        budget_ledger=ledger,
    )
    assert first["text"] == "Committed once."
    assert provider.dispatches == 1
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        checkpoint_store=store,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    # Fresh process: new stores hydrated from committed DB row.
    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        restored = CheckpointStore.from_snapshot(
            dict((row.chunked_state_json or {}).get("checkpoint_store") or {})
        )
        restored_ledger = CallBudgetLedger()
        restored_ledger.import_state(
            dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
        )

    provider2 = CountingProvider({"kind": "paragraph", "text": "Should not run."})
    engine2 = AuthoringEngine(
        registry=AuthoringRegistry().with_validator("document.writer_schema", lambda *_a, **_k: []),
        provider=provider2,
        max_repair_attempts=0,
        max_transport_attempts=1,
        budget_ledger=restored_ledger,
    )
    second = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=provider2,
        engine=engine2,
        work_order_id="learn-node:b1:paragraph:0",
        node_id="learn-node:b1:paragraph:0",
        checkpoint_store=restored,
        budget_ledger=restored_ledger,
    )
    assert second["text"] == "Committed once."
    assert provider2.dispatches == 0


@pytest.mark.asyncio
async def test_t05_renewals_keep_ownership_past_short_lease(
    db_session, db_session_factory
) -> None:
    """T05-shaped: renewals keep ownership longer than lease_seconds without raising timeout."""
    import asyncio
    from datetime import UTC, datetime

    from core.database.models import GenerationModel, UserModel
    from learn.generation.fencing import (
        claim_learn_execution,
        empty_learn_execution_meta,
        learn_execution_from_generation,
    )
    from learn.generation.reliability_persist import (
        learn_heartbeat_loop,
        persist_learn_reliability_state,
    )

    user = UserModel(
        id="corr-user-t05",
        email="t05@example.com",
        name="T05",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(user)
    await db_session.flush()
    gen = GenerationModel(
        id="learn-out-corr-t05",
        user_id=user.id,
        subject="Science",
        context="corr",
        status="queued",
        requested_template_id="lesson",
        requested_preset_id="standard",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        chunked_state_json={"learn_execution": empty_learn_execution_meta()},
    )
    db_session.add(gen)
    await db_session.commit()
    # Controllable lease duration (do not raise the production 90s default).
    lease = await claim_learn_execution(
        db_session,
        generation_id=gen.id,
        worker_id="t05-worker",
        lease_seconds=1,
    )
    assert lease is not None
    await db_session.commit()

    stop = asyncio.Event()
    task = asyncio.create_task(
        learn_heartbeat_loop(
            generation_id=gen.id,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            interval_seconds=0.15,
            stop_event=stop,
            session_factory=db_session_factory,
        )
    )
    # First renew immediately so we do not wait a full interval before the first beat.
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=CallBudgetLedger(),
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        renew_heartbeat=True,
        session_factory=db_session_factory,
    )
    await asyncio.sleep(1.6)  # exceeds lease_seconds=1 if heartbeats fail
    # Owner can still persist after > lease_seconds because heartbeats renewed.
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=CallBudgetLedger(),
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        renew_heartbeat=True,
        session_factory=db_session_factory,
    )
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)
    row = await db_session.get(GenerationModel, gen.id)
    await db_session.refresh(row)
    assert learn_execution_from_generation(row)["lease_seconds"] == 1
    assert learn_execution_from_generation(row)["heartbeat_at"] is not None

    # Without renewals the original 1s lease would be dead; takeover must fail.
    again = await claim_learn_execution(
        db_session,
        generation_id=gen.id,
        worker_id="t05-takeover",
    )
    assert again is None


@pytest.mark.asyncio
async def test_t02_ambiguous_reserve_survives_restore(
    db_session, db_session_factory
) -> None:
    """T02: reserved→persist→ambiguous; restored remaining respects ambiguous slots."""
    from core.database.models import GenerationModel
    from learn.generation.fencing import claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t02",
        email="t02@example.com",
        generation_id="learn-out-corr-t02",
        name="T02",
    )
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t02-worker"
    )
    assert lease is not None
    await db_session.commit()

    work_id = "learn-node:b1:paragraph:0"
    ledger = CallBudgetLedger()
    budget = ledger.get_or_create(work_id, max_calls=3)
    attempt = budget.reserve()
    ledger.persist(budget)
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    budget.mark_ambiguous(attempt)
    ledger.persist(budget)
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        restored = CallBudgetLedger()
        restored.import_state(
            dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
        )

    restored_budget = restored.get_or_create(work_id, max_calls=3)
    assert restored_budget.consumed == 1
    assert restored_budget.ambiguous_count == 1
    assert restored_budget.remaining == 2
    assert restored_budget.max_calls == 3

    # Fill remaining slots without ever exceeding max_calls=3.
    for _ in range(restored_budget.remaining):
        a = restored_budget.reserve()
        restored_budget.mark_dispatched(a)
        restored.persist(restored_budget)
    assert restored_budget.consumed == 3
    assert restored_budget.remaining == 0
    with pytest.raises(BudgetExhaustedError) as excinfo:
        restored_budget.reserve()
    assert excinfo.value.consumed == 3
    assert excinfo.value.max_calls == 3


@pytest.mark.asyncio
async def test_t03_exhausted_budget_is_durable_terminal(
    db_session, db_session_factory
) -> None:
    """T03: three reserves/dispatches persist; 4th reserve raises after restore."""
    from core.database.models import GenerationModel
    from learn.generation.fencing import claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t03",
        email="t03@example.com",
        generation_id="learn-out-corr-t03",
        name="T03",
    )
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t03-worker"
    )
    assert lease is not None
    await db_session.commit()

    work_id = "learn-node:b1:paragraph:0"
    ledger = CallBudgetLedger()
    budget = ledger.get_or_create(work_id, max_calls=3)
    for _ in range(3):
        attempt = budget.reserve()
        budget.mark_dispatched(attempt)
        ledger.persist(budget)
    assert budget.consumed == 3
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        restored = CallBudgetLedger()
        restored.import_state(
            dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
        )

    restored_budget = restored.get_or_create(work_id, max_calls=3)
    assert restored_budget.consumed == 3
    with pytest.raises(BudgetExhaustedError) as excinfo:
        restored_budget.reserve()
    assert excinfo.value.consumed == 3
    assert excinfo.value.max_calls == 3
    # Durable terminal: exhausted consumed remains 3 after failed reserve.
    assert restored_budget.consumed == 3


@pytest.mark.asyncio
async def test_t04_concurrent_claims_admit_one_owner(
    db_session, db_session_factory
) -> None:
    """T04: concurrent claim race → one owner; only that token can persist."""
    import asyncio

    from learn.generation.fencing import LearnFenceError, claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t04",
        email="t04@example.com",
        generation_id="learn-out-corr-t04",
        name="T04",
    )
    await db_session.commit()

    async def _claim(worker_id: str):
        async with db_session_factory() as session:
            lease = await claim_learn_execution(
                session, generation_id=gen.id, worker_id=worker_id
            )
            await session.commit()
            return lease

    first, second = await asyncio.gather(
        _claim("t04-worker-a"),
        _claim("t04-worker-b"),
    )
    winners = [lease for lease in (first, second) if lease is not None]
    losers = [lease for lease in (first, second) if lease is None]
    # Under row lock, exactly one claim succeeds while the lease is live.
    assert len(winners) == 1
    assert len(losers) == 1
    owner = winners[0]

    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=CallBudgetLedger(),
        worker_id=owner.worker_id,
        lease_token=owner.lease_token,
        renew_heartbeat=True,
        session_factory=db_session_factory,
    )
    # A fabricated competing token cannot persist under the live owner.
    with pytest.raises(LearnFenceError):
        await persist_learn_reliability_state(
            generation_id=gen.id,
            budget_ledger=CallBudgetLedger(),
            worker_id="t04-impostor",
            lease_token=owner.lease_token + 99,
            renew_heartbeat=True,
            session_factory=db_session_factory,
        )


@pytest.mark.asyncio
async def test_t06_expired_lease_allows_takeover_and_blocks_old_persist(
    db_session, db_session_factory
) -> None:
    """T06: lease_seconds=1 without renew → B claims; A's persist raises LearnFenceError."""
    import asyncio

    from learn.generation.fencing import LearnFenceError, claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t06",
        email="t06@example.com",
        generation_id="learn-out-corr-t06",
        name="T06",
    )
    lease_a = await claim_learn_execution(
        db_session,
        generation_id=gen.id,
        worker_id="t06-worker-a",
        lease_seconds=1,
    )
    assert lease_a is not None
    await db_session.commit()

    await asyncio.sleep(1.2)  # exceed lease_seconds=1 without renew

    lease_b = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t06-worker-b"
    )
    assert lease_b is not None
    await db_session.commit()

    with pytest.raises(LearnFenceError):
        await persist_learn_reliability_state(
            generation_id=gen.id,
            budget_ledger=CallBudgetLedger(),
            worker_id=lease_a.worker_id,
            lease_token=lease_a.lease_token,
            renew_heartbeat=True,
            session_factory=db_session_factory,
        )


@pytest.mark.asyncio
async def test_t07_cancel_blocks_persist_and_dispatch(
    db_session, db_session_factory
) -> None:
    """T07: cancel raises LearnCancelledError on persist and assert_learn_dispatch_allowed."""
    from core.database.models import GenerationModel
    from learn.generation.fencing import (
        LearnCancelledError,
        assert_learn_dispatch_allowed,
        cancel_learn_execution,
        claim_learn_execution,
        learn_execution_from_generation,
    )
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t07",
        email="t07@example.com",
        generation_id="learn-out-corr-t07",
        name="T07",
    )
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t07-worker"
    )
    assert lease is not None
    await db_session.commit()
    await cancel_learn_execution(db_session, generation_id=gen.id)
    await db_session.commit()

    with pytest.raises(LearnCancelledError):
        await persist_learn_reliability_state(
            generation_id=gen.id,
            budget_ledger=CallBudgetLedger(),
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            renew_heartbeat=True,
            session_factory=db_session_factory,
        )

    row = await db_session.get(GenerationModel, gen.id)
    await db_session.refresh(row)
    execution = learn_execution_from_generation(row)
    with pytest.raises(LearnCancelledError):
        assert_learn_dispatch_allowed(execution)


@pytest.mark.asyncio
async def test_t08_incompatible_ready_reuse_does_not_reset_budget() -> None:
    """T08: incompatible ready reuse raises; ledger consumed stays unchanged."""
    store = CheckpointStore()
    ledger = CallBudgetLedger()
    work_id = "learn-node:b1:paragraph:0"
    budget = ledger.get_or_create(work_id, max_calls=3)
    attempt = budget.reserve()
    budget.mark_dispatched(attempt)
    ledger.persist(budget)
    consumed_before = budget.consumed

    compat = CheckpointCompatibility(
        teaching_revision=1,
        input_hash=content_hash({"brief": "old", "role": "core", "reason": "orig"}),
        definition_hash="def-a",
        composition_identity=work_id,
    )
    store.commit(
        f"node:{work_id}",
        payload={"id": work_id, "kind": "paragraph", "text": "Old"},
        compatibility=compat,
    )
    provider = CountingProvider({"kind": "paragraph", "text": "Fresh rewrite."})
    engine = _authoring_engine(provider, ledger)

    with pytest.raises(IncompatibleCheckpointError):
        await write_document_primitive(
            kind="paragraph",
            brief="new brief that changes input hash",
            teaching_block={"id": "b1", "intent": "explain", "brief": "new", "evidence": ""},
            lesson_context={"teaching_plan_revision": 1, "objective": "obj"},
            teaching_block_id="b1",
            role="core",
            reason="changed",
            neighbour_summaries=[{"kind": "paragraph"}],
            provider=provider,
            engine=engine,
            work_order_id=work_id,
            node_id=work_id,
            checkpoint_store=store,
            budget_ledger=ledger,
            terminology=["stomata"],
            allowed_facts=["plants need light"],
        )
    assert provider.dispatches == 0
    # No silent budget reset when reuse is rejected.
    after = ledger.get_or_create(work_id, max_calls=3)
    assert after.consumed == consumed_before == 1


def test_t09_indexed_node_ids_unique_and_collision_raises() -> None:
    """T09: Paragraph→Figure→Paragraph→Callout indexed ids unique; collision still raises."""
    kinds = ["paragraph", "figure", "paragraph", "callout"]
    ids = [f"learn-node:b1:{kind}:{i}" for i, kind in enumerate(kinds)]
    nodes = [{"id": nid, "kind": kinds[i]} for i, nid in enumerate(ids)]
    _assert_unique_node_ids(nodes)
    assert len(set(ids)) == 4

    with pytest.raises(ValueError, match="duplicate learn node id"):
        _assert_unique_node_ids(
            [
                {"id": "learn-node:b1:paragraph:0", "kind": "paragraph"},
                {"id": "learn-node:b1:figure:1", "kind": "figure"},
                {"id": "learn-node:b1:paragraph:0", "kind": "paragraph"},
            ]
        )


@pytest.mark.asyncio
async def test_t10_partial_ready_resume_reuses_one_item(
    db_session, db_session_factory
) -> None:
    """T10: two work items; after restore ready item skips provider, other still needs work."""
    from core.database.models import GenerationModel
    from learn.generation.fencing import claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t10",
        email="t10@example.com",
        generation_id="learn-out-corr-t10",
        name="T10",
    )
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t10-worker"
    )
    assert lease is not None
    await db_session.commit()

    store = CheckpointStore()
    ledger = CallBudgetLedger()
    teaching_block = {"id": "b1", "intent": "explain", "brief": "Brief", "evidence": "Ev"}
    lesson_context = {"teaching_plan_revision": 1, "objective": "obj"}
    ready_id = "learn-node:b1:paragraph:0"
    pending_id = "learn-node:b1:paragraph:1"

    provider = CountingProvider({"kind": "paragraph", "text": "Ready item."})
    engine = _authoring_engine(provider, ledger)
    first = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=provider,
        engine=engine,
        work_order_id=ready_id,
        node_id=ready_id,
        checkpoint_store=store,
        budget_ledger=ledger,
    )
    assert first["text"] == "Ready item."
    assert provider.dispatches == 1
    # Second item not written yet — only budget slot may exist after restore as empty.
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=ledger,
        checkpoint_store=store,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        restored = CheckpointStore.from_snapshot(
            dict((row.chunked_state_json or {}).get("checkpoint_store") or {})
        )
        restored_ledger = CallBudgetLedger()
        restored_ledger.import_state(
            dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
        )

    reuse_provider = CountingProvider({"kind": "paragraph", "text": "Should not run."})
    reuse_engine = _authoring_engine(reuse_provider, restored_ledger)
    reused = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=reuse_provider,
        engine=reuse_engine,
        work_order_id=ready_id,
        node_id=ready_id,
        checkpoint_store=restored,
        budget_ledger=restored_ledger,
    )
    assert reused["text"] == "Ready item."
    assert reuse_provider.dispatches == 0

    pending_provider = CountingProvider({"kind": "paragraph", "text": "Pending item."})
    pending_engine = _authoring_engine(pending_provider, restored_ledger)
    pending = await write_document_primitive(
        kind="paragraph",
        brief="Brief",
        teaching_block=teaching_block,
        lesson_context=lesson_context,
        teaching_block_id="b1",
        provider=pending_provider,
        engine=pending_engine,
        work_order_id=pending_id,
        node_id=pending_id,
        checkpoint_store=restored,
        budget_ledger=restored_ledger,
    )
    assert pending["text"] == "Pending item."
    assert pending_provider.dispatches == 1


@pytest.mark.asyncio
async def test_t11_progress_events_survive_restart(
    db_session, db_session_factory
) -> None:
    """T11: progress_store snapshot + events persist; second session reads same events."""
    from core.database.models import GenerationModel
    from infra.execution.progress import ProgressStore
    from learn.generation.fencing import claim_learn_execution
    from learn.generation.reliability_persist import persist_learn_reliability_state

    gen = await _seed_learn_generation(
        db_session,
        user_id="corr-user-t11",
        email="t11@example.com",
        generation_id="learn-out-corr-t11",
        name="T11",
    )
    lease = await claim_learn_execution(
        db_session, generation_id=gen.id, worker_id="t11-worker"
    )
    assert lease is not None
    await db_session.commit()

    run_id = "realize-t11"
    progress = ProgressStore()
    progress.ensure_run(
        run_id,
        path="learn",
        owner_user_id="corr-user-t11",
        status="running",
        stage="writing",
        realization_revision=1,
        teaching_plan_revision=1,
    )
    progress.append_event(
        run_id,
        event_type="learn_production_started",
        path="learn",
        stage="writing",
        item_id=gen.id,
        attempt=1,
        payload={"phase": "start"},
    )
    progress.append_event(
        run_id,
        event_type="item_completed",
        path="learn",
        stage="writing",
        item_id="learn-node:b1:paragraph:0",
        attempt=1,
        payload={"phase": "done"},
    )
    await persist_learn_reliability_state(
        generation_id=gen.id,
        budget_ledger=CallBudgetLedger(),
        progress_store=progress,
        progress_run_id=run_id,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
        session_factory=db_session_factory,
    )

    # Fresh process / new session: hydrate progress from committed chunked_state_json.
    async with db_session_factory() as other:
        row = await other.get(GenerationModel, gen.id)
        assert row is not None
        raw = dict((row.chunked_state_json or {}).get("progress_store") or {})
        assert raw.get("run_id") == run_id
        events = list(raw.get("events") or [])
        assert len(events) == 2
        assert events[0]["event_type"] == "learn_production_started"
        assert events[1]["event_type"] == "item_completed"
        assert events[1]["item_id"] == "learn-node:b1:paragraph:0"

        restarted = ProgressStore()
        restarted.import_run_snapshot(raw)
        snap = restarted.snapshot(run_id)
        assert [e["event_type"] for e in snap["events"]] == [
            "learn_production_started",
            "item_completed",
        ]


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_second_connection_sees_reserved_budget_under_claim() -> None:
    """Postgres: second connection sees reserved budget while claim holder is live."""
    import os
    from datetime import UTC, datetime

    pytest.importorskip("asyncpg")
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    # Prefer env; else docker-compose db-dev defaults (textbook/textbook @ :5432).
    url = os.environ.get("POSTGRES_TEST_URL") or (
        "postgresql+asyncpg://textbook:textbook@127.0.0.1:5432/textbook_agent"
    )

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"postgres unreachable at {url}: {exc}")

    from core.database.models import Base, GenerationModel, UserModel
    from learn.generation.fencing import claim_learn_execution, empty_learn_execution_meta
    from learn.generation.reliability_persist import persist_learn_reliability_state

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        stamp = datetime.now(UTC).strftime("%H%M%S%f")
        gen_id = f"learn-out-corr-pg-{stamp}"
        user_id = f"corr-user-pg-{stamp}"

        async with factory() as production:
            user = UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="PG",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            production.add(user)
            await production.flush()
            gen = GenerationModel(
                id=gen_id,
                user_id=user.id,
                subject="Science",
                context="corr-pg",
                status="queued",
                requested_template_id="lesson",
                requested_preset_id="standard",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                chunked_state_json={"learn_execution": empty_learn_execution_meta()},
            )
            production.add(gen)
            await production.commit()

            lease = await claim_learn_execution(
                production, generation_id=gen_id, worker_id="pg-producer"
            )
            assert lease is not None
            await production.commit()

            ledger = CallBudgetLedger()
            budget = ledger.get_or_create("learn-node:b1:paragraph:0", max_calls=3)
            attempt = budget.reserve()
            ledger.persist(budget)
            await persist_learn_reliability_state(
                generation_id=gen_id,
                budget_ledger=ledger,
                worker_id=lease.worker_id,
                lease_token=lease.lease_token,
                renew_heartbeat=True,
                session_factory=factory,
            )

            # Second connection observes reserved budget while producer still holds claim.
            async with factory() as observer:
                row = await observer.get(GenerationModel, gen_id)
                assert row is not None
                stored = dict((row.chunked_state_json or {}).get("call_budget_ledger") or {})
                assert "learn-node:b1:paragraph:0" in stored
                attempts = stored["learn-node:b1:paragraph:0"]["attempts"]
                assert attempts[-1]["attempt"] == attempt
                assert attempts[-1]["status"] == "reserved"
                execution = dict((row.chunked_state_json or {}).get("learn_execution") or {})
                assert execution.get("worker_id") == "pg-producer"
    finally:
        await engine.dispose()

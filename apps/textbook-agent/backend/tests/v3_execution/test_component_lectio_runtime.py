"""Phases 05–08 runtime policy tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from v3_blueprint.planning.canonical_plan import build_canonical_execution_plan
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_execution.runtime.checkpoints import (
    CheckpointStore,
    GenerationControlState,
    resume_after_crash,
)
from v3_execution.runtime.failure_policy import (
    BudgetLedger,
    FailureClass,
    classify_failure,
    recovery_for,
    scoped_repair_keeps_siblings_ready,
)
from v3_execution.runtime.leases import LeaseLostError, LeaseStore
from v3_execution.runtime.lesson_document import assemble_lesson_document, reconnect_from_store
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject


def test_failure_classes_map_to_deterministic_recovery() -> None:
    ledger = BudgetLedger()
    cases = [
        (TimeoutError("timeout"), None, FailureClass.TRANSPORT_RETRYABLE, "retry"),
        (RuntimeError("rate limit"), 429, FailureClass.RATE_LIMITED, "retry"),
        (ValueError("malformed json output"), None, FailureClass.MODEL_OUTPUT_RETRYABLE, "retry"),
        (ValueError("lectio validation failed"), None, FailureClass.COMPONENT_REPAIRABLE, "repair"),
        (RuntimeError("visual render failed"), None, FailureClass.VISUAL_RETRYABLE, "retry"),
        (TypeError("NoneType"), None, FailureClass.TERMINAL_CODE_ERROR, "stop"),
    ]
    for exc, status, expected_class, expected_action in cases:
        failure = classify_failure(exc, block_id="b1", status_code=status)
        assert failure.failure_class == expected_class
        action = recovery_for(failure, ledger, sibling_block_ids=["b2"])
        assert action.action == expected_action


def test_scoped_repair_preserves_siblings() -> None:
    ready = scoped_repair_keeps_siblings_ready(
        failed_block_id="b2",
        ready_block_ids=["b1", "b2", "b3"],
    )
    assert ready == ["b1", "b3"]
    ledger = BudgetLedger()
    failure = classify_failure("invalid lectio payload", block_id="b2")
    action = recovery_for(failure, ledger, sibling_block_ids=["b1", "b3"])
    assert action.action == "repair"
    assert action.payload["preserve_siblings"] == ["b1", "b3"]
    # Second repair exhausted.
    action2 = recovery_for(failure, ledger, sibling_block_ids=["b1", "b3"])
    assert action2.action == "stop"


def test_checkpoints_resume_only_missing_and_idempotent() -> None:
    store = CheckpointStore(
        control=GenerationControlState(
            generation_id="gen-1",
            state="running",
            plan_revision=1,
            plan_hash="abc",
            desired_work=["b1", "b2", "b3", "b4"],
        )
    )
    store.mark_block_ready("b1", plan_revision=1, plan_hash="abc", payload={"content": {"x": 1}})
    store.mark_block_ready("b2", plan_revision=1, plan_hash="abc", payload={"content": {"x": 2}})
    store.mark_block_ready("b3", plan_revision=1, plan_hash="abc", payload={"content": {"x": 3}})
    # duplicate ready
    store.mark_block_ready("b1", plan_revision=1, plan_hash="abc", payload={"content": {"x": 1}})
    pending = resume_after_crash(store)
    assert pending == ["b4"]
    store.mark_block_ready("b4", plan_revision=1, plan_hash="abc", payload={"content": {"x": 4}})
    store.mark_terminal("complete")
    reconstructed = store.reconstruct()
    assert reconstructed["state"] == "complete"
    assert reconstructed["ready_blocks"] == ["b1", "b2", "b3", "b4"]
    assert resume_after_crash(store) == []


def test_leases_single_writer_and_late_write_rejected() -> None:
    store = LeaseStore(ttl_seconds=30)
    store.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lease = store.claim("gen-1")
    with pytest.raises(LeaseLostError):
        store.claim("gen-1")
    assert store.mutating_write("gen-1", lease.owner_token, payload={"a": 1})["ok"] is True
    # Expire and reclaim.
    store.now = store.now + timedelta(seconds=31)
    assert store.reclaim_expired() == ["gen-1"]
    with pytest.raises(LeaseLostError):
        store.mutating_write("gen-1", lease.owner_token, payload={"a": 2})
    new_lease = store.claim("gen-1")
    assert new_lease.owner_token != lease.owner_token


def test_lesson_document_partial_open_and_human_fence() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    canonical, _ = build_canonical_execution_plan(plan, generation_id="gen-doc")
    store = CheckpointStore(
        control=GenerationControlState(
            generation_id="gen-doc",
            state="running",
            plan_revision=canonical.plan_revision,
            plan_hash=canonical.plan_hash,
            desired_work=[block.block_id for block in canonical.blocks],
        )
    )
    first = canonical.blocks[0]
    store.mark_block_ready(
        first.block_id,
        plan_revision=canonical.plan_revision,
        plan_hash=canonical.plan_hash,
        payload={"content": {"ok": True}},
    )
    doc = assemble_lesson_document(canonical, store, title="Ratios", subject="Math")
    assert doc["version"] == 1
    assert doc["id"] == "gen-doc"
    assert doc["preset_id"] == "blue-classroom"
    assert first.block_id in doc["blocks"]
    from v3_execution.runtime.lesson_document import lesson_is_partial

    assert lesson_is_partial(canonical, store) is True
    # Human fence beats stale generator.
    fenced = assemble_lesson_document(
        canonical,
        store,
        title="Ratios",
        human_revision=2,
        generator_revision=1,
    )
    assert first.block_id not in fenced["blocks"]
    assert reconnect_from_store(store)["ready_blocks"] == [first.block_id]

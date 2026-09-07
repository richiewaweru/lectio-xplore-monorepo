"""Canonical Component Lectio pipeline (mocked writers) — Phases 09/10 path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from v3_blueprint.planning.canonical_plan import (
    CanonicalExecutionPlan,
    build_canonical_execution_plan,
)
from v3_blueprint.planning.models import IntentPlan, StructuralPlan, intent_plan_to_structural_plan
from v3_blueprint.planning.work_orders import ExactWorkOrder, compile_exact_work_orders
from v3_execution.runtime.checkpoints import (
    CheckpointStore,
    GenerationControlState,
    resume_after_crash,
)
from v3_execution.runtime.failure_policy import (
    BudgetLedger,
    classify_failure,
    recovery_for,
)
from v3_execution.runtime.leases import LeaseStore
from v3_execution.runtime.lesson_document import assemble_lesson_document


WriterFn = Callable[[ExactWorkOrder], dict[str, Any]]


def mock_writer(order: ExactWorkOrder) -> dict[str, Any]:
    """Deterministic mocked content/items/visual payload."""
    return {
        "content": {
            "component_id": order.locked_component_id,
            "purpose": order.purpose,
            "mock": True,
            "lane": order.lane,
        }
    }


@dataclass
class PipelineResult:
    generation_id: str
    intent: IntentPlan
    structural: StructuralPlan
    canonical: CanonicalExecutionPlan
    work_orders: list[ExactWorkOrder]
    store: CheckpointStore
    lease_token: str
    document: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)


def run_mocked_component_lectio_pipeline(
    intent: IntentPlan,
    *,
    title: str,
    generation_id: str | None = None,
    writer: WriterFn | None = None,
    inject_failures: dict[str, BaseException] | None = None,
) -> PipelineResult:
    """
    unit/intent → selection → work orders → mocked writers → validate/repair
    → checkpoints → lease-guarded writes → LessonDocument.
    Does not call V3 Studio.
    """
    gen_id = generation_id or str(uuid4())
    write = writer or mock_writer
    injections = inject_failures or {}
    events: list[dict[str, Any]] = []

    structural = intent_plan_to_structural_plan(intent)
    canonical, filled = build_canonical_execution_plan(
        structural,
        generation_id=gen_id,
        lesson_id=title,
    )
    orders = compile_exact_work_orders(canonical)
    desired = [order.block_id for order in orders]

    leases = LeaseStore(ttl_seconds=60)
    lease = leases.claim(gen_id)
    store = CheckpointStore(
        control=GenerationControlState(
            generation_id=gen_id,
            state="running",
            plan_revision=canonical.plan_revision,
            plan_hash=canonical.plan_hash,
            desired_work=desired,
        )
    )
    ledger = BudgetLedger()

    for order in orders:
        try:
            if order.block_id in injections:
                raise injections[order.block_id]
            leases.mutating_write(gen_id, lease.owner_token, payload={"block": order.block_id})
            payload = write(order)
            if payload.get("content", {}).get("component_id") != order.locked_component_id:
                raise ValueError("writer changed component_id")
            store.mark_block_ready(
                order.block_id,
                plan_revision=canonical.plan_revision,
                plan_hash=canonical.plan_hash,
                payload=payload,
            )
            events.append({"type": "block_ready", "block_id": order.block_id})
        except Exception as exc:  # noqa: BLE001
            failure = classify_failure(exc, block_id=order.block_id)
            ready_siblings = [
                block_id
                for block_id, checkpoint in store.blocks.items()
                if checkpoint.state == "ready"
            ]
            action = recovery_for(failure, ledger, sibling_block_ids=ready_siblings)
            events.append(
                {
                    "type": "failure",
                    "block_id": order.block_id,
                    "class": failure.failure_class.value,
                    "action": action.action,
                }
            )
            if action.action == "repair":
                # One scoped repair attempt with mock writer.
                payload = write(order)
                store.mark_block_ready(
                    order.block_id,
                    plan_revision=canonical.plan_revision,
                    plan_hash=canonical.plan_hash,
                    payload=payload,
                )
                events.append({"type": "block_repaired", "block_id": order.block_id})
            elif action.action == "retry":
                payload = write(order)
                store.mark_block_ready(
                    order.block_id,
                    plan_revision=canonical.plan_revision,
                    plan_hash=canonical.plan_hash,
                    payload=payload,
                )
                events.append({"type": "block_retried", "block_id": order.block_id})
            else:
                from v3_execution.runtime.checkpoints import BlockCheckpoint

                store.blocks[order.block_id] = BlockCheckpoint(
                    block_id=order.block_id,
                    plan_revision=canonical.plan_revision,
                    plan_hash=canonical.plan_hash,
                    state="failed",
                    last_error={"message": str(exc), "class": failure.failure_class.value},
                )

    # Crash-resume simulation: only missing work remains.
    pending = resume_after_crash(store)
    for block_id in pending:
        order = next(item for item in orders if item.block_id == block_id)
        payload = write(order)
        store.mark_block_ready(
            block_id,
            plan_revision=canonical.plan_revision,
            plan_hash=canonical.plan_hash,
            payload=payload,
        )
        events.append({"type": "resumed", "block_id": block_id})

    store.mark_terminal("complete")
    document = assemble_lesson_document(canonical, store, title=title)
    return PipelineResult(
        generation_id=gen_id,
        intent=intent,
        structural=filled,
        canonical=canonical,
        work_orders=orders,
        store=store,
        lease_token=lease.owner_token,
        document=document,
        events=events,
    )

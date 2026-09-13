"""Rewrite Learn production to admit before provider dispatch (P02 G07)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import admit_realization
from core.database.models import EditableLessonModel, GenerationModel
from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import AuthoringEngine, AuthoringProvider, LLMAuthoringProvider
from infra.authoring.capability_selector import ChooseFn
from infra.execution.call_budget import CallBudgetLedger
from infra.execution.checkpoints import CheckpointStore
from infra.execution.progress import default_progress_store
from learn.generation.fencing import (
    LEARN_EXECUTION_KEY,
    LearnCancelledError,
    assert_learn_commit_allowed,
    assert_learn_dispatch_allowed,
    claim_learn_execution,
    empty_learn_execution_meta,
    learn_execution_from_generation,
    write_learn_execution,
)
from learn.generation.native_production import (
    package_contract_hash,
    produce_learn_document_from_teaching_async,
    teaching_plan_content_hash,
)
from learn.generation.preparation_context import (
    LearnPreparationContext,
    learn_preparation_context_from_state,
)
from learn.publishing.publish_validation import validate_publishable_lesson_document
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _preparation_from_generation(
    generation: GenerationModel | None,
) -> LearnPreparationContext:
    """Load preparation only from GenerationModel.chunked_state_json."""
    prep_state: dict[str, Any] = {}
    if generation is not None:
        chunked = generation.chunked_state_json
        if isinstance(chunked, dict):
            prep_state = dict(chunked)
            packet = chunked.get("shared_preparation_packet")
            if isinstance(packet, dict):
                prep_state["shared_preparation_packet"] = packet
    return learn_preparation_context_from_state(prep_state)


async def _ready_result_from_existing(
    session: AsyncSession,
    *,
    realization,
    plan_hash: str,
    teaching_plan: TeachingPlan,
    policy_hash: str,
    pkg_hash: str,
) -> dict[str, Any] | None:
    """Return a replay payload when a completed Learn realization already exists."""
    output_id = str(realization.output_id or "")
    if realization.status != "ready" or not output_id:
        return None
    generation = await session.get(GenerationModel, output_id)
    if generation is None or not isinstance(generation.document_json, dict):
        return None
    document = dict(generation.document_json)
    editable = None
    # Prefer the editable lesson linked to this output when present.
    from sqlalchemy import select

    editable = await session.scalar(
        select(EditableLessonModel)
        .where(EditableLessonModel.source_generation_id == output_id)
        .order_by(EditableLessonModel.created_at.desc())
    )
    return {
        "status": "ready",
        "output_id": output_id,
        "editable_lesson_id": editable.id if editable is not None else None,
        "realization_id": realization.id,
        "realization_created": False,
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": int(teaching_plan.revision or 1),
        "selection_trace": (generation.chunked_state_json or {}).get("selection_trace")
        if isinstance(generation.chunked_state_json, dict)
        else {},
        "document": document,
        "content_hash": teaching_plan_content_hash(teaching_plan),
        "native_policy_hash": policy_hash,
        "package_contract_hash": pkg_hash,
        "replayed": True,
    }


async def produce_learn_from_approved_teaching(
    session: AsyncSession,
    *,
    teaching_plan: TeachingPlan,
    user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
    pack_id: str | None = None,
    title: str | None = None,
    subject: str = "science",
    available_asset_ids: Sequence[str] | None = None,
    approved_items: Sequence[Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    preparation_context: LearnPreparationContext | None = None,
    choose: ChooseFn | None = None,
    admission_request_key: str | None = None,
    worker_id: str | None = None,
    allow_heuristic_composition_fallback: bool | None = None,
) -> dict[str, Any]:
    """Admit Learn realization, then run LearnDocument v2 production.

    Provider/engine are required for real writing. When omitted, defaults to
    ``LLMAuthoringProvider`` so Unit production does not silently stub content.

    Ordering (P02 G07): allocate stable IDs + admit **before** provider calls so
    concurrent identical requests reuse the same realization instead of minting
    orphan generations.

    P03: claim a Learn execution lease before dispatch; cancelled runs cannot
    start new provider work.
    """
    _ = choose  # closed-selection choose is unused on the v2 compose path
    prep = preparation_context
    if prep is None:
        prep_generation = await session.get(GenerationModel, preparation_generation_id)
        prep = _preparation_from_generation(prep_generation)

    body = dict(policy) if policy is not None else default_learn_policy()
    _, policy_hash = policy_version_and_hash(body)
    pkg_hash = package_contract_hash()
    plan_hash = teaching_plan_content_hash(teaching_plan)
    heuristic_fallback = (
        bool(allow_heuristic_composition_fallback)
        if allow_heuristic_composition_fallback is not None
        else bool(body.get("allow_heuristic_composition_fallback", True))
    )

    # Admit first with a durable output_id (or reuse an existing admission).
    provisional_output_id = f"learn-out-{uuid.uuid4().hex[:12]}"
    realization, created = await admit_realization(
        session,
        path_lesson_id=path_lesson_id,
        path="learn",
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=plan_hash,
        preparation_generation_id=preparation_generation_id,
        pack_id=pack_id or preparation_generation_id,
        output_id=provisional_output_id,
        native_policy_hash=policy_hash,
        package_contract_hash=pkg_hash,
        admission_request_key=admission_request_key,
        admission_payload_hash=plan_hash,
    )
    if not created and realization.output_id:
        # Failed prior runs keep stale checkpoints that can trip input_hash
        # mismatches on resume. Mint a fresh output identity after failure.
        if str(realization.status) in {
            "failed",
            "failed_terminal",
            "failed_recoverable",
            "cancelled",
        }:
            output_id = provisional_output_id
            realization.output_id = output_id
            realization.status = "queued"
            realization.error_summary = None
        else:
            output_id = str(realization.output_id)
    else:
        output_id = provisional_output_id
        realization.output_id = output_id
    await session.flush()

    replay = await _ready_result_from_existing(
        session,
        realization=realization,
        plan_hash=plan_hash,
        teaching_plan=teaching_plan,
        policy_hash=policy_hash,
        pkg_hash=pkg_hash,
    )
    if replay is not None:
        return replay

    # Ensure generation row exists so Learn fencing can attach lease metadata.
    generation = await session.get(GenerationModel, output_id)
    if generation is None:
        generation = GenerationModel(
            id=output_id,
            user_id=user_id,
            subject=subject,
            context=title or teaching_plan.arc or "Learn native output",
            status="queued",
            requested_template_id="lesson",
            requested_preset_id="standard",
            pack_id=pack_id,
            created_at=_utcnow(),
            chunked_state_json={LEARN_EXECUTION_KEY: empty_learn_execution_meta()},
        )
        session.add(generation)
        await session.flush()

    execution = learn_execution_from_generation(generation)
    try:
        assert_learn_dispatch_allowed(execution)
    except LearnCancelledError:
        realization.status = "cancelled"
        await session.flush()
        raise

    owner = worker_id or f"learn-worker-{uuid.uuid4().hex[:8]}"
    lease = await claim_learn_execution(
        session, generation_id=output_id, worker_id=owner
    )
    if lease is None:
        # Re-check cancel / ownership.
        generation = await session.get(GenerationModel, output_id)
        assert generation is not None
        execution = learn_execution_from_generation(generation)
        assert_learn_dispatch_allowed(execution)
        raise LearnCancelledError("Learn execution could not be claimed")

    realization.status = "running"
    await session.flush()
    # Independent-session durable persist / heartbeat cannot see uncommitted rows.
    # Commit admission identity + lease before any cross-session write.
    await session.commit()
    realization = await session.get(type(realization), realization.id)
    assert realization is not None
    generation = await session.get(GenerationModel, output_id)
    assert generation is not None

    # Durable budgets / checkpoints / progress (P03–P04 product wiring).
    prior_state = dict(generation.chunked_state_json or {})
    budget_ledger = CallBudgetLedger()
    raw_ledger = prior_state.get("call_budget_ledger")
    if isinstance(raw_ledger, dict) and raw_ledger:
        budget_ledger.import_state(raw_ledger)

    checkpoint_store = CheckpointStore()
    raw_checkpoints = prior_state.get("checkpoint_store")
    if isinstance(raw_checkpoints, dict) and raw_checkpoints:
        try:
            checkpoint_store = CheckpointStore.from_snapshot(raw_checkpoints)
        except Exception:  # noqa: BLE001
            checkpoint_store = CheckpointStore()

    progress = default_progress_store
    raw_progress = prior_state.get("progress_store")
    if isinstance(raw_progress, dict) and raw_progress.get("run_id"):
        try:
            progress.import_run_snapshot(raw_progress)
        except Exception:
            logger.debug("learn progress snapshot restore skipped", exc_info=True)
    progress.ensure_run(
        realization.id,
        path="learn",
        owner_user_id=user_id,
        status="running",
        stage="running",
        realization_revision=int(realization.realization_revision or 1),
        teaching_plan_revision=int(teaching_plan.revision or 1),
    )
    progress.append_event(
        realization.id,
        event_type="learn_production_started",
        path="learn",
        stage="running",
        item_id=output_id,
        attempt=1,
    )

    from learn.generation.reliability_persist import (
        LEARN_HEARTBEAT_INTERVAL_SECONDS,
        learn_heartbeat_loop,
        persist_learn_reliability_state,
    )

    async def _durable_persist() -> None:
        await persist_learn_reliability_state(
            generation_id=output_id,
            budget_ledger=budget_ledger,
            checkpoint_store=checkpoint_store,
            progress_store=progress,
            progress_run_id=realization.id,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            renew_heartbeat=True,
        )

    # Commit restored/empty reliability state before expensive provider work.
    await _durable_persist()

    stop_heartbeat = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        learn_heartbeat_loop(
            generation_id=output_id,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            budget_ledger=budget_ledger,
            checkpoint_store=checkpoint_store,
            progress_store=progress,
            progress_run_id=realization.id,
            interval_seconds=LEARN_HEARTBEAT_INTERVAL_SECONDS,
            stop_event=stop_heartbeat,
        )
    )

    # Provider work happens after admission identity is durable.
    selected_provider = provider or LLMAuthoringProvider(node_name="v3_block_writer_fast")
    selected_engine = engine

    async def _on_item_committed(_item_id: str, _node: dict[str, Any]) -> None:
        await _durable_persist()

    try:
        production = await produce_learn_document_from_teaching_async(
            teaching_plan=teaching_plan,
            title=title,
            subject=subject,
            source_generation_id=output_id,
            lesson_id=output_id,
            provider=selected_provider,
            engine=selected_engine,
            preparation_context=prep,
            available_asset_ids=available_asset_ids,
            approved_items=approved_items,
            allow_heuristic_composition_fallback=heuristic_fallback,
            budget_ledger=budget_ledger,
            checkpoint_store=checkpoint_store,
            progress_store=progress,
            progress_run_id=realization.id,
            durable_persist_hook=_durable_persist,
            on_item_committed=_on_item_committed,
        )
    except Exception:
        stop_heartbeat.set()
        try:
            await asyncio.wait_for(heartbeat_task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            heartbeat_task.cancel()
        # Persist terminal failure state so UI does not remain running.
        try:
            generation = await session.get(GenerationModel, output_id)
            if generation is not None:
                execution = learn_execution_from_generation(generation)
                execution["status"] = "failed"
                # Drop ownership so a later resume can claim after crash/fail.
                execution["worker_id"] = None
                execution["heartbeat_at"] = None
                write_learn_execution(generation, execution)
                await session.commit()
                # Best-effort durable snapshot without ownership fence.
                await persist_learn_reliability_state(
                    generation_id=output_id,
                    budget_ledger=budget_ledger,
                    checkpoint_store=checkpoint_store,
                    progress_store=progress,
                    progress_run_id=realization.id,
                )
            progress.sync_from_db(
                realization.id,
                path="learn",
                owner_user_id=user_id,
                status="failed",
                realization_revision=int(realization.realization_revision or 1),
                teaching_plan_revision=int(teaching_plan.revision or 1),
                stage="failed",
            )
            realization.status = "failed"
            await session.commit()
        except Exception:
            logger.debug("learn failure persist skipped", exc_info=True)
        raise
    finally:
        stop_heartbeat.set()
        if not heartbeat_task.done():
            try:
                await asyncio.wait_for(heartbeat_task, timeout=2.0)
            except (TimeoutError, asyncio.CancelledError):
                heartbeat_task.cancel()

    document = dict(production["document"])
    document["id"] = output_id
    document["source_generation_id"] = output_id
    validate_publishable_lesson_document(document)

    plan_hash = str(production["teaching_plan_hash"])
    generation = await session.get(GenerationModel, output_id)
    assert generation is not None
    # Fenced commit: expired / cancelled workers cannot publish.
    execution = learn_execution_from_generation(generation)
    assert_learn_commit_allowed(
        execution, worker_id=lease.worker_id, lease_token=lease.lease_token
    )

    generation.status = "completed"
    composition_plan = production["composition_plan"]
    composition_mode = (
        composition_plan.composition_mode
        if hasattr(composition_plan, "composition_mode")
        else (composition_plan or {}).get("composition_mode")
        if isinstance(composition_plan, dict)
        else "llm"
    )
    generation.document_json = document
    generation.chunked_state_json = {
        **dict(generation.chunked_state_json or {}),
        "shared_preparation": False,
        "native_learn": True,
        "learn_document": True,
        "document_version": 2,
        "control": {"pipeline": "native_learn"},
        "preparation_generation_id": preparation_generation_id,
        "teaching_plan_id": teaching_plan.teaching_plan_id,
        "teaching_plan_revision": teaching_plan.revision,
        "teaching_plan_hash": plan_hash,
        "call_budget_ledger": budget_ledger.export_state(),
        "checkpoint_store": checkpoint_store.snapshot(),
        "progress_store": progress.snapshot(realization.id),
        "selection_trace": {
            "form_prompt": "learn_document_v2_compose_write",
            "composition_mode": composition_mode,
            "composition_plan": (
                composition_plan.model_dump(mode="json")
                if hasattr(composition_plan, "model_dump")
                else composition_plan
            ),
        },
        "form_prompt": "learn_document_v2_compose_write",
    }
    progress.sync_from_db(
        realization.id,
        path="learn",
        owner_user_id=user_id,
        status="ready",
        realization_revision=int(realization.realization_revision or 1),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        stage="ready",
    )
    progress.append_event(
        realization.id,
        event_type="learn_production_ready",
        path="learn",
        stage="ready",
        item_id=output_id,
        attempt=1,
        payload={"composition_mode": composition_mode},
    )
    # Keep lease meta after success.
    execution = learn_execution_from_generation(generation)
    execution["status"] = "ready"
    write_learn_execution(generation, execution)

    lesson_id = str(uuid.uuid4())
    now = _utcnow()
    editable = EditableLessonModel(
        id=lesson_id,
        user_id=user_id,
        source_generation_id=output_id,
        source_type="learn_document",
        title=str(document.get("title") or "Learn lesson"),
        class_label=None,
        document_json={
            **document,
            "id": lesson_id,
            "updated_at": now.isoformat() + "Z",
            "created_at": now.isoformat() + "Z",
        },
        created_at=now,
        updated_at=now,
    )
    session.add(editable)

    realization.status = "ready"
    realization.output_id = output_id
    realization.teaching_plan_hash = plan_hash
    await session.flush()

    return {
        "status": "ready",
        "output_id": output_id,
        "editable_lesson_id": lesson_id,
        "realization_id": realization.id,
        "realization_created": created,
        "teaching_plan_hash": plan_hash,
        "teaching_plan_revision": int(teaching_plan.revision or 1),
        "selection_trace": generation.chunked_state_json["selection_trace"],
        "document": document,
        "content_hash": teaching_plan_content_hash(teaching_plan),
        "native_policy_hash": policy_hash,
        "package_contract_hash": pkg_hash,
        "replayed": False,
    }


__all__ = ["produce_learn_from_approved_teaching"]

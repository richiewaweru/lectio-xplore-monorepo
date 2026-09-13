"""Rewrite Learn production to admit before provider dispatch (P02 G07)."""

from __future__ import annotations

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

    # Provider work happens after admission identity is durable.
    selected_provider = provider or LLMAuthoringProvider(node_name="v3_block_writer_fast")
    selected_engine = engine

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
    )
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

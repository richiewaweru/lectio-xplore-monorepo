"""Persist native Learn outputs from an approved shared teaching revision.

Production Learn generation uses the LearnDocument v2 document path:
compose (LLM) → write ordinary primitives (LLM) → interaction writer → assemble.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import admit_realization
from core.database.models import EditableLessonModel, GenerationModel
from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import AuthoringEngine, AuthoringProvider, LLMAuthoringProvider
from infra.authoring.capability_selector import ChooseFn
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
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
) -> dict[str, Any]:
    """Run LearnDocument v2 production and persist generation + editable draft.

    Provider/engine are required for real writing. When omitted, defaults to
    ``LLMAuthoringProvider`` so Unit production does not silently stub content.
    """
    _ = choose  # closed-selection choose is unused on the v2 compose path
    output_id = f"learn-out-{uuid.uuid4().hex[:12]}"
    prep = preparation_context
    if prep is None:
        prep_generation = await session.get(GenerationModel, preparation_generation_id)
        prep = _preparation_from_generation(prep_generation)

    body = dict(policy) if policy is not None else default_learn_policy()
    _, policy_hash = policy_version_and_hash(body)
    pkg_hash = package_contract_hash()

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
        allow_heuristic_composition_fallback=True,
    )
    document = dict(production["document"])
    document["id"] = output_id
    document["source_generation_id"] = output_id
    validate_publishable_lesson_document(document)

    plan_hash = str(production["teaching_plan_hash"])
    generation = GenerationModel(
        id=output_id,
        user_id=user_id,
        subject=subject,
        context=title or teaching_plan.arc or "Learn native output",
        status="completed",
        requested_template_id="lesson",
        requested_preset_id="standard",
        pack_id=pack_id,
        created_at=_utcnow(),
        document_json=document,
        chunked_state_json={
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
                "composition_plan": (
                    production["composition_plan"].model_dump(mode="json")
                    if hasattr(production["composition_plan"], "model_dump")
                    else production["composition_plan"]
                ),
            },
            "form_prompt": "learn_document_v2_compose_write",
        },
    )
    session.add(generation)

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

    realization, created = await admit_realization(
        session,
        path_lesson_id=path_lesson_id,
        path="learn",
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=plan_hash,
        preparation_generation_id=preparation_generation_id,
        pack_id=pack_id or preparation_generation_id,
        output_id=output_id,
        native_policy_hash=policy_hash,
        package_contract_hash=pkg_hash,
    )
    realization.status = "ready"
    realization.output_id = output_id
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
    }


__all__ = ["produce_learn_from_approved_teaching"]

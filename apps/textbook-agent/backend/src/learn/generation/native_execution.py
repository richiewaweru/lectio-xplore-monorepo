"""Persist native Learn outputs from an approved shared teaching revision.

Does not substitute prepared plans or bypass closed selection. Application
orchestration loads the shared teaching state and passes the accepted plan here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.realizations import admit_realization
from core.database.models import EditableLessonModel, GenerationModel
from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import AuthoringEngine, AuthoringProvider
from learn.generation.native_production import (
    build_closed_learn_production_async,
    teaching_plan_content_hash,
)
from learn.generation.preparation_context import (
    LearnPreparationContext,
    learn_preparation_context_from_state,
)
from learn.publishing.publish_validation import validate_publishable_lesson_document


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
) -> dict[str, Any]:
    """Run closed Learn production and persist generation + editable draft.

    Returns production artifacts plus realization linkage. Selection is never
    bypassed: ``build_closed_learn_production`` seals the snapshot first.
    """
    output_id = f"learn-out-{uuid.uuid4().hex[:12]}"
    prep = preparation_context
    if prep is None:
        from print.generation.whole_lesson.repository import PageDocumentRepository

        state = await PageDocumentRepository(session, preparation_generation_id).load_page_generation_state()
        prep = learn_preparation_context_from_state(state)
    production = await build_closed_learn_production_async(
        teaching_plan=teaching_plan,
        available_asset_ids=available_asset_ids,
        policy=policy,
        title=title,
        subject=subject,
        source_generation_id=output_id,
        approved_items=approved_items,
        write_interactions=True,
        provider=provider,
        engine=engine,
        preparation_context=prep,
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
        # Only set pack_id when it is a real learning_packs row (FK).
        pack_id=pack_id,
        created_at=_utcnow(),
        document_json=document,
        chunked_state_json={
            "shared_preparation": False,
            "native_learn": True,
            "control": {"pipeline": "native_learn"},
            "preparation_generation_id": preparation_generation_id,
            "teaching_plan_id": teaching_plan.teaching_plan_id,
            "teaching_plan_revision": teaching_plan.revision,
            "teaching_plan_hash": plan_hash,
            "selection_trace": production["selection_trace"],
            "form_prompt": "closed_learn_selection",
        },
    )
    session.add(generation)

    lesson_id = str(uuid.uuid4())
    now = _utcnow()
    editable = EditableLessonModel(
        id=lesson_id,
        user_id=user_id,
        source_generation_id=output_id,
        source_type="native_learn",
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
        native_policy_hash=str(production["native_policy_hash"]),
        package_contract_hash=str(production["package_contract_hash"]),
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
        "selection_trace": production["selection_trace"],
        "document": document,
        "content_hash": teaching_plan_content_hash(teaching_plan),
    }


__all__ = ["produce_learn_from_approved_teaching"]

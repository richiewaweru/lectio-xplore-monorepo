"""Preparation reuse / stale-admission status helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.contracts import PathPreparationBlocked
from core.database.models import GenerationModel, LessonProvenanceModel, PathLessonModel
from curriculum.models import PrepareLessonRequest, PreparedLessonResponse
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.persistence import load_chunked_state


async def try_reuse_existing_preparation(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    request: PrepareLessonRequest,
) -> tuple[PreparedLessonResponse, StructuralPlan] | None:
    """Return a reused preparation when the existing row is still valid.

    Raises PathPreparationBlocked when an existing preparation is stale or
    settings changed. Returns None when there is no reusable preparation and
    a fresh prepare should proceed.
    """
    previous_pack_id = lesson.pack_id
    if not previous_pack_id:
        return None

    generation = await session.get(GenerationModel, lesson.pack_id)
    provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
    if generation is None or provenance is None:
        return None

    if provenance.objective_hash != lesson.objective_hash:
        raise PathPreparationBlocked(
            "Existing preparation is stale; use explicit regeneration"
        )
    if provenance.path_lesson_revision not in {None, lesson.revision}:
        raise PathPreparationBlocked(
            "Existing preparation is for an earlier lesson revision; use explicit regeneration"
        )
    if provenance.lesson_mode not in {None, request.lesson_mode} or sorted(
        provenance.group_ids or []
    ) != sorted(request.group_ids):
        raise PathPreparationBlocked(
            "Preparation settings changed; use explicit regeneration"
        )
    try:
        state = await load_chunked_state(generation.id, session)
    except ValueError as exc:
        raise PathPreparationBlocked(
            "Existing preparation predates the resumable workflow; regenerate it explicitly"
        ) from exc
    # A failed pre-worker handoff can leave the lesson pointing at an
    # `awaiting_visuals` row before execution ever started. Treat that
    # empty row as stale so the normal Prepare action creates a fresh
    # native run instead of reopening a document that can never make
    # progress. A visual handoff with saved execution/document output
    # remains reusable and can still take the targeted visual retry path.
    stale_empty_visual_handoff = (
        state.get("stage") == "awaiting_visuals"
        and not bool(state.get("execution_started"))
        and not (
            isinstance(generation.document_json, dict)
            and isinstance(generation.document_json.get("sections"), list)
            and generation.document_json.get("sections")
        )
    )
    if stale_empty_visual_handoff:
        return None

    plan = StructuralPlan.model_validate(state.get("structural_plan"))
    slots = [section.role for section in plan.sections]
    return (
        PreparedLessonResponse(
            generation_id=generation.id,
            path_lesson_id=lesson.id,
            objective=lesson.objective,
            objective_hash=lesson.objective_hash,
            skeleton_id=provenance.skeleton_id or "",
            skeleton_version=provenance.skeleton_version or 0,
            slots=slots,
            section_roles=slots,
            status="awaiting_review",
            reused=True,
        ),
        plan,
    )


__all__ = ["try_reuse_existing_preparation"]

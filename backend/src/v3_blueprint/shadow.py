from __future__ import annotations

import csv
from io import StringIO
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel, SkeletonShadowRecordModel
from core.database.session import async_session_factory
from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.knowledge_classifier import classify_knowledge_type
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.skeletons import SkeletonPreviewRequest, load_skeleton_catalog

log = logging.getLogger(__name__)

_CSV_FIELDS = (
    "generation_id",
    "subject",
    "grade",
    "objective",
    "current_roles",
    "classifier_type",
    "classifier_confidence",
    "classifier_success_test",
    "classifier_note",
    "shadow_skeleton",
    "shadow_slots",
    "structural_match_score",
    "reviewer_preference",
    "wrong_classification",
    "deviation_required",
    "severity",
    "notes",
)


def structural_match_score(current_roles: list[str], shadow_slots: list[str]) -> float:
    if not current_roles and not shadow_slots:
        return 1.0
    if not current_roles or not shadow_slots:
        return 0.0
    previous = [0] * (len(shadow_slots) + 1)
    for role in current_roles:
        current = [0]
        for index, slot in enumerate(shadow_slots, start=1):
            current.append(
                previous[index - 1] + 1
                if role == slot
                else max(previous[index], current[index - 1])
            )
        previous = current
    return round(previous[-1] / max(len(current_roles), len(shadow_slots)), 4)


async def record_skeleton_shadow(
    *,
    generation_id: str,
    plan: StructuralPlan,
    form: V3InputForm,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> SkeletonShadowRecordModel:
    objective = plan.lesson_intent.goal
    classification = await classify_knowledge_type(
        objective,
        trace_id=generation_id,
        generation_id=generation_id,
    )
    catalog = load_skeleton_catalog()
    preview = catalog.preview(
        SkeletonPreviewRequest(
            objective=objective,
            lesson_mode=plan.lesson_mode,
            misconception_count=min(sum(len(card.misconceptions) for card in plan.cards), 3),
            group_profiles=["core"],
        ),
        knowledge_type=classification.primary_knowledge_type,
    )
    variant = preview.variants[0]
    current_roles = [section.role for section in plan.sections]
    shadow_slots = [slot.slot_id for slot in variant.slots]
    record = SkeletonShadowRecordModel(
        generation_id=generation_id,
        subject=form.subject,
        grade=form.grade_level,
        objective=objective,
        current_roles=current_roles,
        classifier_type=classification.primary_knowledge_type,
        classifier_confidence=classification.confidence,
        classifier_success_test=classification.success_test,
        classifier_note=classification.note,
        skeleton_id=preview.skeleton_id,
        skeleton_version=preview.skeleton_version,
        expanded_slots=shadow_slots,
        toggles_applied=variant.toggles_applied,
        expansion_warnings=variant.warnings,
        structural_match_score=structural_match_score(current_roles, shadow_slots),
    )
    async with session_factory() as session:
        existing = await session.scalar(
            select(SkeletonShadowRecordModel).where(
                SkeletonShadowRecordModel.generation_id == generation_id
            )
        )
        if existing is not None:
            await session.delete(existing)
            await session.flush()
        session.add(record)
        await session.commit()
    return record


async def shadow_review_csv(
    *,
    user_id: str,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> str:
    async with session_factory() as session:
        result = await session.execute(
            select(SkeletonShadowRecordModel)
            .join(
                GenerationModel,
                GenerationModel.id == SkeletonShadowRecordModel.generation_id,
            )
            .where(GenerationModel.user_id == user_id)
            .order_by(SkeletonShadowRecordModel.created_at)
        )
        records = list(result.scalars())

    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                "generation_id": record.generation_id,
                "subject": record.subject,
                "grade": record.grade,
                "objective": record.objective,
                "current_roles": " | ".join(record.current_roles),
                "classifier_type": record.classifier_type,
                "classifier_confidence": record.classifier_confidence,
                "classifier_success_test": record.classifier_success_test,
                "classifier_note": record.classifier_note or "",
                "shadow_skeleton": record.skeleton_id,
                "shadow_slots": " | ".join(record.expanded_slots),
                "structural_match_score": record.structural_match_score,
                "reviewer_preference": record.reviewer_preference or "",
                "wrong_classification": record.wrong_classification,
                "deviation_required": record.deviation_required,
                "severity": record.severity or "",
                "notes": record.notes or "",
            }
        )
    return output.getvalue()

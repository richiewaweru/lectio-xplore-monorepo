"""Teacher insight / analytics aggregates (Phase 11).

No frontend raw-attempt joins — all metrics computed server-side from
attempts + concept projections.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.database.session import get_async_session
from core.entities.user import User
from learning.class_service import require_class_owner
from learning.runtime_models import (
    ConceptEvidenceModel,
    ConceptStateModel,
    LearnAssignmentModel,
    LearnClassMembershipModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearningInstanceModel,
)

router = APIRouter(prefix="/api/v1/learn/analytics", tags=["learn-analytics"])

ITEM_LOW_SUCCESS = 0.4
ITEM_HIGH_RETRIES = 2.5


async def class_overview(
    session: AsyncSession, *, class_id: str, teacher_id: str
) -> dict[str, Any]:
    await require_class_owner(session, class_id=class_id, teacher_id=teacher_id)
    memberships = (
        await session.execute(
            select(LearnClassMembershipModel).where(
                LearnClassMembershipModel.class_id == class_id,
                LearnClassMembershipModel.learner_id.is_not(None),
            )
        )
    ).scalars().all()
    learner_ids = [m.learner_id for m in memberships if m.learner_id]
    if not learner_ids:
        return {
            "class_id": class_id,
            "learners": [],
            "completion": {"completed": 0, "active": 0},
            "graded": {"attempts": 0, "score_earned": 0, "score_possible": 0},
            "practice": {"attempts": 0, "score_earned": 0, "score_possible": 0},
            "concepts": [],
            "misconceptions": [],
            "item_quality": [],
        }

    instances = (
        await session.execute(
            select(LearningInstanceModel).where(
                LearningInstanceModel.learner_id.in_(learner_ids)
            )
        )
    ).scalars().all()
    instance_ids = [i.id for i in instances]
    attempts = (
        (
            await session.execute(
                select(LearnerAttemptModel).where(
                    LearnerAttemptModel.learning_instance_id.in_(instance_ids)
                )
            )
        )
        .scalars()
        .all()
        if instance_ids
        else []
    )

    graded = [a for a in attempts if a.assessment_mode == "graded"]
    practice = [a for a in attempts if a.assessment_mode == "practice"]
    states = (
        await session.execute(
            select(ConceptStateModel).where(ConceptStateModel.learner_id.in_(learner_ids))
        )
    ).scalars().all()

    # Misconception prevalence from evidence
    evidence = (
        await session.execute(
            select(ConceptEvidenceModel).where(
                ConceptEvidenceModel.learner_id.in_(learner_ids)
            )
        )
    ).scalars().all()
    misconception_counts: dict[str, int] = defaultdict(int)
    for row in evidence:
        if row.misconception_id:
            misconception_counts[row.misconception_id] += 1

    # Item quality: low first-success / high retries
    by_item: dict[str, list[LearnerAttemptModel]] = defaultdict(list)
    for a in attempts:
        by_item[a.interaction_id].append(a)
    item_quality = []
    for interaction_id, rows in by_item.items():
        # group by instance for first-attempt vs eventual
        by_instance: dict[str, list[LearnerAttemptModel]] = defaultdict(list)
        for r in rows:
            by_instance[r.learning_instance_id].append(r)
        first_ok = 0
        eventual_ok = 0
        retries = 0
        for group in by_instance.values():
            ordered = sorted(group, key=lambda x: x.created_at)
            retries += max(0, len(ordered) - 1)
            if ordered and ordered[0].outcome == "correct":
                first_ok += 1
            if any(o.outcome == "correct" for o in ordered):
                eventual_ok += 1
        n = len(by_instance) or 1
        first_rate = first_ok / n
        avg_retries = retries / n
        review = first_rate < ITEM_LOW_SUCCESS or avg_retries >= ITEM_HIGH_RETRIES
        item_quality.append(
            {
                "interaction_id": interaction_id,
                "first_attempt_success_rate": first_rate,
                "eventual_success_rate": eventual_ok / n,
                "avg_retries": avg_retries,
                "attempt_count": len(rows),
                "review_recommended": review,
            }
        )

    return {
        "class_id": class_id,
        "learners": learner_ids,
        "completion": {
            "completed": sum(1 for i in instances if i.status == "completed"),
            "active": sum(1 for i in instances if i.status == "active"),
        },
        "graded": {
            "attempts": len(graded),
            "score_earned": sum(a.score_earned for a in graded),
            "score_possible": sum(a.score_possible for a in graded),
        },
        "practice": {
            "attempts": len(practice),
            "score_earned": sum(a.score_earned for a in practice),
            "score_possible": sum(a.score_possible for a in practice),
        },
        "concepts": [
            {
                "learner_id": s.learner_id,
                "concept_id": s.concept_id,
                "classification": s.classification,
                "first_attempt_success": s.first_attempt_success,
                "score_earned": s.score_earned,
                "score_possible": s.score_possible,
            }
            for s in states
        ],
        "misconceptions": [
            {"misconception_id": mid, "count": count}
            for mid, count in sorted(misconception_counts.items(), key=lambda x: -x[1])
        ],
        "item_quality": item_quality,
    }


async def lesson_overview(
    session: AsyncSession, *, class_id: str, teacher_id: str, learn_release_id: str
) -> dict[str, Any]:
    base = await class_overview(session, class_id=class_id, teacher_id=teacher_id)
    memberships = (
        await session.execute(
            select(LearnClassMembershipModel).where(
                LearnClassMembershipModel.class_id == class_id,
                LearnClassMembershipModel.learner_id.is_not(None),
            )
        )
    ).scalars().all()
    learner_ids = [m.learner_id for m in memberships if m.learner_id]
    instances = (
        await session.execute(
            select(LearningInstanceModel).where(
                LearningInstanceModel.learner_id.in_(learner_ids or ["__none__"]),
                LearningInstanceModel.learn_release_id == learn_release_id,
            )
        )
    ).scalars().all()
    return {
        **base,
        "learn_release_id": learn_release_id,
        "lesson_instances": len(instances),
        "lesson_completed": sum(1 for i in instances if i.status == "completed"),
    }


async def concept_overview(
    session: AsyncSession, *, class_id: str, teacher_id: str, concept_id: str
) -> dict[str, Any]:
    base = await class_overview(session, class_id=class_id, teacher_id=teacher_id)
    concepts = [c for c in base["concepts"] if c["concept_id"] == concept_id]
    return {"class_id": class_id, "concept_id": concept_id, "learners": concepts}


async def learner_detail(
    session: AsyncSession, *, class_id: str, teacher_id: str, learner_id: str
) -> dict[str, Any]:
    await require_class_owner(session, class_id=class_id, teacher_id=teacher_id)
    membership = await session.scalar(
        select(LearnClassMembershipModel).where(
            LearnClassMembershipModel.class_id == class_id,
            LearnClassMembershipModel.learner_id == learner_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Learner not in class")
    learner = await session.get(LearnerIdentityModel, learner_id)
    instances = (
        await session.execute(
            select(LearningInstanceModel).where(
                LearningInstanceModel.learner_id == learner_id
            )
        )
    ).scalars().all()
    states = (
        await session.execute(
            select(ConceptStateModel).where(ConceptStateModel.learner_id == learner_id)
        )
    ).scalars().all()
    return {
        "class_id": class_id,
        "learner_id": learner_id,
        "display_name": learner.display_name if learner else "",
        "instances": [
            {
                "id": i.id,
                "status": i.status,
                "score_earned": i.score_earned,
                "score_possible": i.score_possible,
                "learn_release_id": i.learn_release_id,
            }
            for i in instances
        ],
        "concepts": [
            {
                "concept_id": s.concept_id,
                "classification": s.classification,
                "score_earned": s.score_earned,
                "score_possible": s.score_possible,
                "first_attempt_success": s.first_attempt_success,
            }
            for s in states
        ],
    }


@router.get("/classes/{class_id}/overview")
async def api_class_overview(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    return await class_overview(session, class_id=class_id, teacher_id=current_user.id)


@router.get("/classes/{class_id}/lessons/{learn_release_id}")
async def api_lesson_overview(
    class_id: str,
    learn_release_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    return await lesson_overview(
        session,
        class_id=class_id,
        teacher_id=current_user.id,
        learn_release_id=learn_release_id,
    )


@router.get("/classes/{class_id}/concepts/{concept_id}")
async def api_concept_overview(
    class_id: str,
    concept_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    return await concept_overview(
        session, class_id=class_id, teacher_id=current_user.id, concept_id=concept_id
    )


@router.get("/classes/{class_id}/learners/{learner_id}")
async def api_learner_detail(
    class_id: str,
    learner_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    return await learner_detail(
        session, class_id=class_id, teacher_id=current_user.id, learner_id=learner_id
    )

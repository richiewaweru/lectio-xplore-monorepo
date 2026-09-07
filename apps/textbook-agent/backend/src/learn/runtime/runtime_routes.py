"""HTTP routes for Learn runtime, classes, assignments, and teacher insight."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.auth.middleware import get_current_user
from core.database.models import LearnReleaseModel
from infra.database.session import get_async_session
from core.entities.user import User
from learn.class_service import (
    accept_class_invite,
    add_learner_to_class,
    create_assignment,
    create_class,
    require_class_owner,
)
from learn.runtime_models import (
    ConceptStateModel,
    LearnAssignmentModel,
    LearnAssignmentRecipientModel,
    LearnClassMembershipModel,
    LearnClassModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearningInstanceModel,
    LessonProgressModel,
)
from learn.runtime_service import (
    complete_instance,
    create_learner,
    create_learner_session,
    rebuild_concept_states,
    rebuild_progress,
    require_learner_session_for,
    score_split,
    set_current_section,
    start_learning_instance,
    submit_attempt,
)

router = APIRouter(prefix="/api/v1/learn", tags=["learn-runtime"])


class CreateLearnerBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class StartInstanceBody(BaseModel):
    learner_id: str
    learn_release_id: str
    assignment_id: str | None = None


class SubmitAttemptBody(BaseModel):
    interaction_id: str
    client_submission_id: str
    response_json: dict[str, Any]
    outcome: str
    score_earned: float = 0
    score_possible: float = 1
    assessment_mode: str = "graded"
    section_id: str | None = None
    concept_bindings: list[dict[str, Any]] | None = None
    misconception_id: str | None = None


class CreateClassBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AddLearnerBody(BaseModel):
    display_name: str | None = None
    learner_id: str | None = None


class AcceptInviteBody(BaseModel):
    invite_code: str
    learner_id: str


class CreateAssignmentBody(BaseModel):
    learn_release_id: str
    title: str
    class_id: str | None = None
    class_ids: list[str] | None = None
    mode: str = "rolling"
    selected_learner_ids: list[str] | None = None


class CreateSessionBody(BaseModel):
    learner_id: str | None = None
    invite_code: str | None = None


class ResumeSectionBody(BaseModel):
    section_id: str


async def _optional_learner_guard(
    session: AsyncSession,
    *,
    learner_id: str,
    x_learner_session: str | None,
) -> None:
    """If session header present, enforce own-data; else teacher JWT may proceed."""
    if x_learner_session:
        await require_learner_session_for(
            session, token=x_learner_session, learner_id=learner_id
        )


@router.post("/sessions")
async def api_create_session(
    body: CreateSessionBody,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Opaque learner session via invite code or learner id (no email)."""
    row = await create_learner_session(
        session, learner_id=body.learner_id, invite_code=body.invite_code
    )
    await session.commit()
    return {"token": row.token, "learner_id": row.learner_id, "session_id": row.id}


@router.post("/learners")
async def api_create_learner(
    body: CreateLearnerBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    learner = await create_learner(
        session, display_name=body.display_name, created_by_teacher_id=current_user.id
    )
    await session.commit()
    return {"id": learner.id, "display_name": learner.display_name, "invite_code": learner.invite_code}


@router.post("/instances")
async def api_start_instance(
    body: StartInstanceBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    release = await session.get(LearnReleaseModel, body.learn_release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="LearnRelease not found")
    learner = await session.get(LearnerIdentityModel, body.learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    await _optional_learner_guard(
        session, learner_id=body.learner_id, x_learner_session=x_learner_session
    )
    instance = await start_learning_instance(
        session,
        learner_id=body.learner_id,
        learn_release_id=body.learn_release_id,
        assignment_id=body.assignment_id,
    )
    await session.commit()
    return {
        "id": instance.id,
        "learner_id": instance.learner_id,
        "learn_release_id": instance.learn_release_id,
        "status": instance.status,
        "current_section_id": instance.current_section_id,
    }


@router.post("/instances/{instance_id}/attempts")
async def api_submit_attempt(
    instance_id: str,
    body: SubmitAttemptBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    instance = await session.get(LearningInstanceModel, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    await _optional_learner_guard(
        session, learner_id=instance.learner_id, x_learner_session=x_learner_session
    )
    attempt = await submit_attempt(
        session,
        learning_instance_id=instance_id,
        interaction_id=body.interaction_id,
        client_submission_id=body.client_submission_id,
        response_json=body.response_json,
        outcome=body.outcome,
        score_earned=body.score_earned,
        score_possible=body.score_possible,
        assessment_mode=body.assessment_mode,
        section_id=body.section_id,
        concept_bindings=body.concept_bindings,
        misconception_id=body.misconception_id,
    )
    if instance.assignment_id:
        recipient = await session.scalar(
            select(LearnAssignmentRecipientModel).where(
                LearnAssignmentRecipientModel.assignment_id == instance.assignment_id,
                LearnAssignmentRecipientModel.learner_id == instance.learner_id,
            )
        )
        if recipient is not None and recipient.status == "assigned":
            from learn.runtime.runtime_service import _utcnow

            recipient.status = "started"
            recipient.started_at = _utcnow()
    await session.commit()
    return {
        "id": attempt.id,
        "client_submission_id": attempt.client_submission_id,
        "outcome": attempt.outcome,
        "score_earned": attempt.score_earned,
        "score_possible": attempt.score_possible,
    }


@router.get("/instances/{instance_id}")
async def api_get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    instance = await session.get(LearningInstanceModel, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    await _optional_learner_guard(
        session, learner_id=instance.learner_id, x_learner_session=x_learner_session
    )
    progress = await session.scalar(
        select(LessonProgressModel).where(
            LessonProgressModel.learning_instance_id == instance_id
        )
    )
    attempts = (
        await session.execute(
            select(LearnerAttemptModel)
            .where(LearnerAttemptModel.learning_instance_id == instance_id)
            .order_by(LearnerAttemptModel.created_at.asc())
        )
    ).scalars().all()
    scores = score_split(list(attempts))
    return {
        "id": instance.id,
        "learner_id": instance.learner_id,
        "learn_release_id": instance.learn_release_id,
        "assignment_id": instance.assignment_id,
        "status": instance.status,
        "score_earned": instance.score_earned,
        "score_possible": instance.score_possible,
        "current_section_id": instance.current_section_id,
        "graded": scores["graded"],
        "practice": scores["practice"],
        "progress": {
            "completed_section_ids": progress.completed_section_ids if progress else [],
            "completed_interaction_ids": progress.completed_interaction_ids if progress else [],
            "score_earned": progress.score_earned if progress else 0,
            "score_possible": progress.score_possible if progress else 0,
        },
        "attempts": [
            {
                "id": a.id,
                "interaction_id": a.interaction_id,
                "client_submission_id": a.client_submission_id,
                "outcome": a.outcome,
                "assessment_mode": a.assessment_mode,
                "score_earned": a.score_earned,
                "score_possible": a.score_possible,
            }
            for a in attempts
        ],
    }


@router.post("/instances/{instance_id}/resume")
async def api_resume_section(
    instance_id: str,
    body: ResumeSectionBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    instance = await session.get(LearningInstanceModel, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    await _optional_learner_guard(
        session, learner_id=instance.learner_id, x_learner_session=x_learner_session
    )
    updated = await set_current_section(
        session, learning_instance_id=instance_id, section_id=body.section_id
    )
    await session.commit()
    return {"id": updated.id, "current_section_id": updated.current_section_id}


@router.post("/instances/{instance_id}/complete")
async def api_complete_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    instance = await session.get(LearningInstanceModel, instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    await _optional_learner_guard(
        session, learner_id=instance.learner_id, x_learner_session=x_learner_session
    )
    completed = await complete_instance(session, instance_id)
    if completed.assignment_id:
        recipient = await session.scalar(
            select(LearnAssignmentRecipientModel).where(
                LearnAssignmentRecipientModel.assignment_id == completed.assignment_id,
                LearnAssignmentRecipientModel.learner_id == completed.learner_id,
            )
        )
        if recipient is not None:
            from learn.runtime.runtime_service import _utcnow

            recipient.status = "completed"
            recipient.completed_at = _utcnow()
    await session.commit()
    return {"id": completed.id, "status": completed.status, "completed_at": completed.completed_at}


@router.post("/instances/{instance_id}/rebuild-progress")
async def api_rebuild_progress(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    progress = await rebuild_progress(session, instance_id)
    await session.commit()
    return {
        "completed_section_ids": progress.completed_section_ids,
        "completed_interaction_ids": progress.completed_interaction_ids,
        "score_earned": progress.score_earned,
        "score_possible": progress.score_possible,
    }


@router.post("/learners/{learner_id}/rebuild-concept-states")
async def api_rebuild_concept_states(
    learner_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    states = await rebuild_concept_states(session, learner_id=learner_id)
    await session.commit()
    return [
        {
            "concept_id": s.concept_id,
            "classification": s.classification,
            "score_earned": s.score_earned,
            "score_possible": s.score_possible,
            "first_attempt_success": s.first_attempt_success,
        }
        for s in states
    ]


@router.post("/classes")
async def api_create_class(
    body: CreateClassBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await create_class(session, teacher_id=current_user.id, name=body.name)
    await session.commit()
    return {
        "id": row.id,
        "name": row.name,
        "invite_code": row.invite_code,
        "role": "owner",
    }


@router.get("/classes")
async def api_list_classes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(LearnClassModel).where(LearnClassModel.teacher_id == current_user.id)
        )
    ).scalars().all()
    return [{"id": r.id, "name": r.name, "invite_code": r.invite_code} for r in rows]


@router.get("/classes/{class_id}")
async def api_get_class(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await require_class_owner(session, class_id=class_id, teacher_id=current_user.id)
    memberships = (
        await session.execute(
            select(LearnClassMembershipModel).where(
                LearnClassMembershipModel.class_id == class_id
            )
        )
    ).scalars().all()
    assignments = (
        await session.execute(
            select(LearnAssignmentModel).where(LearnAssignmentModel.class_id == class_id)
        )
    ).scalars().all()
    learners = []
    for m in memberships:
        if not m.learner_id:
            continue
        learner = await session.get(LearnerIdentityModel, m.learner_id)
        learners.append(
            {
                "learner_id": m.learner_id,
                "display_name": learner.display_name if learner else "",
                "role": m.role,
                "status": m.status,
            }
        )
    return {
        "id": row.id,
        "name": row.name,
        "invite_code": row.invite_code,
        "learners": learners,
        "assignments": [
            {"id": a.id, "title": a.title, "mode": a.mode, "active": a.active}
            for a in assignments
        ],
        "staff_roles": [
            {"teacher_user_id": m.teacher_user_id, "role": m.role}
            for m in memberships
            if m.teacher_user_id
        ],
    }


@router.post("/classes/{class_id}/learners")
async def api_add_learner(
    class_id: str,
    body: AddLearnerBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    learner, membership = await add_learner_to_class(
        session,
        class_id=class_id,
        teacher_id=current_user.id,
        display_name=body.display_name,
        learner_id=body.learner_id,
    )
    await session.commit()
    return {"learner_id": learner.id, "membership_id": membership.id, "class_id": class_id}


@router.post("/classes/accept-invite")
async def api_accept_invite(
    body: AcceptInviteBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    membership = await accept_class_invite(
        session, invite_code=body.invite_code, learner_id=body.learner_id
    )
    await session.commit()
    return {"membership_id": membership.id, "class_id": membership.class_id}


@router.post("/assignments")
async def api_create_assignment(
    body: CreateAssignmentBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    release = await session.get(LearnReleaseModel, body.learn_release_id)
    if release is None or release.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="LearnRelease not found")
    assignment = await create_assignment(
        session,
        teacher_id=current_user.id,
        learn_release_id=body.learn_release_id,
        title=body.title,
        class_id=body.class_id,
        class_ids=body.class_ids,
        mode=body.mode,
        selected_learner_ids=body.selected_learner_ids,
    )
    await session.commit()
    return {
        "id": assignment.id,
        "mode": assignment.mode,
        "learn_release_id": assignment.learn_release_id,
        "class_id": assignment.class_id,
        "class_ids": body.class_ids or ([body.class_id] if body.class_id else []),
    }


@router.get("/learners/{learner_id}/home")
async def api_learner_home(
    learner_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    x_learner_session: str | None = Header(default=None, alias="X-Learner-Session"),
) -> dict[str, Any]:
    learner = await session.get(LearnerIdentityModel, learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    await _optional_learner_guard(
        session, learner_id=learner_id, x_learner_session=x_learner_session
    )
    instances = (
        await session.execute(
            select(LearningInstanceModel)
            .where(LearningInstanceModel.learner_id == learner_id)
            .order_by(LearningInstanceModel.updated_at.desc())
        )
    ).scalars().all()
    memberships = (
        await session.execute(
            select(LearnClassMembershipModel).where(
                LearnClassMembershipModel.learner_id == learner_id
            )
        )
    ).scalars().all()
    classes = []
    for m in memberships:
        c = await session.get(LearnClassModel, m.class_id)
        if c:
            classes.append({"id": c.id, "name": c.name})

    due_soon = [i for i in instances if i.status == "active" and i.assignment_id]
    in_progress = [i for i in instances if i.status == "active"]
    completed = [i for i in instances if i.status == "completed"]

    def _inst(i: LearningInstanceModel) -> dict[str, Any]:
        return {
            "id": i.id,
            "learn_release_id": i.learn_release_id,
            "assignment_id": i.assignment_id,
            "status": i.status,
            "score_earned": i.score_earned,
            "score_possible": i.score_possible,
            "current_section_id": i.current_section_id,
        }

    return {
        "learner_id": learner_id,
        "display_name": learner.display_name,
        "buckets": {
            "due_soon": [_inst(i) for i in due_soon],
            "in_progress": [_inst(i) for i in in_progress],
            "completed": [_inst(i) for i in completed],
            "classes": classes,
        },
        "instances": [_inst(i) for i in instances],
        "classes": classes,
    }


@router.get("/classes/{class_id}/insight")
async def api_class_insight(
    class_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    from learn.insight_service import class_overview

    return await class_overview(session, class_id=class_id, teacher_id=current_user.id)

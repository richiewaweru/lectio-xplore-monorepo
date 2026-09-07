"""Classes, memberships, and assignments (Phases 08–09)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learn.runtime_models import (
    LearnAssignmentModel,
    LearnAssignmentRecipientModel,
    LearnAssignmentTargetModel,
    LearnClassMembershipModel,
    LearnClassModel,
    LearnerIdentityModel,
)
from learn.runtime_service import create_learner, start_learning_instance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _invite_code() -> str:
    return secrets.token_hex(4)


async def create_class(
    session: AsyncSession, *, teacher_id: str, name: str
) -> LearnClassModel:
    row = LearnClassModel(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        name=name.strip() or "Class",
        invite_code=_invite_code(),
        created_at=_utcnow(),
    )
    session.add(row)
    await session.flush()
    # Default owner membership for the creating teacher.
    session.add(
        LearnClassMembershipModel(
            id=str(uuid.uuid4()),
            class_id=row.id,
            learner_id=None,
            teacher_user_id=teacher_id,
            role="owner",
            status="active",
            joined_at=_utcnow(),
        )
    )
    await session.flush()
    return row


async def require_class_owner(
    session: AsyncSession, *, class_id: str, teacher_id: str
) -> LearnClassModel:
    row = await session.get(LearnClassModel, class_id)
    if row is None or row.teacher_id != teacher_id:
        raise HTTPException(status_code=404, detail="Class not found")
    return row


async def require_class_staff(
    session: AsyncSession, *, class_id: str, teacher_id: str
) -> LearnClassModel:
    """Owner / teacher / assistant may manage; others get 404."""
    row = await session.get(LearnClassModel, class_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if row.teacher_id == teacher_id:
        return row
    membership = await session.scalar(
        select(LearnClassMembershipModel).where(
            LearnClassMembershipModel.class_id == class_id,
            LearnClassMembershipModel.teacher_user_id == teacher_id,
            LearnClassMembershipModel.role.in_(("owner", "teacher", "assistant")),
            LearnClassMembershipModel.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return row


async def add_learner_to_class(
    session: AsyncSession,
    *,
    class_id: str,
    teacher_id: str,
    display_name: str | None = None,
    learner_id: str | None = None,
) -> tuple[LearnerIdentityModel, LearnClassMembershipModel]:
    await require_class_owner(session, class_id=class_id, teacher_id=teacher_id)
    if learner_id:
        learner = await session.get(LearnerIdentityModel, learner_id)
        if learner is None:
            raise HTTPException(status_code=404, detail="Learner not found")
    else:
        learner = await create_learner(
            session,
            display_name=display_name or "Learner",
            created_by_teacher_id=teacher_id,
        )
    existing = await session.scalar(
        select(LearnClassMembershipModel).where(
            LearnClassMembershipModel.class_id == class_id,
            LearnClassMembershipModel.learner_id == learner.id,
        )
    )
    if existing:
        return learner, existing
    membership = LearnClassMembershipModel(
        id=str(uuid.uuid4()),
        class_id=class_id,
        learner_id=learner.id,
        role="learner",
        status="active",
        joined_at=_utcnow(),
    )
    session.add(membership)
    await session.flush()

    # Rolling late-join for this class targets
    await _distribute_rolling_for_learner(session, class_id=class_id, learner_id=learner.id)
    return learner, membership


async def accept_class_invite(
    session: AsyncSession, *, invite_code: str, learner_id: str
) -> LearnClassMembershipModel:
    class_row = await session.scalar(
        select(LearnClassModel).where(LearnClassModel.invite_code == invite_code)
    )
    if class_row is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    existing = await session.scalar(
        select(LearnClassMembershipModel).where(
            LearnClassMembershipModel.class_id == class_row.id,
            LearnClassMembershipModel.learner_id == learner_id,
        )
    )
    if existing:
        return existing
    membership = LearnClassMembershipModel(
        id=str(uuid.uuid4()),
        class_id=class_row.id,
        learner_id=learner_id,
        role="learner",
        status="active",
        joined_at=_utcnow(),
    )
    session.add(membership)
    await session.flush()
    await _distribute_rolling_for_learner(session, class_id=class_row.id, learner_id=learner_id)
    return membership


async def _distribute_rolling_for_learner(
    session: AsyncSession, *, class_id: str, learner_id: str
) -> None:
    # Legacy class_id column + new targets table
    assignments = (
        await session.execute(
            select(LearnAssignmentModel).where(
                LearnAssignmentModel.active.is_(True),
                LearnAssignmentModel.mode == "rolling",
            )
        )
    ).scalars().all()
    for assignment in assignments:
        targets_class = assignment.class_id == class_id
        if not targets_class:
            target = await session.scalar(
                select(LearnAssignmentTargetModel).where(
                    LearnAssignmentTargetModel.assignment_id == assignment.id,
                    LearnAssignmentTargetModel.class_id == class_id,
                )
            )
            targets_class = target is not None
        if targets_class:
            await ensure_assignment_instance(
                session, assignment=assignment, learner_id=learner_id, class_id=class_id
            )


async def create_assignment(
    session: AsyncSession,
    *,
    teacher_id: str,
    learn_release_id: str,
    title: str,
    class_id: str | None = None,
    class_ids: list[str] | None = None,
    mode: str = "rolling",
    selected_learner_ids: list[str] | None = None,
) -> LearnAssignmentModel:
    if mode not in {"rolling", "snapshot", "selected"}:
        raise HTTPException(status_code=422, detail="Invalid assignment mode")

    target_class_ids = list(class_ids or [])
    if class_id and class_id not in target_class_ids:
        target_class_ids.append(class_id)

    for cid in target_class_ids:
        await require_class_owner(session, class_id=cid, teacher_id=teacher_id)

    assignment = LearnAssignmentModel(
        id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        learn_release_id=learn_release_id,
        class_id=target_class_ids[0] if target_class_ids else None,
        mode=mode,
        title=title.strip() or "Assignment",
        selected_learner_ids=selected_learner_ids,
        active=True,
        created_at=_utcnow(),
    )
    session.add(assignment)
    await session.flush()

    for cid in target_class_ids:
        session.add(
            LearnAssignmentTargetModel(
                id=str(uuid.uuid4()),
                assignment_id=assignment.id,
                class_id=cid,
                learner_id=None,
                created_at=_utcnow(),
            )
        )
    for lid in selected_learner_ids or []:
        session.add(
            LearnAssignmentTargetModel(
                id=str(uuid.uuid4()),
                assignment_id=assignment.id,
                class_id=None,
                learner_id=lid,
                created_at=_utcnow(),
            )
        )
    await session.flush()

    learner_pairs: list[tuple[str, str | None]] = []
    if mode == "selected":
        learner_pairs = [(lid, None) for lid in (selected_learner_ids or [])]
    else:
        for cid in target_class_ids:
            memberships = (
                await session.execute(
                    select(LearnClassMembershipModel).where(
                        LearnClassMembershipModel.class_id == cid,
                        LearnClassMembershipModel.status == "active",
                        LearnClassMembershipModel.learner_id.is_not(None),
                    )
                )
            ).scalars().all()
            for m in memberships:
                if m.learner_id:
                    learner_pairs.append((m.learner_id, cid))

    seen: set[str] = set()
    for lid, cid in learner_pairs:
        if lid in seen:
            continue
        seen.add(lid)
        await ensure_assignment_instance(
            session, assignment=assignment, learner_id=lid, class_id=cid
        )
    return assignment


async def ensure_assignment_instance(
    session: AsyncSession,
    *,
    assignment: LearnAssignmentModel,
    learner_id: str,
    class_id: str | None = None,
) -> Any:
    from learn.runtime_models import LearningInstanceModel

    existing_recipient = await session.scalar(
        select(LearnAssignmentRecipientModel).where(
            LearnAssignmentRecipientModel.assignment_id == assignment.id,
            LearnAssignmentRecipientModel.learner_id == learner_id,
        )
    )
    if existing_recipient is not None:
        if existing_recipient.learning_instance_id:
            return await session.get(
                LearningInstanceModel, existing_recipient.learning_instance_id
            )
        # Recipient exists without instance — unusual; fall through carefully

    existing = await session.scalar(
        select(LearningInstanceModel).where(
            LearningInstanceModel.assignment_id == assignment.id,
            LearningInstanceModel.learner_id == learner_id,
        )
    )
    if existing:
        if existing_recipient is None:
            session.add(
                LearnAssignmentRecipientModel(
                    id=str(uuid.uuid4()),
                    assignment_id=assignment.id,
                    learner_id=learner_id,
                    class_id=class_id or assignment.class_id,
                    status="started" if existing.status == "active" else existing.status,
                    learning_instance_id=existing.id,
                    assigned_at=_utcnow(),
                    started_at=existing.started_at,
                )
            )
            await session.flush()
        return existing

    if assignment.mode == "snapshot" and existing_recipient is None:
        # Snapshot late-join path: only create when called from create_assignment snapshot
        # (accept_invite / add_learner skip snapshot via rolling filter).
        pass

    instance = await start_learning_instance(
        session,
        learner_id=learner_id,
        learn_release_id=assignment.learn_release_id,
        assignment_id=assignment.id,
    )
    if existing_recipient is None:
        session.add(
            LearnAssignmentRecipientModel(
                id=str(uuid.uuid4()),
                assignment_id=assignment.id,
                learner_id=learner_id,
                class_id=class_id or assignment.class_id,
                status="assigned",
                learning_instance_id=instance.id,
                assigned_at=_utcnow(),
            )
        )
    else:
        existing_recipient.learning_instance_id = instance.id
    await session.flush()
    return instance

"""Learn runtime services: instances, attempts, progress, evidence, sessions (Phases 06–07)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import LearnReleaseModel
from learning.runtime_models import (
    ConceptEvidenceModel,
    ConceptStateModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearnerSessionModel,
    LearningInstanceModel,
    LessonProgressModel,
)

# Band thresholds (Phase 07) — Strong / Developing / Needs Practice.
# Numeric ratios kept documented + testable; legacy aliases map to these labels.
BAND_STRONG_RATIO = 0.85
BAND_DEVELOPING_RATIO = 0.55
# Below developing → Needs Practice

BAND_STRONG = "Strong"
BAND_DEVELOPING = "Developing"
BAND_NEEDS_PRACTICE = "Needs Practice"

# Legacy aliases retained for older fixtures/tests during closeout.
CONCEPT_MASTERED_RATIO = BAND_STRONG_RATIO
CONCEPT_PROFICIENT_RATIO = 0.7
CONCEPT_EMERGING_RATIO = 0.4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def classify_concept(score_earned: float, score_possible: float) -> str:
    """Map score ratio to Strong / Developing / Needs Practice."""
    if score_possible <= 0:
        return BAND_NEEDS_PRACTICE
    ratio = score_earned / score_possible
    if ratio >= BAND_STRONG_RATIO:
        return BAND_STRONG
    if ratio >= BAND_DEVELOPING_RATIO:
        return BAND_DEVELOPING
    return BAND_NEEDS_PRACTICE


def concept_refs_from_section(section: dict[str, Any]) -> list[dict[str, Any]]:
    """Explicit node→concept binding helper from authored section concept_refs."""
    refs = section.get("concept_refs") or section.get("concepts") or []
    if not isinstance(refs, list):
        return []
    bindings: list[dict[str, Any]] = []
    for ref in refs:
        if isinstance(ref, str) and ref.strip():
            bindings.append({"concept_id": ref.strip(), "weight": 1.0, "node_id": section.get("id")})
        elif isinstance(ref, dict) and ref.get("concept_id"):
            bindings.append(
                {
                    "concept_id": str(ref["concept_id"]),
                    "weight": float(ref.get("weight", 1.0)),
                    "node_id": ref.get("node_id") or section.get("id"),
                    "unit_id": ref.get("unit_id"),
                    "path_lesson_id": ref.get("path_lesson_id"),
                }
            )
    return bindings


async def create_learner(
    session: AsyncSession,
    *,
    display_name: str,
    created_by_teacher_id: str | None = None,
    invite_code: str | None = None,
) -> LearnerIdentityModel:
    learner = LearnerIdentityModel(
        id=str(uuid.uuid4()),
        display_name=display_name.strip() or "Learner",
        invite_code=invite_code or str(uuid.uuid4())[:8],
        created_by_teacher_id=created_by_teacher_id,
        created_at=_utcnow(),
    )
    session.add(learner)
    await session.flush()
    return learner


async def create_learner_session(
    session: AsyncSession,
    *,
    learner_id: str | None = None,
    invite_code: str | None = None,
) -> LearnerSessionModel:
    """Create opaque session via learner id or invite code (no email)."""
    learner: LearnerIdentityModel | None = None
    if learner_id:
        learner = await session.get(LearnerIdentityModel, learner_id)
    elif invite_code:
        learner = await session.scalar(
            select(LearnerIdentityModel).where(LearnerIdentityModel.invite_code == invite_code)
        )
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    row = LearnerSessionModel(
        id=str(uuid.uuid4()),
        learner_id=learner.id,
        token=secrets.token_urlsafe(32),
        created_at=_utcnow(),
        last_seen_at=_utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


async def resolve_learner_session(
    session: AsyncSession, token: str | None
) -> LearnerSessionModel | None:
    if not token:
        return None
    row = await session.scalar(
        select(LearnerSessionModel).where(LearnerSessionModel.token == token)
    )
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at < _utcnow():
        return None
    row.last_seen_at = _utcnow()
    return row


async def require_learner_session_for(
    session: AsyncSession,
    *,
    token: str | None,
    learner_id: str,
) -> LearnerSessionModel:
    row = await resolve_learner_session(session, token)
    if row is None:
        raise HTTPException(status_code=401, detail="Learner session required")
    if row.learner_id != learner_id:
        raise HTTPException(status_code=403, detail="Session belongs to another learner")
    return row


async def require_instance_session(
    session: AsyncSession,
    *,
    token: str | None,
    instance: LearningInstanceModel,
) -> LearnerSessionModel:
    return await require_learner_session_for(
        session, token=token, learner_id=instance.learner_id
    )


async def start_learning_instance(
    session: AsyncSession,
    *,
    learner_id: str,
    learn_release_id: str,
    assignment_id: str | None = None,
) -> LearningInstanceModel:
    instance = LearningInstanceModel(
        id=str(uuid.uuid4()),
        learner_id=learner_id,
        learn_release_id=learn_release_id,
        assignment_id=assignment_id,
        status="active",
        started_at=_utcnow(),
        updated_at=_utcnow(),
    )
    session.add(instance)
    progress = LessonProgressModel(
        id=str(uuid.uuid4()),
        learning_instance_id=instance.id,
        completed_section_ids=[],
        completed_interaction_ids=[],
        score_earned=0.0,
        score_possible=0.0,
        updated_at=_utcnow(),
    )
    session.add(progress)
    await session.flush()
    return instance


async def set_current_section(
    session: AsyncSession,
    *,
    learning_instance_id: str,
    section_id: str,
) -> LearningInstanceModel:
    instance = await session.get(LearningInstanceModel, learning_instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    instance.current_section_id = section_id
    instance.updated_at = _utcnow()
    await session.flush()
    return instance


def score_split(attempts: list[LearnerAttemptModel]) -> dict[str, dict[str, float | int]]:
    graded = [a for a in attempts if a.assessment_mode == "graded"]
    practice = [a for a in attempts if a.assessment_mode == "practice"]
    return {
        "graded": {
            "attempts": len(graded),
            "score_earned": sum(float(a.score_earned) for a in graded),
            "score_possible": sum(float(a.score_possible) for a in graded),
        },
        "practice": {
            "attempts": len(practice),
            "score_earned": sum(float(a.score_earned) for a in practice),
            "score_possible": sum(float(a.score_possible) for a in practice),
        },
    }


def extract_v1_requirements(document: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Required section ids + graded interaction ids from release document.

    Graded interactions are only those explicitly marked assessment_mode=graded
    (section or block / interaction contract). Component heuristics are not used
    so manual drafts without markers remain completable after section visits.
    """
    required_sections: set[str] = set()
    required_interactions: set[str] = set()
    sections = document.get("sections") if isinstance(document, dict) else None
    if not isinstance(sections, list):
        return required_sections, required_interactions
    blocks = document.get("blocks") if isinstance(document.get("blocks"), dict) else {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        sid = section.get("id")
        if not sid:
            continue
        if section.get("required", True):
            required_sections.add(str(sid))
        section_mode = section.get("assessment_mode")
        for bid in section.get("block_ids") or []:
            block = blocks.get(bid) if isinstance(blocks, dict) else None
            if not isinstance(block, dict):
                continue
            interaction_id = str(block.get("id") or bid)
            assessment = block.get("assessment_mode") or section_mode
            contract = block.get("interaction") or block.get("learn_interaction")
            if isinstance(contract, dict):
                if contract.get("assessment_mode") == "graded":
                    required_interactions.add(str(contract.get("id") or interaction_id))
            elif assessment == "graded":
                required_interactions.add(interaction_id)
    return required_sections, required_interactions


async def submit_attempt(
    session: AsyncSession,
    *,
    learning_instance_id: str,
    interaction_id: str,
    client_submission_id: str,
    response_json: dict[str, Any],
    outcome: str,
    score_earned: float,
    score_possible: float,
    assessment_mode: str = "graded",
    section_id: str | None = None,
    concept_bindings: list[dict[str, Any]] | None = None,
    misconception_id: str | None = None,
) -> LearnerAttemptModel:
    """Idempotent by (instance, client_submission_id). Immutable once written."""
    existing = await session.scalar(
        select(LearnerAttemptModel).where(
            LearnerAttemptModel.learning_instance_id == learning_instance_id,
            LearnerAttemptModel.client_submission_id == client_submission_id,
        )
    )
    if existing is not None:
        return existing

    attempt = LearnerAttemptModel(
        id=str(uuid.uuid4()),
        learning_instance_id=learning_instance_id,
        interaction_id=interaction_id,
        section_id=section_id,
        client_submission_id=client_submission_id,
        assessment_mode=assessment_mode,
        outcome=outcome,
        score_earned=score_earned,
        score_possible=score_possible,
        response_json=response_json,
        created_at=_utcnow(),
    )
    session.add(attempt)
    await session.flush()

    instance = await session.get(LearningInstanceModel, learning_instance_id)
    if instance is not None and assessment_mode == "graded":
        instance.score_earned = float(instance.score_earned or 0) + score_earned
        instance.score_possible = float(instance.score_possible or 0) + score_possible
        instance.updated_at = _utcnow()
    if instance is not None and section_id:
        instance.current_section_id = section_id
        instance.updated_at = _utcnow()

    await rebuild_progress(session, learning_instance_id)

    if concept_bindings and instance is not None:
        for binding in concept_bindings:
            weight = float(binding.get("weight", 1.0))
            session.add(
                ConceptEvidenceModel(
                    id=str(uuid.uuid4()),
                    learner_id=instance.learner_id,
                    learning_instance_id=learning_instance_id,
                    attempt_id=attempt.id,
                    learn_release_id=instance.learn_release_id,
                    path_lesson_id=binding.get("path_lesson_id"),
                    concept_id=str(binding["concept_id"]),
                    unit_id=binding.get("unit_id"),
                    node_id=binding.get("node_id") or interaction_id,
                    weight=weight,
                    score_earned=score_earned * weight,
                    score_possible=score_possible * weight,
                    misconception_id=misconception_id or binding.get("misconception_id"),
                    created_at=_utcnow(),
                )
            )
        await session.flush()
        await rebuild_concept_states(session, learner_id=instance.learner_id)

    return attempt


async def rebuild_progress(session: AsyncSession, learning_instance_id: str) -> LessonProgressModel:
    attempts = (
        await session.execute(
            select(LearnerAttemptModel)
            .where(LearnerAttemptModel.learning_instance_id == learning_instance_id)
            .order_by(LearnerAttemptModel.created_at.asc())
        )
    ).scalars().all()

    completed_interactions: list[str] = []
    completed_sections: list[str] = []
    score_earned = 0.0
    score_possible = 0.0
    for attempt in attempts:
        if attempt.assessment_mode == "graded":
            score_earned += float(attempt.score_earned)
            score_possible += float(attempt.score_possible)
        if attempt.interaction_id not in completed_interactions:
            # Any attempt counts toward "attempted" for completion; correct tracked separately.
            completed_interactions.append(attempt.interaction_id)
        if attempt.section_id and attempt.section_id not in completed_sections:
            completed_sections.append(attempt.section_id)

    progress = await session.scalar(
        select(LessonProgressModel).where(
            LessonProgressModel.learning_instance_id == learning_instance_id
        )
    )
    if progress is None:
        progress = LessonProgressModel(
            id=str(uuid.uuid4()),
            learning_instance_id=learning_instance_id,
            completed_section_ids=[],
            completed_interaction_ids=[],
            score_earned=0.0,
            score_possible=0.0,
            updated_at=_utcnow(),
        )
        session.add(progress)

    progress.completed_interaction_ids = completed_interactions
    progress.completed_section_ids = completed_sections
    progress.score_earned = score_earned
    progress.score_possible = score_possible
    progress.updated_at = _utcnow()
    await session.flush()
    return progress


async def rebuild_concept_states(session: AsyncSession, *, learner_id: str) -> list[ConceptStateModel]:
    existing = (
        await session.execute(
            select(ConceptStateModel).where(ConceptStateModel.learner_id == learner_id)
        )
    ).scalars().all()
    for row in existing:
        await session.delete(row)
    await session.flush()

    evidence = (
        await session.execute(
            select(ConceptEvidenceModel)
            .where(ConceptEvidenceModel.learner_id == learner_id)
            .order_by(ConceptEvidenceModel.created_at.asc())
        )
    ).scalars().all()

    buckets: dict[str, dict[str, Any]] = {}
    for row in evidence:
        bucket = buckets.setdefault(
            row.concept_id,
            {"earned": 0.0, "possible": 0.0, "first_success": None},
        )
        bucket["earned"] += float(row.score_earned)
        bucket["possible"] += float(row.score_possible)
        if bucket["first_success"] is None:
            bucket["first_success"] = float(row.score_earned) >= float(row.score_possible) > 0

    rebuilt: list[ConceptStateModel] = []
    for concept_id, data in buckets.items():
        state = ConceptStateModel(
            id=str(uuid.uuid4()),
            learner_id=learner_id,
            concept_id=concept_id,
            classification=classify_concept(data["earned"], data["possible"]),
            score_earned=data["earned"],
            score_possible=data["possible"],
            first_attempt_success=data["first_success"],
            updated_at=_utcnow(),
        )
        session.add(state)
        rebuilt.append(state)
    await session.flush()
    return rebuilt


async def complete_instance(
    session: AsyncSession,
    learning_instance_id: str,
    *,
    enforce_v1: bool = True,
) -> LearningInstanceModel:
    instance = await session.get(LearningInstanceModel, learning_instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")

    if enforce_v1:
        release = await session.get(LearnReleaseModel, instance.learn_release_id)
        document = (
            release.document_json
            if release is not None and isinstance(release.document_json, dict)
            else {}
        )
        required_sections, required_interactions = extract_v1_requirements(document)
        progress = await rebuild_progress(session, learning_instance_id)
        done_sections = set(progress.completed_section_ids or [])
        done_interactions = set(progress.completed_interaction_ids or [])
        missing_sections = sorted(required_sections - done_sections)
        missing_interactions = sorted(required_interactions - done_interactions)
        if missing_sections or missing_interactions:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "V1 completion requires required sections done and graded interactions attempted",
                    "missing_sections": missing_sections,
                    "missing_interactions": missing_interactions,
                },
            )

    instance.status = "completed"
    instance.completed_at = _utcnow()
    instance.updated_at = _utcnow()
    await session.flush()
    return instance

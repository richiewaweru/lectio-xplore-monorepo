"""Learn runtime services: instances, attempts, progress, evidence, sessions (Phases 06–07)."""

from __future__ import annotations

import json
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import LearnReleaseModel
from learn.runtime.evaluation import (
    UnknownInteractionError,
    concept_bindings_from_contract,
    evaluate_interaction,
    find_interaction_in_document,
    is_complete,
    score_aggregation_of,
)
from learn.runtime.evaluation import (
    InteractionConfigError,
    InteractionResponseError,
)
from learn.runtime_models import (
    ConceptEvidenceModel,
    ConceptStateModel,
    LearnAssignmentModel,
    LearnAssignmentRecipientModel,
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


def _canonical_response(response_json: dict[str, Any]) -> str:
    return json.dumps(response_json, sort_keys=True, separators=(",", ":"), default=str)


def _select_aggregated(attempts: list[LearnerAttemptModel], policy: str) -> LearnerAttemptModel | None:
    if not attempts:
        return None
    ordered = sorted(attempts, key=lambda a: a.created_at)
    if policy == "first":
        return ordered[0]
    if policy == "best":
        return max(
            ordered,
            key=lambda a: (
                float(a.score_earned) / float(a.score_possible) if float(a.score_possible) > 0 else 0.0,
                float(a.score_earned),
            ),
        )
    return ordered[-1]  # latest


def score_split(
    attempts: list[LearnerAttemptModel],
    *,
    contracts_by_interaction: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, float | int]]:
    """Aggregate scores without silently inflating numerator/denominator on retries."""
    contracts_by_interaction = contracts_by_interaction or {}
    by_mode_interaction: dict[str, dict[str, list[LearnerAttemptModel]]] = {
        "graded": defaultdict(list),
        "practice": defaultdict(list),
    }
    for attempt in attempts:
        mode = "practice" if attempt.assessment_mode == "practice" else "graded"
        by_mode_interaction[mode][attempt.interaction_id].append(attempt)

    result: dict[str, dict[str, float | int]] = {}
    for mode, groups in by_mode_interaction.items():
        earned = 0.0
        possible = 0.0
        selected_count = 0
        for interaction_id, rows in groups.items():
            contract = contracts_by_interaction.get(interaction_id)
            policy = score_aggregation_of(contract)
            chosen = _select_aggregated(rows, policy)
            if chosen is None:
                continue
            earned += float(chosen.score_earned)
            possible += float(chosen.score_possible)
            selected_count += 1
        result[mode] = {
            "attempts": selected_count,
            "raw_attempts": sum(len(v) for v in groups.values()),
            "score_earned": earned,
            "score_possible": possible,
        }
    return result


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


def _contracts_index(document: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict):
        return {}
    blocks = document.get("blocks") if isinstance(document.get("blocks"), dict) else {}
    index: dict[str, dict[str, Any]] = {}
    for block_id, block in blocks.items():
        if not isinstance(block, dict):
            continue
        contract = block.get("learn_interaction") or block.get("interaction")
        if isinstance(contract, dict):
            cid = str(contract.get("id") or block.get("id") or block_id)
            index[cid] = contract
            index[str(block_id)] = contract
            if block.get("id"):
                index[str(block["id"])] = contract
    return index


async def _load_release_document(
    session: AsyncSession, learn_release_id: str
) -> tuple[LearnReleaseModel, dict[str, Any]]:
    release = await session.get(LearnReleaseModel, learn_release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="LearnRelease not found")
    document = release.document_json if isinstance(release.document_json, dict) else {}
    return release, document


async def assert_instance_access(
    session: AsyncSession,
    *,
    instance: LearningInstanceModel,
    token: str | None,
    require_session: bool = False,
) -> LearnerSessionModel | None:
    """Validate learner session ownership and assignment recipient when bound."""
    row: LearnerSessionModel | None = None
    if token:
        row = await require_learner_session_for(
            session, token=token, learner_id=instance.learner_id
        )
    elif require_session:
        raise HTTPException(status_code=401, detail="Learner session required")

    if instance.assignment_id:
        recipient = await session.scalar(
            select(LearnAssignmentRecipientModel).where(
                LearnAssignmentRecipientModel.assignment_id == instance.assignment_id,
                LearnAssignmentRecipientModel.learner_id == instance.learner_id,
            )
        )
        if recipient is None:
            raise HTTPException(
                status_code=403,
                detail="Learner is not a recipient of this assignment",
            )
        assignment = await session.get(LearnAssignmentModel, instance.assignment_id)
        if assignment is not None and assignment.learn_release_id != instance.learn_release_id:
            raise HTTPException(
                status_code=409,
                detail="Instance release does not match assignment release",
            )
    return row


async def submit_attempt(
    session: AsyncSession,
    *,
    learning_instance_id: str,
    interaction_id: str,
    client_submission_id: str,
    response_json: dict[str, Any],
    section_id: str | None = None,
    expected_release_id: str | None = None,
) -> tuple[LearnerAttemptModel, dict[str, Any], bool]:
    """Server-authoritative attempt write.

    Loads evaluation/assessment/concept bindings from the immutable release.
    Idempotent by (instance, client_submission_id); same key with a different
    response is a conflict. Concurrent submissions cannot bypass max attempts.
    Returns (attempt, evaluation_payload, created).
    """
    # Lock the instance row so attempt-policy checks are serialized.
    instance = await session.scalar(
        select(LearningInstanceModel)
        .where(LearningInstanceModel.id == learning_instance_id)
        .with_for_update()
    )
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")

    release, document = await _load_release_document(session, instance.learn_release_id)
    if expected_release_id and expected_release_id != release.id:
        raise HTTPException(status_code=409, detail="Release identity mismatch")

    try:
        contract, contract_section_id = find_interaction_in_document(document, interaction_id)
    except UnknownInteractionError as exc:
        raise HTTPException(status_code=404, detail="Unknown interaction_id for release") from exc

    resolved_section = section_id or contract_section_id
    if section_id and contract_section_id and section_id != contract_section_id:
        raise HTTPException(status_code=422, detail="section_id does not match release membership")

    existing = await session.scalar(
        select(LearnerAttemptModel).where(
            LearnerAttemptModel.learning_instance_id == learning_instance_id,
            LearnerAttemptModel.client_submission_id == client_submission_id,
        )
    )
    if existing is not None:
        if _canonical_response(existing.response_json or {}) != _canonical_response(response_json):
            raise HTTPException(
                status_code=409,
                detail="Idempotency conflict: same submission key with different response",
            )
        payload = {
            "outcome": existing.outcome,
            "score_earned": existing.score_earned,
            "score_possible": existing.score_possible,
            "feedback": "",
            "completed": False,
            "assessment_mode": existing.assessment_mode,
            "idempotent_replay": True,
        }
        try:
            # Refresh feedback text from release without trusting stored client fields.
            re_eval = evaluate_interaction(contract, existing.response_json)
            payload["feedback"] = re_eval.feedback
            payload["completed"] = is_complete(re_eval, contract.get("completion"))
        except (InteractionConfigError, InteractionResponseError):
            pass
        return existing, payload, False

    prior = (
        await session.execute(
            select(LearnerAttemptModel)
            .where(
                LearnerAttemptModel.learning_instance_id == learning_instance_id,
                LearnerAttemptModel.interaction_id == interaction_id,
            )
            .order_by(LearnerAttemptModel.created_at.asc())
        )
    ).scalars().all()

    attempt_policy = contract.get("attempt_policy") if isinstance(contract.get("attempt_policy"), dict) else {}
    max_attempts = attempt_policy.get("max_attempts")
    if max_attempts is not None:
        try:
            max_n = int(max_attempts)
        except (TypeError, ValueError):
            max_n = 0
        if max_n > 0 and len(prior) >= max_n:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Maximum attempts exceeded",
                    "max_attempts": max_n,
                    "attempt_count": len(prior),
                },
            )

    if (
        attempt_policy.get("allow_retry_after_correct") is False
        and prior
        and prior[-1].outcome == "correct"
    ):
        raise HTTPException(status_code=422, detail="Retry after correct is not allowed")

    try:
        evaluation = evaluate_interaction(contract, response_json)
    except InteractionConfigError as exc:
        raise HTTPException(status_code=422, detail=f"Interaction config error: {exc}") from exc
    except InteractionResponseError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "code": exc.code},
        ) from exc

    assessment_mode = str(contract.get("assessment_mode") or "graded")
    if assessment_mode not in {"graded", "practice"}:
        assessment_mode = "graded"

    attempt = LearnerAttemptModel(
        id=str(uuid.uuid4()),
        learning_instance_id=learning_instance_id,
        interaction_id=str(contract.get("id") or interaction_id),
        section_id=resolved_section,
        client_submission_id=client_submission_id,
        assessment_mode=assessment_mode,
        outcome=evaluation.outcome,
        score_earned=float(evaluation.score_earned),
        score_possible=float(evaluation.score_possible),
        response_json=response_json,
        created_at=_utcnow(),
    )
    session.add(attempt)
    await session.flush()

    completed = is_complete(evaluation, contract.get("completion"))
    bindings = concept_bindings_from_contract(
        contract, interaction_id=str(contract.get("id") or interaction_id)
    )
    for binding in bindings:
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
                score_earned=float(evaluation.score_earned) * weight,
                score_possible=float(evaluation.score_possible) * weight,
                misconception_id=binding.get("misconception_id"),
                created_at=_utcnow(),
            )
        )
    if bindings:
        await session.flush()
        await rebuild_concept_states(session, learner_id=instance.learner_id)

    if resolved_section:
        instance.current_section_id = resolved_section
    instance.updated_at = _utcnow()

    progress = await rebuild_progress(session, learning_instance_id)
    instance.score_earned = float(progress.score_earned or 0)
    instance.score_possible = float(progress.score_possible or 0)
    await session.flush()

    payload = {
        "outcome": evaluation.outcome,
        "score_earned": evaluation.score_earned,
        "score_possible": evaluation.score_possible,
        "feedback": evaluation.feedback,
        "completed": completed,
        "assessment_mode": assessment_mode,
        "idempotent_replay": False,
        "score_aggregation": score_aggregation_of(contract),
    }
    return attempt, payload, True


async def mark_section_passive_complete(
    session: AsyncSession,
    *,
    learning_instance_id: str,
    section_id: str,
) -> LessonProgressModel:
    """Visit/passive completion without inventing graded LearnerAttempt rows."""
    instance = await session.get(LearningInstanceModel, learning_instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="LearningInstance not found")
    _, document = await _load_release_document(session, instance.learn_release_id)
    section_ids = {
        str(s.get("id"))
        for s in (document.get("sections") or [])
        if isinstance(s, dict) and s.get("id")
    }
    if section_id not in section_ids:
        raise HTTPException(status_code=404, detail="Unknown section_id for release")

    progress = await rebuild_progress(session, learning_instance_id)
    completed = list(progress.completed_section_ids or [])
    if section_id not in completed:
        completed.append(section_id)
        progress.completed_section_ids = completed
        progress.updated_at = _utcnow()
    instance.current_section_id = section_id
    instance.updated_at = _utcnow()
    await session.flush()
    return progress


async def rebuild_progress(session: AsyncSession, learning_instance_id: str) -> LessonProgressModel:
    instance = await session.get(LearningInstanceModel, learning_instance_id)
    document: dict[str, Any] = {}
    if instance is not None:
        _, document = await _load_release_document(session, instance.learn_release_id)
    contracts = _contracts_index(document)

    attempts = (
        await session.execute(
            select(LearnerAttemptModel)
            .where(LearnerAttemptModel.learning_instance_id == learning_instance_id)
            .order_by(LearnerAttemptModel.created_at.asc())
        )
    ).scalars().all()

    completed_interactions: list[str] = []
    completed_sections: list[str] = []
    by_interaction: dict[str, list[LearnerAttemptModel]] = defaultdict(list)
    for attempt in attempts:
        by_interaction[attempt.interaction_id].append(attempt)
        if attempt.section_id and attempt.section_id not in completed_sections:
            # Graded/practice attempt still marks section visited; passive uses mark_section.
            completed_sections.append(attempt.section_id)

    for interaction_id, rows in by_interaction.items():
        contract = contracts.get(interaction_id) or {}
        policy = score_aggregation_of(contract)
        chosen = _select_aggregated(rows, policy)
        if chosen is None:
            continue
        # Build a synthetic EvaluationResult for completion check.
        from learn.runtime.evaluation import EvaluationResult

        result = EvaluationResult(
            outcome=chosen.outcome,
            score_earned=float(chosen.score_earned),
            score_possible=float(chosen.score_possible),
            feedback="",
        )
        if is_complete(result, contract.get("completion") if contract else {"type": "submitted"}):
            if interaction_id not in completed_interactions:
                completed_interactions.append(interaction_id)

    scores = score_split(list(attempts), contracts_by_interaction=contracts)
    score_earned = float(scores["graded"]["score_earned"])
    score_possible = float(scores["graded"]["score_possible"])

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

    # Preserve passively completed sections that have no attempt yet.
    prior_sections = list(progress.completed_section_ids or [])
    merged_sections = list(dict.fromkeys([*prior_sections, *completed_sections]))

    progress.completed_interaction_ids = completed_interactions
    progress.completed_section_ids = merged_sections
    progress.score_earned = score_earned
    progress.score_possible = score_possible
    progress.updated_at = _utcnow()
    await session.flush()

    if instance is not None:
        instance.score_earned = score_earned
        instance.score_possible = score_possible
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

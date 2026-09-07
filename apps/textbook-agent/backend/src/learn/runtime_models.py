"""Learn runtime domain models (Phases 06–09). Additive; no LearnDocument mutation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from core.database.models import Base, JSON_DOCUMENT_TYPE, _utcnow


class LearnerIdentityModel(Base):
    """Learner identity that does not require email/account (Phase 06)."""

    __tablename__ = "learner_identities"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    invite_code = Column(String, nullable=True, unique=True, index=True)
    created_by_teacher_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class LearnerSessionModel(Base):
    """Opaque learner session token (no email). Header: X-Learner-Session."""

    __tablename__ = "learner_sessions"

    id = Column(String, primary_key=True)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=_utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)


class LearningInstanceModel(Base):
    """Runtime context bridge for one learner executing one release (Phase 06)."""

    __tablename__ = "learning_instances"
    __table_args__ = (
        Index("ix_learning_instances_learner_release", "learner_id", "learn_release_id"),
    )

    id = Column(String, primary_key=True)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=False, index=True)
    learn_release_id = Column(String, ForeignKey("learn_releases.id"), nullable=False, index=True)
    assignment_id = Column(String, ForeignKey("learn_assignments.id"), nullable=True, index=True)
    status = Column(String, nullable=False, default="active", server_default="active")
    current_section_id = Column(String, nullable=True)
    score_earned = Column(Float, nullable=False, default=0.0, server_default="0")
    score_possible = Column(Float, nullable=False, default=0.0, server_default="0")
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class LearnerAttemptModel(Base):
    """Immutable learner attempt rows (Phase 06)."""

    __tablename__ = "learner_attempts"
    __table_args__ = (
        UniqueConstraint(
            "learning_instance_id",
            "client_submission_id",
            name="uq_learner_attempts_instance_submission",
        ),
    )

    id = Column(String, primary_key=True)
    learning_instance_id = Column(
        String, ForeignKey("learning_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interaction_id = Column(String, nullable=False, index=True)
    section_id = Column(String, nullable=True)
    client_submission_id = Column(String, nullable=False)
    assessment_mode = Column(String, nullable=False, default="graded")
    outcome = Column(String, nullable=False)
    score_earned = Column(Float, nullable=False, default=0.0)
    score_possible = Column(Float, nullable=False, default=1.0)
    response_json = Column(JSON_DOCUMENT_TYPE, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class LessonProgressModel(Base):
    """Rebuildable progress projection from attempts (Phase 06)."""

    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("learning_instance_id", name="uq_lesson_progress_instance"),
    )

    id = Column(String, primary_key=True)
    learning_instance_id = Column(
        String, ForeignKey("learning_instances.id", ondelete="CASCADE"), nullable=False
    )
    completed_section_ids = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    completed_interaction_ids = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    score_earned = Column(Float, nullable=False, default=0.0)
    score_possible = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class ConceptEvidenceModel(Base):
    """Raw concept evidence rows (Phase 07). Projection-rebuildable."""

    __tablename__ = "concept_evidence"

    id = Column(String, primary_key=True)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=False, index=True)
    learning_instance_id = Column(String, ForeignKey("learning_instances.id"), nullable=False, index=True)
    attempt_id = Column(String, ForeignKey("learner_attempts.id"), nullable=False, index=True)
    learn_release_id = Column(String, ForeignKey("learn_releases.id"), nullable=False, index=True)
    path_lesson_id = Column(String, nullable=True)
    concept_id = Column(String, nullable=False, index=True)
    unit_id = Column(String, nullable=True)
    node_id = Column(String, nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    score_earned = Column(Float, nullable=False)
    score_possible = Column(Float, nullable=False)
    misconception_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class ConceptStateModel(Base):
    """Rebuildable concept-state projection (Phase 07)."""

    __tablename__ = "concept_states"
    __table_args__ = (
        UniqueConstraint("learner_id", "concept_id", name="uq_concept_state_learner_concept"),
    )

    id = Column(String, primary_key=True)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=False)
    concept_id = Column(String, nullable=False)
    classification = Column(String, nullable=False, default="Needs Practice")
    score_earned = Column(Float, nullable=False, default=0.0)
    score_possible = Column(Float, nullable=False, default=0.0)
    first_attempt_success = Column(Boolean, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class LearnClassModel(Base):
    """Teacher-owned class (Phase 08)."""

    __tablename__ = "learn_classes"

    id = Column(String, primary_key=True)
    teacher_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    invite_code = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class LearnClassMembershipModel(Base):
    """Learner or staff membership in a class (Phase 08)."""

    __tablename__ = "learn_class_memberships"
    __table_args__ = (
        UniqueConstraint("class_id", "learner_id", name="uq_class_membership"),
    )

    id = Column(String, primary_key=True)
    class_id = Column(String, ForeignKey("learn_classes.id", ondelete="CASCADE"), nullable=False)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=True)
    teacher_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False, default="learner", server_default="learner")
    # roles: owner | teacher | assistant | learner
    status = Column(String, nullable=False, default="active", server_default="active")
    joined_at = Column(DateTime, default=_utcnow, nullable=False)


class LearnAssignmentModel(Base):
    """Assignment of a LearnRelease (Phase 09). Multi-class via targets table."""

    __tablename__ = "learn_assignments"

    id = Column(String, primary_key=True)
    teacher_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    learn_release_id = Column(String, ForeignKey("learn_releases.id"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("learn_classes.id"), nullable=True, index=True)
    mode = Column(String, nullable=False, default="rolling")  # rolling | snapshot | selected
    title = Column(String, nullable=False)
    selected_learner_ids = Column(JSON_DOCUMENT_TYPE, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    closes_at = Column(DateTime, nullable=True)


class LearnAssignmentTargetModel(Base):
    """Assignment target: a class and/or individual learner (multi-class)."""

    __tablename__ = "learn_assignment_targets"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "class_id",
            "learner_id",
            name="uq_learn_assignment_target",
        ),
    )

    id = Column(String, primary_key=True)
    assignment_id = Column(
        String, ForeignKey("learn_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id = Column(String, ForeignKey("learn_classes.id"), nullable=True, index=True)
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class LearnAssignmentRecipientModel(Base):
    """Append-only recipient row — historical truth, not derived from live roster."""

    __tablename__ = "learn_assignment_recipients"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "learner_id",
            name="uq_learn_assignment_recipient",
        ),
    )

    id = Column(String, primary_key=True)
    assignment_id = Column(
        String, ForeignKey("learn_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learner_id = Column(String, ForeignKey("learner_identities.id"), nullable=False, index=True)
    class_id = Column(String, ForeignKey("learn_classes.id"), nullable=True)
    status = Column(String, nullable=False, default="assigned", server_default="assigned")
    # assigned | started | completed (+ overdue/excused-ready unused)
    learning_instance_id = Column(String, ForeignKey("learning_instances.id"), nullable=True)
    assigned_at = Column(DateTime, default=_utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    overdue_at = Column(DateTime, nullable=True)
    excused = Column(Boolean, nullable=False, default=False, server_default="false")

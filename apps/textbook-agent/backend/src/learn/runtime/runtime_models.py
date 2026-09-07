"""Compatibility shim — ORM classes live in `infra.database.models`."""

from __future__ import annotations

from infra.database.models import (  # noqa: F401
    ConceptEvidenceModel,
    ConceptStateModel,
    LearnAssignmentModel,
    LearnAssignmentRecipientModel,
    LearnAssignmentTargetModel,
    LearnClassMembershipModel,
    LearnClassModel,
    LearnerAttemptModel,
    LearnerIdentityModel,
    LearnerSessionModel,
    LearningInstanceModel,
    LessonProgressModel,
)

__all__ = [
    "ConceptEvidenceModel",
    "ConceptStateModel",
    "LearnAssignmentModel",
    "LearnAssignmentRecipientModel",
    "LearnAssignmentTargetModel",
    "LearnClassMembershipModel",
    "LearnClassModel",
    "LearnerAttemptModel",
    "LearnerIdentityModel",
    "LearnerSessionModel",
    "LearningInstanceModel",
    "LessonProgressModel",
]

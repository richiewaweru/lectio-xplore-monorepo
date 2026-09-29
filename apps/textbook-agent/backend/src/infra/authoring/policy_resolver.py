"""Package-owned knowledge and assessment policy resolution.

Deterministic: package defaults + optional task overrides → effective decision.
The model cannot authorize fallbacks or choose grading policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from infra.authoring.models import AuthoringEngineError

KnowledgePolicy = Literal["supplied_only", "supplied_preferred", "objective_development"]
AssessmentPolicy = Literal["automatic_required", "automatic_preferred", "teacher_review"]
InputAvailability = Literal[
    "supplied_statements",
    "intentionally_absent",
    "unresolved_references",
    "retrieval_failure",
    "legacy_unknown",
]
ExecutedKnowledgeMode = Literal[
    "supplied_facts",
    "model_knowledge",
    "objective_development",
    "convert_approved",
    "missing_context",
]
ExecutedEvaluationMode = Literal["accepted-answers", "teacher-review", "n/a"]

POLICY_VERSION = "1.0.0"
LEGACY_ABSENT_VERSION = "legacy-absent-v1"


@dataclass(frozen=True)
class PolicyDecision:
    """Resolved, persistable policy snapshot."""

    requested_knowledge_policy: KnowledgePolicy | None
    effective_knowledge_policy: KnowledgePolicy
    knowledge_policy_source: str
    requested_assessment_policy: AssessmentPolicy | None
    effective_assessment_policy: AssessmentPolicy | None
    assessment_policy_source: str | None
    policy_version: str
    input_availability: InputAvailability
    executed_knowledge_mode: ExecutedKnowledgeMode
    executed_evaluation_mode: ExecutedEvaluationMode | None
    fallback_reason: str | None
    definition_version: str | None
    definition_hash: str | None
    input_revision: str | None
    teacher_review_permitted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_knowledge_policy": self.requested_knowledge_policy,
            "effective_knowledge_policy": self.effective_knowledge_policy,
            "knowledge_policy_source": self.knowledge_policy_source,
            "requested_assessment_policy": self.requested_assessment_policy,
            "effective_assessment_policy": self.effective_assessment_policy,
            "assessment_policy_source": self.assessment_policy_source,
            "policy_version": self.policy_version,
            "input_availability": self.input_availability,
            "executed_knowledge_mode": self.executed_knowledge_mode,
            "executed_evaluation_mode": self.executed_evaluation_mode,
            "fallback_reason": self.fallback_reason,
            "definition_version": self.definition_version,
            "definition_hash": self.definition_hash,
            "input_revision": self.input_revision,
            "teacher_review_permitted": self.teacher_review_permitted,
        }


def _normalize_knowledge(value: Any) -> KnowledgePolicy | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text in {"supplied_only", "supplied_preferred", "objective_development"}:
        return text  # type: ignore[return-value]
    raise AuthoringEngineError(
        "POLICY_CONFLICT",
        f"unsupported knowledge policy {text!r}",
        stage="policy",
        retryable=False,
    )


def _normalize_assessment(value: Any) -> AssessmentPolicy | None:
    if value is None or value == "":
        return None
    text = str(value).strip().replace("-", "_")
    aliases = {
        "accepted_answers": "automatic_required",
        "accepted-answers": "automatic_required",
        "teacher-review": "teacher_review",
        "automatic_required": "automatic_required",
        "automatic_preferred": "automatic_preferred",
        "teacher_review": "teacher_review",
    }
    mapped = aliases.get(text)
    if mapped in {"automatic_required", "automatic_preferred", "teacher_review"}:
        return mapped  # type: ignore[return-value]
    raise AuthoringEngineError(
        "POLICY_CONFLICT",
        f"unsupported assessment policy {text!r}",
        stage="policy",
        retryable=False,
    )


def read_legacy_policy_snapshot(
    provenance: Mapping[str, Any] | None,
) -> PolicyDecision | None:
    """Read persisted snapshot when present."""
    if not isinstance(provenance, Mapping):
        return None
    snap = provenance.get("policy")
    if isinstance(snap, Mapping) and snap.get("policy_version"):
        return PolicyDecision(
            requested_knowledge_policy=_normalize_knowledge(snap.get("requested_knowledge_policy")),
            effective_knowledge_policy=_normalize_knowledge(snap.get("effective_knowledge_policy"))
            or "supplied_preferred",
            knowledge_policy_source=str(snap.get("knowledge_policy_source") or LEGACY_ABSENT_VERSION),
            requested_assessment_policy=_normalize_assessment(snap.get("requested_assessment_policy")),
            effective_assessment_policy=_normalize_assessment(snap.get("effective_assessment_policy")),
            assessment_policy_source=(
                str(snap["assessment_policy_source"])
                if snap.get("assessment_policy_source") is not None
                else None
            ),
            policy_version=str(snap.get("policy_version") or LEGACY_ABSENT_VERSION),
            input_availability=str(snap.get("input_availability") or "legacy_unknown"),  # type: ignore[arg-type]
            executed_knowledge_mode=str(snap.get("executed_knowledge_mode") or "model_knowledge"),  # type: ignore[arg-type]
            executed_evaluation_mode=snap.get("executed_evaluation_mode"),  # type: ignore[arg-type]
            fallback_reason=snap.get("fallback_reason"),
            definition_version=snap.get("definition_version"),
            definition_hash=snap.get("definition_hash"),
            input_revision=snap.get("input_revision"),
            teacher_review_permitted=bool(snap.get("teacher_review_permitted")),
        )
    return None


def knowledge_instruction_block(decision: PolicyDecision) -> str:
    """Prompt fragment distinguishing supplied-only vs model-knowledge modes."""
    if decision.executed_knowledge_mode == "convert_approved":
        return (
            "Conversion mode: preserve approved source material. Do not invent facts "
            "or describe model knowledge as approved factual material."
        )
    if decision.effective_knowledge_policy == "supplied_only":
        return (
            "Knowledge policy: supplied_only. Write strictly within the supplied facts "
            "and terminology. If required factual context is absent, do not invent "
            "statements; report missing input."
        )
    if decision.effective_knowledge_policy == "objective_development":
        return (
            "Knowledge policy: objective_development. Develop the objective using "
            "scoped model knowledge while respecting any supplied material and "
            "constraints. Do not describe model knowledge as approved factual material."
        )
    if decision.input_availability == "supplied_statements":
        return (
            "Knowledge policy: supplied_preferred. Use supplied facts as the primary "
            "basis; you may add relevant model knowledge within the objective and "
            "constraints. Do not describe model knowledge as approved factual material."
        )
    return (
        "Knowledge policy: supplied_preferred. No facts were supplied by design. "
        "Generate from the objective and scoped model knowledge within constraints. "
        "Do not invent an approval claim or treat model knowledge as approved facts."
    )


__all__ = [
    "LEGACY_ABSENT_VERSION",
    "POLICY_VERSION",
    "AssessmentPolicy",
    "ExecutedEvaluationMode",
    "ExecutedKnowledgeMode",
    "InputAvailability",
    "KnowledgePolicy",
    "PolicyDecision",
    "knowledge_instruction_block",
    "read_legacy_policy_snapshot",
]

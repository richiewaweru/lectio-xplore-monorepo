"""Package-owned knowledge and assessment policy resolution.

Deterministic: package defaults + optional task overrides → effective decision.
The model cannot authorize fallbacks or choose grading policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

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

_DEFAULT_KNOWLEDGE_SUPPORTED: tuple[KnowledgePolicy, ...] = (
    "supplied_only",
    "supplied_preferred",
    "objective_development",
)
_DEFAULT_ASSESSMENT_SUPPORTED: tuple[AssessmentPolicy, ...] = (
    "automatic_required",
    "automatic_preferred",
    "teacher_review",
)


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


def knowledge_defaults_for_capability(
    *,
    capability_id: str,
    native_path: str,
    modes: Sequence[str],
    raw_definition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Package knowledge block, with defaults when definition omits it."""
    raw = dict(raw_definition or {})
    declared = raw.get("knowledge") if isinstance(raw.get("knowledge"), Mapping) else {}
    default = str(declared.get("default") or "supplied_preferred")
    supported_raw = declared.get("supported")
    if isinstance(supported_raw, Sequence) and not isinstance(supported_raw, (str, bytes)):
        supported = tuple(str(item) for item in supported_raw)
    else:
        supported = _DEFAULT_KNOWLEDGE_SUPPORTED
    if native_path == "print" and set(modes) == {"convert-approved"}:
        default = str(declared.get("default") or "supplied_only")
        if not supported_raw:
            supported = ("supplied_only",)
    return {
        "default": default,
        "supported": list(supported),
        "capability_id": capability_id,
    }


def assessment_defaults_for_capability(
    *,
    capability_id: str,
    raw_definition: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Package assessment block for Learn interactions; None for content/Print."""
    raw = dict(raw_definition or {})
    if capability_id != "short-response" and "assessment" not in raw:
        if capability_id in {
            "choice",
            "multi-select",
            "fill-blank",
            "numeric",
            "match-pairs",
            "classify",
            "sequence",
        }:
            return {
                "default": "automatic_required",
                "supported": ["automatic_required"],
                "teacher_review_permitted": False,
            }
        return None
    declared = raw.get("assessment") if isinstance(raw.get("assessment"), Mapping) else {}
    if capability_id == "short-response":
        default = str(declared.get("default") or "automatic_preferred")
        supported_raw = declared.get("supported")
        if isinstance(supported_raw, Sequence) and not isinstance(supported_raw, (str, bytes)):
            supported = [str(item) for item in supported_raw]
        else:
            supported = list(_DEFAULT_ASSESSMENT_SUPPORTED)
        permitted = declared.get("teacher_review_permitted")
        if permitted is None:
            permitted = "teacher_review" in supported or default in {
                "automatic_preferred",
                "teacher_review",
            }
        return {
            "default": default,
            "supported": supported,
            "teacher_review_permitted": bool(permitted),
        }
    if not declared:
        return None
    return {
        "default": str(declared.get("default") or "automatic_required"),
        "supported": list(declared.get("supported") or ["automatic_required"]),
        "teacher_review_permitted": bool(declared.get("teacher_review_permitted") or False),
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


def classify_input_availability(
    *,
    allowed_facts: Sequence[str] | None,
    referenced_fact_ids: Sequence[str] | None = None,
    unresolved_fact_ids: Sequence[str] | None = None,
    retrieval_failed: bool = False,
    legacy_absent: bool = False,
) -> InputAvailability:
    if retrieval_failed:
        return "retrieval_failure"
    if unresolved_fact_ids:
        return "unresolved_references"
    facts = [str(f).strip() for f in (allowed_facts or []) if str(f).strip()]
    if facts:
        return "supplied_statements"
    if referenced_fact_ids:
        return "unresolved_references"
    if legacy_absent:
        return "legacy_unknown"
    return "intentionally_absent"


def resolve_authoring_policy(
    *,
    capability_id: str,
    native_path: str,
    modes: Sequence[str],
    authoring_mode: str,
    raw_definition: Mapping[str, Any] | None = None,
    requested_knowledge_policy: Any = None,
    requested_assessment_policy: Any = None,
    allowed_facts: Sequence[str] | None = None,
    referenced_fact_ids: Sequence[str] | None = None,
    unresolved_fact_ids: Sequence[str] | None = None,
    retrieval_failed: bool = False,
    legacy_absent: bool = False,
    definition_version: str | None = None,
    definition_hash: str | None = None,
    input_revision: str | None = None,
    approved_item_assessment: Any = None,
) -> PolicyDecision:
    """Resolve effective knowledge/assessment policy for one work order."""
    knowledge_pkg = knowledge_defaults_for_capability(
        capability_id=capability_id,
        native_path=native_path,
        modes=modes,
        raw_definition=raw_definition,
    )
    assessment_pkg = assessment_defaults_for_capability(
        capability_id=capability_id,
        raw_definition=raw_definition,
    )

    supported_k = set(knowledge_pkg["supported"])
    requested_k = _normalize_knowledge(requested_knowledge_policy)
    if requested_k is not None and requested_k not in supported_k:
        raise AuthoringEngineError(
            "POLICY_CONFLICT",
            f"knowledge policy {requested_k!r} is not supported by {capability_id}",
            stage="policy",
            retryable=False,
        )
    default_k = _normalize_knowledge(knowledge_pkg["default"])
    assert default_k is not None
    if default_k not in supported_k:
        raise AuthoringEngineError(
            "POLICY_CONFLICT",
            f"package default knowledge {default_k!r} not in supported set",
            stage="policy",
            retryable=False,
        )
    if legacy_absent and requested_k is None:
        effective_k: KnowledgePolicy = "supplied_preferred"
        k_source = LEGACY_ABSENT_VERSION
    elif requested_k is not None:
        effective_k = requested_k
        k_source = "task"
    else:
        effective_k = default_k
        k_source = f"package:{POLICY_VERSION}"

    availability = classify_input_availability(
        allowed_facts=allowed_facts,
        referenced_fact_ids=referenced_fact_ids,
        unresolved_fact_ids=unresolved_fact_ids,
        retrieval_failed=retrieval_failed,
        legacy_absent=legacy_absent,
    )

    executed_k: ExecutedKnowledgeMode
    if authoring_mode == "convert-approved":
        executed_k = "convert_approved"
    elif availability in {"unresolved_references", "retrieval_failure"}:
        executed_k = "missing_context"
    elif availability == "supplied_statements":
        if effective_k == "objective_development":
            executed_k = "objective_development"
        else:
            executed_k = "supplied_facts"
    elif effective_k == "supplied_only":
        executed_k = "missing_context"
    elif effective_k == "objective_development":
        executed_k = "objective_development"
    else:
        executed_k = "model_knowledge"

    requested_a = _normalize_assessment(requested_assessment_policy)
    item_a = _normalize_assessment(approved_item_assessment)
    effective_a: AssessmentPolicy | None = None
    a_source: str | None = None
    teacher_permitted = False
    executed_eval: ExecutedEvaluationMode | None = None
    fallback_reason: str | None = None

    if assessment_pkg is not None:
        supported_a = set(assessment_pkg["supported"])
        teacher_permitted = bool(assessment_pkg.get("teacher_review_permitted"))
        default_a = _normalize_assessment(assessment_pkg["default"])
        assert default_a is not None
        if requested_a is not None:
            if requested_a not in supported_a:
                raise AuthoringEngineError(
                    "POLICY_CONFLICT",
                    f"assessment policy {requested_a!r} is not supported by {capability_id}",
                    stage="policy",
                    retryable=False,
                )
            effective_a = requested_a
            a_source = "task"
        elif item_a is not None:
            if item_a not in supported_a:
                raise AuthoringEngineError(
                    "POLICY_CONFLICT",
                    f"approved-item assessment {item_a!r} is not supported by {capability_id}",
                    stage="policy",
                    retryable=False,
                )
            effective_a = item_a
            a_source = "approved_item"
        elif legacy_absent:
            effective_a = default_a
            a_source = LEGACY_ABSENT_VERSION
        else:
            effective_a = default_a
            a_source = f"package:{POLICY_VERSION}"

        if effective_a == "teacher_review" and not teacher_permitted:
            raise AuthoringEngineError(
                "POLICY_CONFLICT",
                "teacher_review is not permitted for this capability",
                stage="policy",
                retryable=False,
            )
        if requested_a is not None and item_a is not None and requested_a != item_a:
            raise AuthoringEngineError(
                "POLICY_CONFLICT",
                f"task assessment {requested_a!r} conflicts with approved item {item_a!r}",
                stage="policy",
                retryable=False,
            )

        if effective_a == "teacher_review":
            executed_eval = "teacher-review"
        elif effective_a in {"automatic_required", "automatic_preferred"}:
            executed_eval = "accepted-answers"
        else:
            executed_eval = "n/a"

    return PolicyDecision(
        requested_knowledge_policy=requested_k,
        effective_knowledge_policy=effective_k,
        knowledge_policy_source=k_source,
        requested_assessment_policy=requested_a,
        effective_assessment_policy=effective_a,
        assessment_policy_source=a_source,
        policy_version=POLICY_VERSION,
        input_availability=availability,
        executed_knowledge_mode=executed_k,
        executed_evaluation_mode=executed_eval,
        fallback_reason=fallback_reason,
        definition_version=definition_version,
        definition_hash=definition_hash,
        input_revision=input_revision,
        teacher_review_permitted=teacher_permitted,
    )


def with_assessment_fallback(
    decision: PolicyDecision,
    *,
    accepted_answers_present: bool,
    review_guidance: str | None = None,
) -> PolicyDecision:
    """Apply authorized missing-answer fallback for ShortResponse convert."""
    if decision.effective_assessment_policy is None:
        return decision
    if accepted_answers_present:
        return PolicyDecision(
            requested_knowledge_policy=decision.requested_knowledge_policy,
            effective_knowledge_policy=decision.effective_knowledge_policy,
            knowledge_policy_source=decision.knowledge_policy_source,
            requested_assessment_policy=decision.requested_assessment_policy,
            effective_assessment_policy=decision.effective_assessment_policy,
            assessment_policy_source=decision.assessment_policy_source,
            policy_version=decision.policy_version,
            input_availability=decision.input_availability,
            executed_knowledge_mode=decision.executed_knowledge_mode,
            executed_evaluation_mode="accepted-answers",
            fallback_reason=None,
            definition_version=decision.definition_version,
            definition_hash=decision.definition_hash,
            input_revision=decision.input_revision,
            teacher_review_permitted=decision.teacher_review_permitted,
        )

    policy = decision.effective_assessment_policy
    if policy == "automatic_required":
        raise AuthoringEngineError(
            "INCOMPATIBLE_APPROVED_ITEM",
            "automatic_required assessment requires accepted answers; teacher-review fallback is not authorized",
            stage="convert",
            retryable=False,
        )
    if policy == "teacher_review":
        if not str(review_guidance or "").strip():
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                "teacher_review requires non-empty review_guidance",
                stage="convert",
                retryable=False,
            )
        return PolicyDecision(
            requested_knowledge_policy=decision.requested_knowledge_policy,
            effective_knowledge_policy=decision.effective_knowledge_policy,
            knowledge_policy_source=decision.knowledge_policy_source,
            requested_assessment_policy=decision.requested_assessment_policy,
            effective_assessment_policy=policy,
            assessment_policy_source=decision.assessment_policy_source,
            policy_version=decision.policy_version,
            input_availability=decision.input_availability,
            executed_knowledge_mode=decision.executed_knowledge_mode,
            executed_evaluation_mode="teacher-review",
            fallback_reason=None,
            definition_version=decision.definition_version,
            definition_hash=decision.definition_hash,
            input_revision=decision.input_revision,
            teacher_review_permitted=decision.teacher_review_permitted,
        )
    if policy == "automatic_preferred":
        if not decision.teacher_review_permitted:
            raise AuthoringEngineError(
                "POLICY_CONFLICT",
                "automatic_preferred fallback to teacher-review is not permitted",
                stage="policy",
                retryable=False,
            )
        if not str(review_guidance or "").strip():
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                "teacher-review fallback requires non-empty review_guidance",
                stage="convert",
                retryable=False,
            )
        return PolicyDecision(
            requested_knowledge_policy=decision.requested_knowledge_policy,
            effective_knowledge_policy=decision.effective_knowledge_policy,
            knowledge_policy_source=decision.knowledge_policy_source,
            requested_assessment_policy=decision.requested_assessment_policy,
            effective_assessment_policy=policy,
            assessment_policy_source=decision.assessment_policy_source,
            policy_version=decision.policy_version,
            input_availability=decision.input_availability,
            executed_knowledge_mode=decision.executed_knowledge_mode,
            executed_evaluation_mode="teacher-review",
            fallback_reason="missing_accepted_answers_automatic_preferred",
            definition_version=decision.definition_version,
            definition_hash=decision.definition_hash,
            input_revision=decision.input_revision,
            teacher_review_permitted=decision.teacher_review_permitted,
        )
    raise AuthoringEngineError(
        "POLICY_CONFLICT",
        f"cannot resolve missing-answer behavior for {policy!r}",
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
    "AssessmentPolicy",
    "ExecutedEvaluationMode",
    "ExecutedKnowledgeMode",
    "InputAvailability",
    "KnowledgePolicy",
    "LEGACY_ABSENT_VERSION",
    "POLICY_VERSION",
    "PolicyDecision",
    "assessment_defaults_for_capability",
    "classify_input_availability",
    "knowledge_defaults_for_capability",
    "knowledge_instruction_block",
    "read_legacy_policy_snapshot",
    "resolve_authoring_policy",
    "with_assessment_fallback",
]

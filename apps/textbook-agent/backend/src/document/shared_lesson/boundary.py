"""Bounded semantic validation and repair for one shared lesson boundary.

The deterministic continuity checks are always the first gate.  A semantic
review may add one typed issue, but it never rewrites a section.  If a repair
is needed, the caller supplies the exact accepted ``SectionWriterRequest``;
the repair adapter is called once for the affected section and the boundary is
checked once more.  The other accepted section is returned unchanged.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.composer import SectionCompositionPlan
from document.shared_lesson.continuity import (
    ContinuityIssue,
    ExpectedNodeShape,
    validate_section_boundary,
    validate_section_continuity,
)
from document.shared_lesson.models import SharedLessonNode, SharedSection
from document.shared_lesson.writer import (
    SectionWriteResult,
    SectionWriterRequest,
    SectionWriteValidationError,
    _default_provider,
    _request_payload,
    validate_and_build_section,
)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundarySemanticRequest(_ClosedModel):
    """The narrow context exposed to a semantic boundary reviewer."""

    previous_plan: TeachingPlanSection
    previous_exit_state: tuple[str, ...]
    previous_final_nodes: tuple[SharedLessonNode, ...]
    next_plan: TeachingPlanSection
    next_entry_state: tuple[str, ...]
    next_bridge: str | None
    next_first_nodes: tuple[SharedLessonNode, ...]


class BoundarySemanticVerdict(_ClosedModel):
    """Closed reviewer output: exactly PASS or one typed continuity issue."""

    status: Literal["pass", "issue"]
    issue: ContinuityIssue | None = None

    @model_validator(mode="after")
    def _match_status(self) -> BoundarySemanticVerdict:
        if self.status == "pass" and self.issue is not None:
            raise ValueError("a passing boundary verdict cannot carry an issue")
        if self.status == "issue" and self.issue is None:
            raise ValueError("an issue boundary verdict must carry one issue")
        return self


class BoundaryRepairRequest(_ClosedModel):
    """One targeted repair request with the original composition contract."""

    target_section_id: str = Field(min_length=1)
    writer_request: SectionWriterRequest
    issues: tuple[ContinuityIssue, ...] = Field(min_length=1)
    previous_section: SharedSection
    next_section: SharedSection

    @model_validator(mode="after")
    def _target_matches_writer_request(self) -> BoundaryRepairRequest:
        if self.writer_request.section.slot_id != self.target_section_id:
            raise ValueError("writer request must belong to the targeted section")
        if self.target_section_id not in {
            self.previous_section.id,
            self.next_section.id,
        }:
            raise ValueError("target section must be one side of this boundary")
        if any(issue.affected_section_id != self.target_section_id for issue in self.issues):
            raise ValueError("targeted repair issues must belong to the target section")
        return self


class BoundaryRepairEngine(Protocol):
    async def repair_section(
        self, request: BoundaryRepairRequest
    ) -> SharedSection | SectionWriteResult:
        """Return only the affected section using the existing writer stack."""


class BoundarySemanticValidator(Protocol):
    async def __call__(self, request: BoundarySemanticRequest) -> BoundarySemanticVerdict | Any:
        """Return one closed semantic verdict without a rewrite."""


class BoundarySemanticOutputError(ValueError):
    """The provider returned a value outside the closed semantic contract."""


_INTERNAL_REVIEW_TEXT = re.compile(
    r"\b(?:teaching[_ -]?block[_ -]?id|task[_ -]?spec[_ -]?id|section[_ -]?slot|"
    r"composition[_ -]?plan|semantic[_ -]?role|source[_ -]?ids?|renderer|"
    r"learn widget|print page|model planning)\b",
    re.IGNORECASE,
)


class BoundaryValidationResult(_ClosedModel):
    """Result retaining both accepted siblings and any recoverable failure."""

    status: Literal["pass", "recoverable_failure"]
    previous_section: SharedSection
    next_section: SharedSection
    issues: tuple[ContinuityIssue, ...] = ()
    initial_issues: tuple[ContinuityIssue, ...] = ()
    repair_attempted: bool = False
    semantic_calls: int = 0
    failure_code: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass" and not self.issues


def _failure_issue(
    code: str, section_id: str, explanation: str, correction: str
) -> ContinuityIssue:
    return ContinuityIssue(
        issue_code=code,
        affected_section_id=section_id,
        explanation=explanation,
        required_correction=correction,
    )


def _semantic_request(
    *,
    previous_section: SharedSection,
    previous_plan: TeachingPlanSection,
    next_section: SharedSection,
    next_plan: TeachingPlanSection,
    lookaround_nodes: int,
) -> BoundarySemanticRequest:
    return BoundarySemanticRequest(
        previous_plan=previous_plan,
        previous_exit_state=tuple(previous_plan.exit_state or ()),
        previous_final_nodes=tuple(previous_section.nodes[-lookaround_nodes:]),
        next_plan=next_plan,
        next_entry_state=tuple(next_plan.entry_state or ()),
        next_bridge=next_plan.bridge_from_previous,
        next_first_nodes=tuple(next_section.nodes[:lookaround_nodes]),
    )


def _coerce_verdict(raw: Any) -> BoundarySemanticVerdict:
    try:
        if isinstance(raw, BoundarySemanticVerdict):
            verdict = raw
        else:
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump(mode="json")
            verdict = BoundarySemanticVerdict.model_validate(raw)
    except ValidationError as exc:
        raise BoundarySemanticOutputError(
            "semantic boundary output violates its closed schema"
        ) from exc
    if verdict.issue is not None and any(
        _INTERNAL_REVIEW_TEXT.search(value)
        for value in (verdict.issue.explanation, verdict.issue.required_correction)
    ):
        raise BoundarySemanticOutputError("semantic boundary issue contains internal planning text")
    return verdict


def _expected_shapes(plan: SectionCompositionPlan) -> tuple[ExpectedNodeShape, ...]:
    return tuple(
        ExpectedNodeShape(
            id=item.id,
            kind=item.kind,
            teaching_block_id=item.teaching_block_id,
            semantic_role=item.semantic_role,
            task_spec_id=item.task_spec_id,
        )
        for item in plan.items
    )


def _section_from_repair(
    *,
    request: BoundaryRepairRequest,
    value: SharedSection | SectionWriteResult,
) -> SharedSection:
    if isinstance(value, SectionWriteResult):
        repaired = value.as_shared_section(
            section_id=request.target_section_id,
            position=(
                request.previous_section.position
                if request.previous_section.id == request.target_section_id
                else request.next_section.position
            ),
        )
    elif isinstance(value, SharedSection):
        repaired = value
    else:
        raise TypeError("boundary repair must return a SharedSection or SectionWriteResult")
    if repaired.id != request.target_section_id:
        raise ValueError("boundary repair changed the section identity")
    return repaired


class _WriterBoundaryRepairEngine:
    """One-call adapter around the existing section writer provider.

    ``write_section`` owns a three-dispatch authoring loop.  Boundary repair
    must not enter that loop, so this adapter performs exactly one structured
    provider dispatch and validates it with the same closed writer contract.
    """

    def __init__(self, provider: Callable[[dict[str, Any]], Awaitable[Any]] | None = None):
        self._provider = provider or _default_provider

    async def repair_section(self, request: BoundaryRepairRequest) -> SharedSection:
        errors = tuple(issue.required_correction for issue in request.issues)
        node_ids = tuple(node_id for issue in request.issues for node_id in issue.affected_node_ids)
        payload = _request_payload(
            request.writer_request,
            repair_scope="targeted",
            errors=errors,
            affected_node_ids=node_ids,
        )
        payload["boundary_context"] = {
            "previous_section": request.previous_section.model_dump(mode="json"),
            "next_section": request.next_section.model_dump(mode="json"),
            "target_section_id": request.target_section_id,
        }
        raw = await self._provider(payload)
        result = validate_and_build_section(request=request.writer_request, draft=raw)
        return _section_from_repair(request=request, value=result)


async def default_boundary_semantic_validator(
    request: BoundarySemanticRequest,
) -> BoundarySemanticVerdict:
    """Use the existing structured provider with the STANDARD capability slot."""
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.model_policy import BOUNDARY_CONTINUITY_VALIDATOR
    from infra.authoring.structured_provider import run_structured_agent

    raw = await run_structured_agent(
        node_name=BOUNDARY_CONTINUITY_VALIDATOR,
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("boundary-continuity-validator"),
        user_prompt=json.dumps(request.model_dump(mode="json"), sort_keys=True),
        output_type=BoundarySemanticVerdict,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(max_attempts=1),
    )
    return _coerce_verdict(raw)


async def validate_and_repair_boundary(
    *,
    previous_section: SharedSection,
    previous_plan: TeachingPlanSection,
    next_section: SharedSection,
    next_plan: TeachingPlanSection,
    semantic_validator: BoundarySemanticValidator | None = None,
    repair_engine: BoundaryRepairEngine | None = None,
    writer_requests: Mapping[str, SectionWriterRequest] | None = None,
    lookaround_nodes: int = 3,
) -> BoundaryValidationResult:
    """Validate one adjacent boundary and spend at most one repair call.

    Deterministic issues stop semantic review.  A semantic review is invoked
    once only when deterministic checks pass.  A repair is legal only when all
    issues target one side and an exact writer request for that side is given.
    """
    deterministic = tuple(
        validate_section_boundary(
            previous_section=previous_section,
            previous_plan=previous_plan,
            next_section=next_section,
            next_plan=next_plan,
            lookaround_nodes=lookaround_nodes,
        )
    )
    semantic_calls = 0
    initial = deterministic
    reviewer = semantic_validator or default_boundary_semantic_validator
    if not initial:
        semantic_calls = 1
        try:
            verdict = _coerce_verdict(
                await reviewer(
                    _semantic_request(
                        previous_section=previous_section,
                        previous_plan=previous_plan,
                        next_section=next_section,
                        next_plan=next_plan,
                        lookaround_nodes=lookaround_nodes,
                    )
                )
            )
        except BoundarySemanticOutputError as exc:
            issue = _failure_issue(
                "boundary_semantic_output_invalid",
                next_section.id,
                f"semantic boundary review returned malformed output: {exc}",
                "Return exactly PASS or one typed ContinuityIssue.",
            )
            return BoundaryValidationResult(
                status="recoverable_failure",
                previous_section=previous_section,
                next_section=next_section,
                issues=(issue,),
                initial_issues=(issue,),
                semantic_calls=semantic_calls,
                failure_code=issue.issue_code,
            )
        if verdict.status == "issue":
            assert verdict.issue is not None
            if verdict.issue.affected_section_id not in {
                previous_section.id,
                next_section.id,
            }:
                issue = _failure_issue(
                    "boundary_issue_unbound",
                    next_section.id,
                    "semantic boundary review targeted a section outside this boundary",
                    "Target only the accepted previous or next section.",
                )
                return BoundaryValidationResult(
                    status="recoverable_failure",
                    previous_section=previous_section,
                    next_section=next_section,
                    issues=(issue,),
                    initial_issues=(issue,),
                    semantic_calls=semantic_calls,
                    failure_code=issue.issue_code,
                )
            initial = (verdict.issue,)

    if not initial:
        return BoundaryValidationResult(
            status="pass",
            previous_section=previous_section,
            next_section=next_section,
            semantic_calls=semantic_calls,
        )

    affected_ids = {issue.affected_section_id for issue in initial}
    if len(affected_ids) != 1:
        issue = _failure_issue(
            "boundary_repair_ambiguous",
            next_section.id,
            "boundary issues affect both accepted siblings and cannot be repaired as one section",
            "Repair each affected section through its own bounded work item.",
        )
        return BoundaryValidationResult(
            status="recoverable_failure",
            previous_section=previous_section,
            next_section=next_section,
            issues=(*initial, issue),
            initial_issues=initial,
            semantic_calls=semantic_calls,
            failure_code=issue.issue_code,
        )
    target_id = next(iter(affected_ids))
    writer_request = (writer_requests or {}).get(target_id)
    if writer_request is None:
        issue = _failure_issue(
            "boundary_targeted_repair_unavailable",
            target_id,
            "the boundary issue requires a targeted section writer request and repair engine",
            "Supply the exact accepted SectionWriterRequest and bounded repair adapter.",
        )
        return BoundaryValidationResult(
            status="recoverable_failure",
            previous_section=previous_section,
            next_section=next_section,
            issues=(*initial, issue),
            initial_issues=initial,
            semantic_calls=semantic_calls,
            failure_code=issue.issue_code,
        )

    # Production dispatchers always have the exact writer request for either
    # side of this boundary. Use the existing one-call writer adapter when no
    # custom engine is injected, so a legal single-section issue gets the
    # bounded repair promised by the boundary contract.
    selected_repair_engine = repair_engine or _WriterBoundaryRepairEngine()
    request = BoundaryRepairRequest(
        target_section_id=target_id,
        writer_request=writer_request,
        issues=tuple(initial),
        previous_section=previous_section,
        next_section=next_section,
    )
    try:
        repaired = _section_from_repair(
            request=request,
            value=await selected_repair_engine.repair_section(request),
        )
    except SectionWriteValidationError as exc:
        issue = _failure_issue(
            "boundary_repair_failed",
            target_id,
            f"targeted boundary repair failed: {exc}",
            "Retry the affected section through its bounded writer work item.",
        )
        return BoundaryValidationResult(
            status="recoverable_failure",
            previous_section=previous_section,
            next_section=next_section,
            issues=(*initial, issue),
            initial_issues=initial,
            repair_attempted=True,
            semantic_calls=semantic_calls,
            failure_code=issue.issue_code,
        )

    repaired_previous = repaired if target_id == previous_section.id else previous_section
    repaired_next = repaired if target_id == next_section.id else next_section
    remaining = list(
        validate_section_boundary(
            previous_section=repaired_previous,
            previous_plan=previous_plan,
            next_section=repaired_next,
            next_plan=next_plan,
            lookaround_nodes=lookaround_nodes,
        )
    )
    target_plan = previous_plan if target_id == previous_section.id else next_plan
    section_issues = validate_section_continuity(
        section=repaired,
        teaching_plan_section=target_plan,
        expected_nodes=_expected_shapes(writer_request.composition_plan),
    )
    remaining.extend(section_issues)
    if remaining:
        return BoundaryValidationResult(
            status="recoverable_failure",
            previous_section=repaired_previous,
            next_section=repaired_next,
            issues=tuple(remaining),
            initial_issues=initial,
            repair_attempted=True,
            semantic_calls=semantic_calls,
            failure_code="boundary_revalidation_failed",
        )
    # Every repaired boundary gets one final semantic review.  A
    # deterministic-first repair has one call total; a semantic-initiated
    # repair has the initial review plus this one, never another repair.
    if semantic_calls < 2:
        semantic_calls += 1
        try:
            verdict = _coerce_verdict(
                await reviewer(
                    _semantic_request(
                        previous_section=repaired_previous,
                        previous_plan=previous_plan,
                        next_section=repaired_next,
                        next_plan=next_plan,
                        lookaround_nodes=lookaround_nodes,
                    )
                )
            )
        except BoundarySemanticOutputError as exc:
            issue = _failure_issue(
                "boundary_semantic_output_invalid",
                target_id,
                f"semantic boundary revalidation returned malformed output: {exc}",
                "Return exactly PASS or one typed ContinuityIssue.",
            )
            return BoundaryValidationResult(
                status="recoverable_failure",
                previous_section=repaired_previous,
                next_section=repaired_next,
                issues=(issue,),
                initial_issues=initial,
                repair_attempted=True,
                semantic_calls=semantic_calls,
                failure_code=issue.issue_code,
            )
        if verdict.status == "issue":
            assert verdict.issue is not None
            if verdict.issue.affected_section_id not in {
                repaired_previous.id,
                repaired_next.id,
            }:
                issue = _failure_issue(
                    "boundary_issue_unbound",
                    target_id,
                    "semantic boundary revalidation targeted a section outside this boundary",
                    "Target only the accepted previous or next section.",
                )
                return BoundaryValidationResult(
                    status="recoverable_failure",
                    previous_section=repaired_previous,
                    next_section=repaired_next,
                    issues=(issue,),
                    initial_issues=initial,
                    repair_attempted=True,
                    semantic_calls=semantic_calls,
                    failure_code=issue.issue_code,
                )
            return BoundaryValidationResult(
                status="recoverable_failure",
                previous_section=repaired_previous,
                next_section=repaired_next,
                issues=(verdict.issue,),
                initial_issues=initial,
                repair_attempted=True,
                semantic_calls=semantic_calls,
                failure_code="boundary_semantic_revalidation_failed",
            )
    return BoundaryValidationResult(
        status="pass",
        previous_section=repaired_previous,
        next_section=repaired_next,
        initial_issues=initial,
        repair_attempted=True,
        semantic_calls=semantic_calls,
    )


__all__ = [
    "BoundaryRepairEngine",
    "BoundaryRepairRequest",
    "BoundarySemanticRequest",
    "BoundarySemanticValidator",
    "BoundarySemanticVerdict",
    "BoundaryValidationResult",
    "default_boundary_semantic_validator",
    "validate_and_repair_boundary",
]

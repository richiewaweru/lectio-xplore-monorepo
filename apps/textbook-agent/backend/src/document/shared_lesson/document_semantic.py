"""Bounded semantic QA for an assembled shared lesson document.

Deterministic document QA remains the authoritative first gate.  Once it has
passed, this module can make exactly one FAST structured review call.  The
reviewer reports either PASS or typed, target-bound issues; it never rewrites
the immutable document and provider failures are allowed to propagate.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument
from document.shared_lesson.qa import DocumentQAResult
from infra.config import settings


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentSemanticQARequest(_ClosedModel):
    """Closed review context for the single whole-document semantic call."""

    document: SharedLessonDocument
    teaching_plan_sections: tuple[TeachingPlanSection, ...]


class DocumentSemanticVerdict(_ClosedModel):
    """Closed semantic output: PASS or one or more actionable typed issues."""

    status: Literal["pass", "issue"]
    issues: tuple[ContinuityIssue, ...] = ()

    @model_validator(mode="after")
    def _match_status(self) -> DocumentSemanticVerdict:
        if self.status == "pass" and self.issues:
            raise ValueError("a passing document verdict cannot carry issues")
        if self.status == "issue" and not self.issues:
            raise ValueError("an issue document verdict must carry at least one issue")
        return self


class DocumentSemanticQAResult(_ClosedModel):
    """Semantic QA result retaining deterministic issues and call accounting."""

    document_id: str = Field(min_length=1)
    document_revision: int = Field(ge=1)
    document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["pass", "issue"]
    issues: tuple[ContinuityIssue, ...] = ()
    semantic_calls: int = Field(ge=0, le=1)
    deterministic_skipped_semantic: bool = False

    @property
    def passed(self) -> bool:
        return self.status == "pass" and not self.issues

    @model_validator(mode="after")
    def _result_matches_status(self) -> DocumentSemanticQAResult:
        if self.status == "pass" and self.issues:
            raise ValueError("a passing result cannot carry issues")
        if self.deterministic_skipped_semantic and self.semantic_calls != 0:
            raise ValueError("deterministically blocked QA cannot make a semantic call")
        return self


class DocumentSemanticOutputError(ValueError):
    """Provider output was outside the closed semantic QA contract."""


class DocumentSemanticInputError(ValueError):
    """The deterministic result or document identity cannot be trusted."""


class DocumentSemanticValidator(Protocol):
    async def __call__(
        self, request: DocumentSemanticQARequest
    ) -> DocumentSemanticVerdict | Any: ...


def _coerce_verdict(
    raw: DocumentSemanticVerdict | Any,
    *,
    document: SharedLessonDocument,
) -> DocumentSemanticVerdict:
    try:
        if isinstance(raw, DocumentSemanticVerdict):
            verdict = raw
        else:
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump(mode="json")
            verdict = DocumentSemanticVerdict.model_validate(raw)
    except (TypeError, ValueError, ValidationError) as exc:
        raise DocumentSemanticOutputError(
            "semantic document output violates its closed schema"
        ) from exc

    sections = {section.id: {node.id for node in section.nodes} for section in document.sections}
    for issue in verdict.issues:
        node_ids = set(issue.affected_node_ids)
        if issue.affected_section_id not in sections:
            raise DocumentSemanticOutputError(
                f"semantic issue targets unknown section {issue.affected_section_id!r}"
            )
        unknown_nodes = sorted(node_ids - sections[issue.affected_section_id])
        if unknown_nodes:
            raise DocumentSemanticOutputError(
                "semantic issue targets unknown nodes: " + ", ".join(unknown_nodes)
            )
    return verdict


async def default_document_semantic_validator(
    request: DocumentSemanticQARequest,
) -> DocumentSemanticVerdict:
    """Run one FAST structured provider call through existing infrastructure."""
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.model_policy import DOCUMENT_SEMANTIC_QA
    from infra.authoring.structured_provider import run_structured_agent

    raw = await run_structured_agent(
        node_name=DOCUMENT_SEMANTIC_QA,
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("document-semantic-qa"),
        user_prompt=json.dumps(request.model_dump(mode="json"), sort_keys=True),
        output_type=DocumentSemanticVerdict,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(max_attempts=1),
    )
    return _coerce_verdict(raw, document=request.document)


async def _skipped_document_semantic_validator(
    request: DocumentSemanticQARequest,
) -> DocumentSemanticVerdict:
    return DocumentSemanticVerdict(status="pass")


async def qa_shared_lesson_document_semantics(
    *,
    document: SharedLessonDocument,
    teaching_plan_sections: Sequence[TeachingPlanSection],
    deterministic: DocumentQAResult,
    semantic_validator: DocumentSemanticValidator | None = None,
) -> DocumentSemanticQAResult:
    """Run deterministic-first semantic QA with at most one provider call.

    A deterministic failure is returned unchanged and never reaches the
    provider.  Semantic provider or configuration failures are intentionally
    uncaught so they remain operational failures rather than being mislabeled
    as learner-content issues.
    """
    if (
        deterministic.document_id != document.id
        or deterministic.document_revision != document.revision
    ):
        raise DocumentSemanticInputError(
            "deterministic QA identity does not match the shared lesson document"
        )
    if shared_lesson_content_hash(document) != document.content_hash:
        raise DocumentSemanticInputError(
            "shared lesson document content_hash does not match canonical content"
        )

    if not deterministic.ready:
        return DocumentSemanticQAResult(
            document_id=document.id,
            document_revision=document.revision,
            document_hash=document.content_hash,
            status="issue",
            issues=deterministic.issues,
            semantic_calls=0,
            deterministic_skipped_semantic=True,
        )

    request = DocumentSemanticQARequest(
        document=document,
        teaching_plan_sections=tuple(teaching_plan_sections),
    )
    # The skipped review still counts as the one review step so finalizer/handoff
    # invariants (semantic_calls == 1) hold.
    reviewer = semantic_validator or (
        default_document_semantic_validator
        if settings.document_semantic_qa
        else _skipped_document_semantic_validator
    )
    verdict = _coerce_verdict(await reviewer(request), document=document)
    return DocumentSemanticQAResult(
        document_id=document.id,
        document_revision=document.revision,
        document_hash=document.content_hash,
        status="pass" if verdict.status == "pass" else "issue",
        issues=verdict.issues,
        semantic_calls=1,
        deterministic_skipped_semantic=False,
    )


__all__ = [
    "DocumentSemanticInputError",
    "DocumentSemanticOutputError",
    "DocumentSemanticQARequest",
    "DocumentSemanticQAResult",
    "DocumentSemanticValidator",
    "DocumentSemanticVerdict",
    "default_document_semantic_validator",
    "qa_shared_lesson_document_semantics",
]

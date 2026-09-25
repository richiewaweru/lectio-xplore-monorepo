"""Deterministic assembly and final readiness gate for shared lessons.

Section writers may complete in any order.  This module is the single boundary
that puts accepted outputs back into Teaching Plan order, verifies their
identity and source lineage, and runs the final deterministic QA pass.  It has
no provider, worker, or persistence dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.hashing import verify_shared_lesson_source
from document.shared_lesson.models import (
    SharedLessonDocument,
    SharedProvenance,
    SharedSection,
    build_shared_lesson_document,
)
from document.shared_lesson.qa import (
    DocumentQAError,
    DocumentQAResult,
    qa_shared_lesson_document,
)
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    verify_teaching_plan_source,
)


class AssemblyIssue(BaseModel):
    """A typed contract failure before a draft can be assembled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_code: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class SharedLessonAssemblyError(ValueError):
    """Raised when accepted section outputs cannot form one closed draft."""

    def __init__(self, issues: Sequence[AssemblyIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "shared lesson assembly contract failed: "
            + "; ".join(issue.issue_code for issue in self.issues)
        )


class SharedLessonAssemblyResult(BaseModel):
    """Immutable draft plus its final QA result.

    A document is READY only when ``ready`` is true.  A blocked result retains
    the immutable draft and healthy section siblings for targeted correction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    document: SharedLessonDocument
    qa: DocumentQAResult
    status: Literal["ready", "blocked"]

    @property
    def ready(self) -> bool:
        return self.status == "ready" and self.qa.ready

    def require_ready(self) -> SharedLessonDocument:
        """Return the artifact only after the complete deterministic QA gate."""
        if not self.ready:
            raise DocumentQAError(self.qa)
        return self.document


def _issue(code: str, section_id: str, explanation: str) -> AssemblyIssue:
    return AssemblyIssue(
        issue_code=code,
        section_id=section_id,
        explanation=explanation,
    )


def _ordered_sections(
    *,
    plan_sections: Sequence[TeachingPlanSection],
    accepted_sections: Mapping[str, SharedSection] | Sequence[SharedSection],
) -> tuple[SharedSection, ...]:
    """Validate accepted section identity and return the plan order."""
    expected_ids = tuple(section.slot_id for section in plan_sections)
    if len(expected_ids) != len(set(expected_ids)):
        raise SharedLessonAssemblyError(
            (
                _issue(
                    "duplicate_plan_section", "document", "Teaching Plan section IDs are not unique"
                ),
            )
        )

    issues: list[AssemblyIssue] = []
    if isinstance(accepted_sections, Mapping):
        supplied_keys = tuple(str(key) for key in accepted_sections)
        missing = [section_id for section_id in expected_ids if section_id not in accepted_sections]
        extra = [section_id for section_id in supplied_keys if section_id not in expected_ids]
        for section_id in missing:
            issues.append(
                _issue(
                    "missing_section", section_id, "accepted output is missing a planned section"
                )
            )
        for section_id in extra:
            issues.append(
                _issue(
                    "unplanned_section",
                    section_id,
                    "accepted output has no matching planned section",
                )
            )
        sections = tuple(
            accepted_sections[section_id]
            for section_id in expected_ids
            if section_id in accepted_sections
        )
    else:
        supplied = tuple(accepted_sections)
        supplied_ids = tuple(section.id for section in supplied)
        seen: set[str] = set()
        for section_id in supplied_ids:
            if section_id in seen:
                issues.append(
                    _issue(
                        "duplicate_section",
                        section_id,
                        "accepted outputs contain a duplicate section ID",
                    )
                )
            seen.add(section_id)
        if len(supplied) != len(expected_ids):
            issues.append(
                _issue(
                    "section_count_mismatch",
                    "document",
                    f"received {len(supplied)} sections for {len(expected_ids)} planned sections",
                )
            )
        if supplied_ids != expected_ids:
            issues.append(
                _issue(
                    "section_order_mismatch",
                    "document",
                    f"accepted section order {list(supplied_ids)!r} does not match plan order {list(expected_ids)!r}",
                )
            )
        sections = supplied

    for position, (expected_id, section) in enumerate(zip(expected_ids, sections, strict=False)):
        if section.id != expected_id:
            issues.append(
                _issue(
                    "section_id_mismatch",
                    section.id,
                    f"position {position} has {section.id!r}; expected planned section {expected_id!r}",
                )
            )
        if section.position != position:
            issues.append(
                _issue(
                    "section_position_mismatch",
                    section.id,
                    f"section position is {section.position}; expected {position}",
                )
            )

    if issues:
        raise SharedLessonAssemblyError(issues)
    return sections


def assemble_shared_lesson_document(
    *,
    document_id: str,
    revision: int,
    source: TeachingPlanSource,
    accepted_sections: Mapping[str, SharedSection] | Sequence[SharedSection],
    tasks: Sequence[Mapping[str, Any] | Any] = (),
    provenance: SharedProvenance | Mapping[str, Any] | None = None,
    created_at: datetime | str,
    expected_shapes: Mapping[str, Sequence[Any]] | None = None,
    expected_title: str | None = None,
    approved_source_ids: Sequence[str] = (),
    source_facts_by_section: Mapping[str, Sequence[str]] | None = None,
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    available_media_ids: Sequence[str] = (),
    expected_content_hash: str | None = None,
) -> SharedLessonAssemblyResult:
    """Assemble accepted section outputs and run the final deterministic gate.

    Mapping inputs allow parallel writers to complete in arbitrary order.  A
    sequence is intentionally checked for exact plan order so callers cannot
    silently create a different lesson.  Contract failures raise before a
    draft is built; QA failures return a blocked result with the draft intact.
    """
    try:
        source_identity = verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SharedLessonAssemblyError(
            (
                _issue(
                    "teaching_plan_source_invalid",
                    "document",
                    str(exc),
                ),
            )
        ) from exc
    plan = source.plan
    teaching_plan_sections = tuple(plan.sections)
    teaching_plan_id = source_identity.source_artifact_id
    teaching_plan_revision = source_identity.source_revision
    teaching_plan_hash = source_identity.source_hash
    title = plan.learner_title
    if title is None:  # The Phase 6 verifier normally rejects this for v2 plans.
        raise SharedLessonAssemblyError(
            (_issue("teaching_plan_title_missing", "document", "approved source has no learner title"),)
        )
    if expected_title is not None and expected_title != title:
        raise SharedLessonAssemblyError(
            (
                _issue(
                    "teaching_plan_title_mismatch",
                    "document",
                    "expected title differs from the approved Teaching Plan learner title",
                ),
            )
        )
    sections = _ordered_sections(
        plan_sections=teaching_plan_sections,
        accepted_sections=accepted_sections,
    )
    document = build_shared_lesson_document(
        {
            "id": document_id,
            "revision": revision,
            "teaching_plan_id": teaching_plan_id,
            "teaching_plan_revision": teaching_plan_revision,
            "teaching_plan_hash": teaching_plan_hash,
            "title": title,
            "sections": [section.model_dump(mode="json") for section in sections],
            "tasks": [
                task.model_dump(mode="json") if hasattr(task, "model_dump") else dict(task)
                for task in tasks
            ],
            "provenance": provenance or {},
            "created_at": created_at,
        }
    )
    verify_shared_lesson_source(
        document,
        teaching_plan_id=teaching_plan_id,
        teaching_plan_revision=teaching_plan_revision,
        teaching_plan_hash=teaching_plan_hash,
    )
    if expected_content_hash is not None and document.content_hash != expected_content_hash:
        raise SharedLessonAssemblyError(
            (
                _issue(
                    "content_hash_mismatch",
                    "document",
                    "assembled content hash does not match the expected approved hash",
                ),
            )
        )

    qa = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=teaching_plan_sections,
        expected_shapes=expected_shapes or {},
        expected_title=title,
        approved_source_ids=approved_source_ids,
        source_facts_by_section=source_facts_by_section,
        required_media_by_section=required_media_by_section,
        available_media_ids=available_media_ids,
    )
    return SharedLessonAssemblyResult(
        document=document,
        qa=qa,
        status="ready" if qa.ready else "blocked",
    )


__all__ = [
    "AssemblyIssue",
    "SharedLessonAssemblyError",
    "SharedLessonAssemblyResult",
    "assemble_shared_lesson_document",
]

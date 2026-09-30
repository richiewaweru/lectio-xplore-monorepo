"""Teacher-visible quality flags recorded by an advisory document quality gate.

In ``document_quality_gate="advisory"`` mode, semantic/quality findings do not
block READY; they are persisted on the durable document-QA WorkItem output
(never on the immutable document, so content hash and lineage are untouched)
and surfaced to the teacher in the Learn/Print editors.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document.shared_lesson.continuity import ContinuityIssue

QualityFlagSource = Literal["semantic_qa", "deterministic_qa", "writer_warning"]


class QualityFlag(BaseModel):
    """One non-blocking learner-content quality finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: Literal["warning"] = "warning"
    source: QualityFlagSource
    message: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    node_ids: tuple[str, ...] = ()
    required_correction: str = Field(min_length=1)


def quality_flags_from_issues(
    issues: Sequence[ContinuityIssue], *, source: QualityFlagSource
) -> tuple[QualityFlag, ...]:
    return tuple(
        QualityFlag(
            code=issue.issue_code,
            source=source,
            message=issue.explanation,
            section_id=issue.affected_section_id,
            node_ids=tuple(issue.affected_node_ids),
            required_correction=issue.required_correction,
        )
        for issue in issues
    )


__all__ = ["QualityFlag", "QualityFlagSource", "quality_flags_from_issues"]

"""Teacher-visible quality flags recorded by an advisory document quality gate.

In ``document_quality_gate="advisory"`` mode, semantic/quality findings do not
block READY; they are persisted on the durable document-QA WorkItem output
(never on the immutable document, so content hash and lineage are untouched)
and surfaced to the teacher in the Learn/Print editors.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from document.shared_lesson.continuity import ContinuityIssue

QualityFlagSource = Literal["semantic_qa", "deterministic_qa", "writer_warning", "boundary_check"]


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
    # Optional boundary metadata. Omitted from every dump while unset so flags
    # (and the document-QA output hash they live in) persisted before these
    # fields existed stay byte-identical.
    previous_section_id: str | None = None
    next_section_id: str | None = None
    previous_section_title: str | None = None
    next_section_title: str | None = None
    internal_issue_codes: tuple[str, ...] = ()

    @model_serializer(mode="wrap")
    def _omit_unset_boundary_metadata(self, handler):
        data = handler(self)
        if isinstance(data, dict):
            for key in (
                "previous_section_id",
                "next_section_id",
                "previous_section_title",
                "next_section_title",
            ):
                if data.get(key) is None:
                    data.pop(key, None)
            if not data.get("internal_issue_codes"):
                data.pop("internal_issue_codes", None)
        return data


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


BOUNDARY_TRANSITION_FLAG_CODE = "boundary_transition_warning"


def boundary_transition_flag(
    *,
    previous_section_id: str,
    next_section_id: str,
    previous_title: str,
    next_title: str,
    issues: Sequence[ContinuityIssue],
) -> QualityFlag:
    """One plain-language warning for a boundary that fell back to advisory."""
    codes = tuple(dict.fromkeys(issue.issue_code for issue in issues))
    repeats = any("repetition" in code for code in codes)
    bridge = any(
        any(word in code for word in ("bridge", "prerequisite", "exit"))
        for code in codes
    )
    if repeats and bridge:
        reason = "the opening may repeat earlier wording or skip the planned bridge"
    elif repeats:
        reason = "the opening may repeat earlier wording"
    elif bridge:
        reason = "the opening may skip the planned bridge"
    else:
        reason = "the connection between them may be unclear"
    return QualityFlag(
        code=BOUNDARY_TRANSITION_FLAG_CODE,
        source="boundary_check",
        message=(
            f"The move from {previous_title} into {next_title} may feel abrupt \u2014 {reason}."
        ),
        section_id=next_section_id,
        required_correction=(
            f"Read the opening of {next_title} and smooth the transition if needed."
        ),
        previous_section_id=previous_section_id,
        next_section_id=next_section_id,
        previous_section_title=previous_title,
        next_section_title=next_title,
        internal_issue_codes=codes,
    )


__all__ = [
    "BOUNDARY_TRANSITION_FLAG_CODE",
    "QualityFlag",
    "QualityFlagSource",
    "boundary_transition_flag",
    "quality_flags_from_issues",
]

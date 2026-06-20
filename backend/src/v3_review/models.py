from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["minor", "major", "blocking"]

RepairExecutor = Literal[
    "section_writer",
    "question_writer",
    "visual_executor",
    "answer_key_generator",
    "assembler",
]

IssueCategory = Literal[
    "missing_planned_content",
    "extra_unplanned_content",
    "anchor_drift",
    "visual_mismatch",
    "question_mismatch",
    "answer_key_mismatch",
    "register_mismatch",
    "practice_progression_mismatch",
    "internal_artifact_leak",
    "schema_violation",
    "print_risk",
]

CoherenceStatus = Literal[
    "passed",
    "passed_with_warnings",
    "failed",
]


class ReviewIssue(BaseModel):
    model_config = {"extra": "forbid"}

    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    severity: Severity
    category: IssueCategory
    message: str
    blueprint_ref: str | None = None
    generated_ref: str | None = None
    suggested_repair_executor: RepairExecutor
    repair_target_id: str | None = None


class CoherenceReport(BaseModel):
    model_config = {"extra": "forbid"}

    blueprint_id: str
    generation_id: str
    status: CoherenceStatus
    deterministic_passed: bool
    blocking_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    issues: list[ReviewIssue] = Field(default_factory=list)


def derive_coherence_status(issues: Sequence[ReviewIssue]) -> CoherenceStatus:
    blocking = [i for i in issues if i.severity == "blocking"]
    major = [i for i in issues if i.severity == "major"]
    minor = [i for i in issues if i.severity == "minor"]
    if not blocking and not major and not minor:
        return "passed"
    if not blocking and not major:
        return "passed_with_warnings"
    return "failed"


def refresh_issue_counts(report: CoherenceReport) -> None:
    blocking = [i for i in report.issues if i.severity == "blocking"]
    major = [i for i in report.issues if i.severity == "major"]
    minor = [i for i in report.issues if i.severity == "minor"]
    report.blocking_count = len(blocking)
    report.major_count = len(major)
    report.minor_count = len(minor)


__all__ = [
    "CoherenceReport",
    "CoherenceStatus",
    "IssueCategory",
    "RepairExecutor",
    "ReviewIssue",
    "Severity",
    "derive_coherence_status",
    "refresh_issue_counts",
]

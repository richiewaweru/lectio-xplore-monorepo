from __future__ import annotations

from collections.abc import Iterable
from typing import Any

FATAL_ISSUE_CATEGORIES = {
    "internal_artifact_leak",
    "schema_violation",
}


def derive_booklet_status(
    *,
    draft_section_count: int,
    render_valid: bool,
    review_done: bool,
    finalised: bool,
    blocking_count: int,
    major_count: int,
    minor_count: int,
    fatal_issue_categories: set[str],
) -> str:
    if draft_section_count == 0:
        return "failed_unusable"
    if not render_valid:
        return "failed_unusable"
    if fatal_issue_categories:
        return "failed_unusable"
    if not review_done:
        return "draft_ready"
    if blocking_count > 0 or major_count > 0:
        return "draft_needs_review"
    if minor_count > 0:
        return "final_with_warnings" if finalised else "draft_with_warnings"
    return "final_ready" if finalised else "draft_ready"


def collect_fatal_issue_categories(
    issues: Iterable[Any],
) -> set[str]:
    categories: set[str] = set()
    for issue in issues:
        category = getattr(issue, "category", None)
        if isinstance(category, str) and category in FATAL_ISSUE_CATEGORIES:
            categories.add(category)
    return categories


__all__ = [
    "FATAL_ISSUE_CATEGORIES",
    "collect_fatal_issue_categories",
    "derive_booklet_status",
]

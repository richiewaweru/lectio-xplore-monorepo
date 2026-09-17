"""Canonical Learn/Print issue projection for the lesson workspace."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from learn.contracts.lesson_document import validate_learn_document
from print.contracts.lectio_page import validate_document as validate_print_document

ArtifactPath = Literal["learn", "print"]
IssuePath = Literal["learn", "print", "shared"]
IssueSeverity = Literal["info", "warning", "error"]
IssueCategory = Literal[
    "coherence",
    "media",
    "figure",
    "interaction",
    "document",
    "realization",
    "assessment",
    "contract",
    "other",
]


class LessonIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    path: IssuePath
    severity: IssueSeverity
    category: IssueCategory
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    target_id: str | None = None
    repairable: bool = False
    repair_action: str | None = None
    source: str = Field(min_length=1)


class LessonIssueCounts(BaseModel):
    info: int = 0
    warning: int = 0
    error: int = 0


class LessonIssuesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: ArtifactPath
    issues: list[LessonIssue] = Field(default_factory=list)
    counts: LessonIssueCounts = Field(default_factory=LessonIssueCounts)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _stable_id(path: IssuePath, code: str, target_id: str | None) -> str:
    key = f"{path}|{code}|{target_id or 'lesson'}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _severity(value: Any) -> IssueSeverity:
    value = _text(value).lower()
    if value in {"error", "blocking", "failed", "fatal"}:
        return "error"
    if value in {"warning", "major", "warn", "attention"}:
        return "warning"
    return "info"


def _category(code: str, category: Any = None) -> IssueCategory:
    category_text = _text(category).lower()
    if category_text in {
        "coherence", "media", "figure", "interaction", "document",
        "realization", "assessment", "contract", "other",
    }:
        return category_text  # type: ignore[return-value]
    value = f"{code} {_text(category)}".lower()
    for token, result in (
        ("figure", "figure"),
        ("visual", "figure"),
        ("media", "media"),
        ("interaction", "interaction"),
        ("assessment", "assessment"),
        ("coherence", "coherence"),
        ("contract", "contract"),
        ("schema", "contract"),
        ("document", "document"),
        ("print", "document"),
    ):
        if token in value:
            return result  # type: ignore[return-value]
    return "coherence" if _text(category) else "other"


def _target(issue: Mapping[str, Any]) -> str | None:
    for key in (
        "target_id",
        "targetId",
        "repair_target_id",
        "node_id",
        "nodeId",
        "figure_id",
        "figureId",
        "teaching_block_id",
        "shared_task_id",
        "section_id",
        "generated_ref",
    ):
        value = _text(issue.get(key))
        if value:
            return value
    return None


def _as_issue(
    *,
    path: IssuePath,
    raw: Mapping[str, Any],
    source: str,
    default_category: Any = None,
    default_code: str = "LESSON_ISSUE",
    default_severity: Any = "warning",
) -> LessonIssue | None:
    message = _text(raw.get("message")) or _text(raw.get("error_summary"))
    if not message:
        return None
    code = _text(raw.get("code")) or _text(raw.get("category")) or default_code
    target_id = _target(raw)
    repair_action = (
        _text(raw.get("repair_action"))
        or _text(raw.get("repairAction"))
        or _text(raw.get("repair_instruction"))
        or _text(raw.get("suggested_repair_executor"))
    )
    repairable = bool(
        raw.get("repairable")
        or raw.get("retryable")
        or repair_action
        or raw.get("repair_target_id")
    )
    return LessonIssue(
        id=_stable_id(path, code, target_id),
        path=path,
        severity=_severity(raw.get("severity", default_severity)),
        category=_category(code, raw.get("category", default_category)),
        code=code,
        message=message,
        target_id=target_id,
        repairable=repairable,
        repair_action=repair_action or ("retry" if repairable else None),
        source=source,
    )


def _iter_report_issues(state: Mapping[str, Any], path: ArtifactPath) -> Iterable[LessonIssue]:
    smart = state.get("smart_lesson")
    reports = smart.get("coherence_reports") if isinstance(smart, Mapping) else None
    if not isinstance(reports, Mapping):
        reports = state.get("coherence_reports")
    report = reports.get(path) if isinstance(reports, Mapping) else None
    if not isinstance(report, Mapping):
        report = state.get("coherence_report")
    if not isinstance(report, Mapping) and any(
        key in state for key in ("issues", "deterministic_issues", "semantic_issues")
    ):
        report = state
    if not isinstance(report, Mapping):
        return
    raw_issues: list[Any] = []
    for key in ("issues", "deterministic_issues", "semantic_issues"):
        candidate = report.get(key)
        if isinstance(candidate, list):
            raw_issues.extend(candidate)
    for raw in raw_issues:
        if isinstance(raw, Mapping):
            issue = _as_issue(
                path=path,
                raw=raw,
                source="coherence_review",
                default_category="coherence",
            )
            if issue:
                yield issue


def _walk(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _media_issues(
    path: ArtifactPath, documents: Sequence[Mapping[str, Any]]
) -> Iterable[LessonIssue]:
    def is_figure_node(node: Mapping[str, Any]) -> bool:
        kind = _text(node.get("object")) or _text(node.get("kind"))
        return kind in {"figure", "visual"} or "figure" in kind.lower()

    for document in documents:
        media = document.get("media")
        media_ids = set(media) if isinstance(media, Mapping) else set()
        for node in _walk(document):
            kind = _text(node.get("object")) or _text(node.get("kind"))
            status = _text(node.get("status") or node.get("media_status")).lower()
            required = bool(
                node.get("required")
                or node.get("visual_required")
                or node.get("media_required")
            )
            is_figure = kind in {"figure", "visual"} or "figure" in kind.lower()
            has_asset = bool(
                node.get("src")
                or node.get("image_url")
                or node.get("asset")
                or node.get("asset_id") in media_ids
                or node.get("media_id") in media_ids
            )
            if is_figure and required and (
                not has_asset or status in {"pending", "failed", "omitted", "omitted_quality"}
            ):
                raw = {
                    "code": "REQUIRED_FIGURE_MISSING",
                    "message": _text(node.get("error_message"))
                    or "A required figure or media asset is missing.",
                    "severity": "error",
                    "target_id": _target(node),
                    "repairable": status != "failed_terminal",
                    "repair_action": "retry" if status != "failed_terminal" else None,
                }
                issue = _as_issue(
                    path=path,
                    raw=raw,
                    source="media_pipeline",
                    default_category="figure",
                )
                if issue:
                    yield issue
            elif required and bool(node.get("visual_required")) and not is_figure:
                children = next(
                    (
                        node.get(key)
                        for key in ("blocks", "components", "nodes")
                        if isinstance(node.get(key), list)
                    ),
                    None,
                )
                has_figure_child = (
                    any(
                        is_figure_node(child)
                        for child in children
                        if isinstance(child, Mapping)
                    )
                    if isinstance(children, list)
                    else False
                )
                if isinstance(children, list) and not has_figure_child:
                    issue = _as_issue(
                        path=path,
                        raw={
                            "code": "REQUIRED_FIGURE_MISSING",
                            "message": "A section marked visual_required has no figure or media asset.",
                            "severity": "error",
                            "target_id": _target(node),
                            "repairable": True,
                            "repair_action": "retry",
                        },
                        source="media_pipeline",
                        default_category="figure",
                    )
                    if issue:
                        yield issue


def _document_contract_issues(
    path: ArtifactPath, documents: Sequence[Mapping[str, Any]]
) -> Iterable[LessonIssue]:
    """Project persisted document/interaction contract failures without mutating data."""
    for document in documents:
        errors: list[str] = []
        if path == "learn" and ("version" in document or "nodes" in document):
            errors = validate_learn_document(document)
        elif path == "print" and (
            "sections" in document or "pages" in document or "booklet_issues" in document
        ):
            errors = validate_print_document(document)
        for message in errors:
            lowered = message.lower()
            category = "interaction" if "interaction" in lowered else "document"
            code = "LEARN_INTERACTION_INVALID" if category == "interaction" else "DOCUMENT_INVALID"
            issue = _as_issue(
                path=path,
                raw={"code": code, "message": message, "severity": "error"},
                source="document_validation",
                default_category=category,
            )
            if issue:
                yield issue


def collect_lesson_issues(
    *,
    path: ArtifactPath,
    realization: Mapping[str, Any] | None = None,
    states: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Mapping[str, Any]] = (),
    booklet_issues: Sequence[Any] = (),
    generation_errors: Sequence[str] = (),
) -> LessonIssuesResponse:
    """Collect and deterministically normalize all known issues for one path."""
    found: dict[tuple[str, str, str], LessonIssue] = {}

    def add(issue: LessonIssue | None) -> None:
        if issue is None:
            return
        key = (issue.path, issue.code, issue.target_id or "")
        prior = found.get(key)
        score = (issue.repairable, len(issue.message), len(issue.source))
        prior_score = (
            (prior.repairable, len(prior.message), len(prior.source))
            if prior is not None
            else None
        )
        if prior is None or score > prior_score:
            found[key] = issue

    if realization:
        status = _text(realization.get("status")).lower()
        error_summary = _text(realization.get("error_summary"))
        if error_summary or "fail" in status:
            add(
                _as_issue(
                    path=path,
                    raw={
                        "code": "REALIZATION_FAILED",
                        "message": error_summary or f"The {path} realization failed.",
                        "severity": "error",
                        "target_id": realization.get("realization_id"),
                        "repairable": status != "failed_terminal",
                        "repair_action": "retry" if status != "failed_terminal" else None,
                    },
                    source="realization_status",
                    default_category="realization",
                )
            )

    for state in states:
        for issue in _iter_report_issues(state, path):
            add(issue)
    for issue in _media_issues(path, documents):
        add(issue)
    for issue in _document_contract_issues(path, documents):
        add(issue)
    for raw in booklet_issues:
        if isinstance(raw, Mapping):
            add(
                _as_issue(
                    path=path,
                    raw=raw,
                    source="print_document",
                    default_category="document",
                )
            )
        elif isinstance(raw, str) and raw.strip():
            add(
                _as_issue(
                    path=path,
                    raw={"message": raw},
                    source="print_document",
                    default_category="document",
                )
            )
    for message in generation_errors:
        add(
            _as_issue(
                path=path,
                raw={"code": "OUTPUT_ERROR", "message": message, "severity": "error"},
                source="output_generation",
                default_category="document",
            )
        )

    issues = sorted(
        found.values(),
        key=lambda item: (item.severity, item.category, item.code, item.target_id or ""),
    )
    counts = LessonIssueCounts(
        info=sum(issue.severity == "info" for issue in issues),
        warning=sum(issue.severity == "warning" for issue in issues),
        error=sum(issue.severity == "error" for issue in issues),
    )
    return LessonIssuesResponse(path=path, issues=issues, counts=counts)


__all__ = [
    "LessonIssue",
    "LessonIssueCounts",
    "LessonIssuesResponse",
    "collect_lesson_issues",
]

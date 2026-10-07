"""Canonical Learn/Print issue projection for the lesson workspace."""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.lesson_document import validate_learn_document
from contracts.lectio_page import validate_document as validate_print_document
from curriculum.lesson_review.issue_copy import (
    BLOCKING_COPY,
    COHERENCE_COPY,
    FIGURE_FALLBACK_COPY,
    FLAG_COPY,
    IssueCopy,
    IssueGroup,
)

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
    #: Teacher-facing grouping: blocking -> needs_look -> info.
    group: IssueGroup = "blocking"
    #: Section the item is about (deep-link target and teacher-visible title).
    #: ``section_title`` is ``None`` for whole-lesson items.
    section_id: str | None = None
    section_title: str | None = None
    previous_section_title: str | None = None
    #: What the teacher can do about it, in plain language.
    suggestion: str | None = None
    #: Raw internal wording, shown only behind a "details" disclosure.
    details: str | None = None
    #: Only ``needs_look`` items can be marked as fine.
    dismissible: bool = False
    dismissed: bool = False


class LessonIssueCounts(BaseModel):
    info: int = 0
    warning: int = 0
    error: int = 0
    blocking: int = 0
    needs_look: int = 0
    #: Informational items (group ``info``); not part of ``attention``.
    informational: int = 0
    #: Items marked as fine; excluded from every other count except severity.
    dismissed: int = 0
    #: Unresolved blocking + needs_look: what the teacher should look at.
    attention: int = 0


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


def _group_rank(group: IssueGroup) -> int:
    return {"blocking": 0, "needs_look": 1, "info": 2}[group]


def _blocking_copy(code: str, severity: IssueSeverity) -> IssueCopy | None:
    """Copy for the always-teacher-meaningful codes; a planned figure that is
    only an advisory placeholder (``warning``) moves to ``needs_look``."""
    if code == "REQUIRED_FIGURE_MISSING" and severity != "error":
        return FIGURE_FALLBACK_COPY
    return BLOCKING_COPY.get(code)


def _as_issue(
    *,
    path: IssuePath,
    raw: Mapping[str, Any],
    source: str,
    default_category: Any = None,
    default_code: str = "LESSON_ISSUE",
    default_severity: Any = "warning",
    allowed: Mapping[str, IssueCopy] | None = None,
) -> LessonIssue | None:
    """Normalize one raw item. ``allowed`` is an explicit allow-list: a code that
    is not in it is excluded, so new internal codes stay hidden. ``None`` means
    the blocking set (``REALIZATION_FAILED`` and friends)."""
    raw_message = _text(raw.get("message")) or _text(raw.get("error_summary"))
    if not raw_message:
        return None
    code = _text(raw.get("code")) or _text(raw.get("category")) or default_code
    severity = _severity(raw.get("severity", default_severity))
    copy = _blocking_copy(code, severity) if allowed is None else allowed.get(code)
    if copy is None:
        return None
    group: IssueGroup = copy.group
    if group == "blocking":
        severity = "error"
    elif severity == "info":
        group = "info"
    elif severity == "error":
        severity = "warning"
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
        severity=severity,
        category=_category(code, raw.get("category", default_category)),
        code=code,
        message=copy.message or raw_message,
        target_id=target_id,
        repairable=repairable,
        repair_action=repair_action or ("retry" if repairable else None),
        source=source,
        group=group,
        suggestion=copy.suggestion,
        details=raw_message if copy.message else None,
        dismissible=group == "needs_look",
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
                allowed=COHERENCE_COPY,
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


_FAILED_FIGURE_STATUSES = frozenset({"failed", "failed_terminal", "omitted", "omitted_quality"})


def _is_figure_node(node: Mapping[str, Any]) -> bool:
    kind = _text(node.get("object")) or _text(node.get("kind"))
    return kind in {"figure", "visual"} or "figure" in kind.lower()


_READY_REALIZATION_STATUSES = frozenset({"ready", "completed", "published"})


def _figure_node_id(slot_id: str, block: Mapping[str, Any]) -> str | None:
    """Deterministic shared figure node id for a planned block (Print blocks
    keep this id but carry no ``teaching_block_id``)."""
    if not slot_id:
        return None
    try:
        from curriculum.teaching_plan.models import TeachingPlanBlock
        from document.shared_lesson.composer import figure_item_for_block

        return figure_item_for_block(slot_id, TeachingPlanBlock.model_validate(block)).id
    except Exception:  # noqa: BLE001 - id derivation is best-effort matching only
        return None


def _has_image(node: Mapping[str, Any]) -> bool:
    """Whether a Learn figure node or Print figure block has an image attached."""
    content = node.get("content")
    asset = content.get("asset") if isinstance(content, Mapping) else node.get("asset")
    if isinstance(asset, Mapping):
        status = _text(asset.get("status")).lower()
        return bool(_text(asset.get("src"))) and status in {"", "ready"}
    return bool(_text(node.get("asset_id")) or _text(node.get("src")) or _text(node.get("image_url")))


_UNAVAILABLE_FIGURE_DEFAULT_REASON = "The figure could not be generated."


def _unavailable_reason(node: Mapping[str, Any]) -> str | None:
    """Teacher-safe reason when a figure shipped as an unavailable placeholder, else None.

    Learn nodes carry ``status: "unavailable"`` plus ``unavailable_reason``; Print
    blocks carry a ``failed`` asset (no reason is persisted there).
    """
    if _text(node.get("status")).lower() == "unavailable":
        return _text(node.get("unavailable_reason")) or _UNAVAILABLE_FIGURE_DEFAULT_REASON
    content = node.get("content")
    asset = content.get("asset") if isinstance(content, Mapping) else node.get("asset")
    if isinstance(asset, Mapping) and _text(asset.get("status")).lower() == "failed":
        return _UNAVAILABLE_FIGURE_DEFAULT_REASON
    return None


def _plan_visual_blocks(
    states: Sequence[Mapping[str, Any]],
) -> list[tuple[str, bool, str | None]]:
    """(block id, required, figure node id) for every plan block that declares a ``visual``."""
    for state in states:
        plan = state.get("teaching_plan")
        if not isinstance(plan, Mapping):
            continue
        found: list[tuple[str, bool, str | None]] = []
        for section in plan.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for block in section.get("blocks") or []:
                if not isinstance(block, Mapping):
                    continue
                visual = block.get("visual")
                block_id = _text(block.get("id"))
                if isinstance(visual, Mapping) and block_id:
                    found.append(
                        (
                            block_id,
                            visual.get("required") is not False,
                            _figure_node_id(_text(section.get("slot_id")), block),
                        )
                    )
        return found
    return []


def _plan_visual_issues(
    path: ArtifactPath,
    documents: Sequence[Mapping[str, Any]],
    plan_visual_blocks: Sequence[tuple[str, bool, str | None]],
    *,
    realization_ready: bool = False,
    figure_nodes_out: dict[str, set[str]] | None = None,
) -> Iterable[LessonIssue]:
    """The teaching plan is the sole authority for figures: every planned visual
    needs a figure node bound to its block, and that figure must not have failed."""
    figures_by_block: dict[str, list[Mapping[str, Any]]] = {}
    figures_by_id: dict[str, Mapping[str, Any]] = {}
    for document in documents:
        for node in _walk(document):
            if not _is_figure_node(node):
                continue
            block_id = _text(node.get("teaching_block_id"))
            if block_id:
                figures_by_block.setdefault(block_id, []).append(node)
            node_id = _text(node.get("id"))
            if node_id and (_text(node.get("object")) or _text(node.get("kind"))) == "figure":
                figures_by_id[node_id] = node
    for block_id, required, figure_node_id in plan_visual_blocks:
        figures = list(figures_by_block.get(block_id, []))
        by_id = figures_by_id.get(figure_node_id) if figure_node_id else None
        if by_id is not None and not any(by_id is f for f in figures):
            figures.append(by_id)
        unavailable = [_unavailable_reason(node) for node in figures]
        severity = "error" if required else "warning"
        if not figures:
            message = "A teaching block planned a visual but the document has no figure for it."
        elif all(reason is not None for reason in unavailable):
            # Settled outcome: the lesson ships with a placeholder; advisory only.
            message = f"The planned figure is unavailable: {unavailable[0]}"
            severity = "warning"
        elif all(
            _text(node.get("status") or node.get("media_status")).lower()
            in _FAILED_FIGURE_STATUSES
            for node in figures
        ):
            message = "The figure planned for this teaching block failed to generate."
        elif realization_ready and not any(_has_image(node) for node in figures):
            message = "The planned figure has no image yet."
        else:
            continue
        issue = _as_issue(
            path=path,
            raw={
                "code": "REQUIRED_FIGURE_MISSING",
                "message": message,
                "severity": severity,
                "target_id": block_id,
                "repairable": True,
                "repair_action": "retry",
            },
            source="media_pipeline",
            default_category="figure",
        )
        if issue:
            if figure_nodes_out is not None:
                figure_nodes_out[block_id] = {
                    node_id
                    for node_id in (
                        figure_node_id,
                        *(_text(node.get("id")) for node in figures),
                    )
                    if node_id
                }
            yield issue


def _media_issues(
    path: ArtifactPath, documents: Sequence[Mapping[str, Any]]
) -> Iterable[LessonIssue]:
    for document in documents:
        media = document.get("media")
        media_ids = set(media) if isinstance(media, Mapping) else set()
        for node in _walk(document):
            kind = _text(node.get("object")) or _text(node.get("kind"))
            status = _text(node.get("status") or node.get("media_status")).lower()
            required = bool(node.get("required") or node.get("media_required"))
            is_figure = kind in {"figure", "visual"} or "figure" in kind.lower()
            has_asset = bool(
                node.get("src")
                or node.get("image_url")
                or node.get("asset")
                or node.get("asset_id") in media_ids
                or node.get("media_id") in media_ids
            )
            if is_figure and _unavailable_reason(node) is not None:
                continue  # shipped unavailable placeholder; reported by _plan_visual_issues
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


class _SectionIndex:
    """Section titles and node -> section lookups from the shared document."""

    def __init__(self, sections: Sequence[Mapping[str, Any]]) -> None:
        self.titles: dict[str, str] = {}
        self.node_section: dict[str, str] = {}
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            section_id = _text(section.get("id"))
            if not section_id:
                continue
            title = _text(section.get("title"))
            if title:
                self.titles[section_id] = title
            for node in section.get("nodes") or []:
                node_id = _text(node.get("id")) if isinstance(node, Mapping) else ""
                if node_id:
                    self.node_section[node_id] = section_id

    def section_for_nodes(self, node_ids: Iterable[str]) -> str | None:
        for node_id in node_ids:
            if node_id in self.node_section:
                return self.node_section[node_id]
        return None


def _with_section(
    issue: LessonIssue,
    index: _SectionIndex,
    *,
    section_id: str | None,
    section_title: str | None = None,
    previous_section_title: str | None = None,
) -> LessonIssue:
    if section_id is None:
        return issue
    return issue.model_copy(
        update={
            "section_id": section_id,
            "section_title": section_title or index.titles.get(section_id),
            "previous_section_title": previous_section_title,
        }
    )


def _flag_issue(
    *,
    path: ArtifactPath,
    flag: Mapping[str, Any],
    index: _SectionIndex,
) -> LessonIssue | None:
    """Project one persisted QualityFlag; codes outside ``FLAG_COPY`` are dropped."""
    code = _text(flag.get("code"))
    copy = FLAG_COPY.get(code)
    message = _text(flag.get("message"))
    section_id = _text(flag.get("section_id"))
    if copy is None or not message or not section_id:
        return None
    node_ids = tuple(_text(node) for node in flag.get("node_ids") or () if _text(node))
    previous_id = _text(flag.get("previous_section_id"))
    # The id only keys dismissals and de-duplication; it is never shown.
    target = "|".join(part for part in (section_id, previous_id, *node_ids) if part)
    issue = LessonIssue(
        id=_stable_id(path, code, target),
        path=path,
        severity="warning",
        category="figure" if code == "figure_media_unavailable" else "document",
        code=code,
        message=copy.message or message,
        target_id=target,
        repairable=False,
        source=_text(flag.get("source")) or "document_qa",
        group=copy.group,
        suggestion=copy.suggestion,
        details=message if copy.message else None,
        dismissible=copy.group == "needs_look",
    )
    return _with_section(
        issue,
        index,
        section_id=section_id,
        section_title=_text(flag.get("next_section_title")) or None,
        previous_section_title=_text(flag.get("previous_section_title")) or None,
    )


def collect_lesson_issues(
    *,
    path: ArtifactPath,
    realization: Mapping[str, Any] | None = None,
    states: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Mapping[str, Any]] = (),
    booklet_issues: Sequence[Any] = (),
    generation_errors: Sequence[str] = (),
    quality_flags: Sequence[Mapping[str, Any]] = (),
    shared_sections: Sequence[Mapping[str, Any]] = (),
    dismissed_issue_ids: Collection[str] = (),
) -> LessonIssuesResponse:
    """Collect and deterministically normalize all known issues for one path.

    Pure: the caller loads the persisted document-QA ``quality_flags``, the
    shared document's ``shared_sections`` (id / title / nodes) and the
    ``dismissed_issue_ids`` for the lesson output and passes them in. Only
    allow-listed teacher-facing codes are projected.
    """
    found: dict[tuple[str, str, str], LessonIssue] = {}
    index = _SectionIndex(shared_sections)
    figure_nodes: dict[str, set[str]] = {}

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
    if realization and documents:
        ready = _text(realization.get("status")).lower() in _READY_REALIZATION_STATUSES
        for issue in _plan_visual_issues(
            path,
            documents,
            _plan_visual_blocks(states),
            realization_ready=ready,
            figure_nodes_out=figure_nodes,
        ):
            add(issue)
    for issue in _document_contract_issues(path, documents):
        add(issue)
    # Legacy booklet layout issues carry free-form codes and none is on the
    # teacher-facing allow-list, so they are excluded (allow-list, not deny-list).
    for raw in booklet_issues:
        if isinstance(raw, Mapping):
            add(
                _as_issue(
                    path=path,
                    raw=raw,
                    source="print_document",
                    default_category="document",
                    allowed={},
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

    # Document-QA / boundary advisories. A figure fallback already reported by the
    # plan-visual check for the same figure is not shown twice.
    covered_figures = {
        node_id
        for issue in found.values()
        if issue.code == "REQUIRED_FIGURE_MISSING" and issue.group == "needs_look"
        for node_id in figure_nodes.get(issue.target_id or "", ())
    }
    for flag in quality_flags:
        if not isinstance(flag, Mapping):
            continue
        if _text(flag.get("code")) == "figure_media_unavailable" and covered_figures.intersection(
            _text(node) for node in flag.get("node_ids") or ()
        ):
            continue
        add(_flag_issue(path=path, flag=flag, index=index))

    resolved: list[LessonIssue] = []
    for issue in found.values():
        if issue.section_id is None and issue.code == "REQUIRED_FIGURE_MISSING":
            nodes = figure_nodes.get(issue.target_id or "", set()) | {issue.target_id or ""}
            issue = _with_section(issue, index, section_id=index.section_for_nodes(sorted(nodes)))
        if issue.dismissible and issue.id in dismissed_issue_ids:
            issue = issue.model_copy(update={"dismissed": True})
        resolved.append(issue)

    issues = sorted(
        resolved,
        key=lambda item: (
            _group_rank(item.group),
            item.category,
            item.code,
            item.target_id or "",
        ),
    )
    open_issues = [issue for issue in issues if not issue.dismissed]
    blocking = sum(issue.group == "blocking" for issue in open_issues)
    needs_look = sum(issue.group == "needs_look" for issue in open_issues)
    counts = LessonIssueCounts(
        info=sum(issue.severity == "info" for issue in issues),
        warning=sum(issue.severity == "warning" for issue in issues),
        error=sum(issue.severity == "error" for issue in issues),
        blocking=blocking,
        needs_look=needs_look,
        informational=sum(issue.group == "info" for issue in open_issues),
        dismissed=len(issues) - len(open_issues),
        attention=blocking + needs_look,
    )
    return LessonIssuesResponse(path=path, issues=issues, counts=counts)


__all__ = [
    "LessonIssue",
    "LessonIssueCounts",
    "LessonIssuesResponse",
    "collect_lesson_issues",
]

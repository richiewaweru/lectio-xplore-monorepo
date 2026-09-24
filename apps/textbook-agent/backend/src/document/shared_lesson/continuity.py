"""Deterministic continuity and boundary checks for shared lesson sections.

This module deliberately has no provider or persistence dependency. The
approved Teaching Plan supplies continuity intent; an already accepted
section is checked against that intent and an explicit composer shape.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.models import (
    CalloutNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    SharedLessonNode,
    SharedSection,
    TableNode,
    TaskAnchor,
)

IssueCode = str


class ContinuityIssue(BaseModel):
    """A typed, actionable QA result. Validators never rewrite content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_code: IssueCode = Field(min_length=1)
    affected_section_id: str = Field(min_length=1)
    affected_node_ids: tuple[str, ...] = ()
    explanation: str = Field(min_length=1)
    required_correction: str = Field(min_length=1)


class ExpectedNodeShape(BaseModel):
    """Code-owned node shape supplied by the accepted composition plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    kind: Literal[
        "paragraph",
        "heading",
        "list",
        "figure",
        "table",
        "callout",
        "task_anchor",
    ]
    teaching_block_id: str = Field(min_length=1)
    semantic_role: str | None = None
    task_spec_id: str | None = None


@dataclass(frozen=True)
class _TextPart:
    node_id: str
    text: str


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:['’][a-z0-9]+)?", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(
    r"(?:\{\{?[^}]+\}?\}|\[\[[^]]+\]\]|<%[^>]+%>|\b(?:TODO|TBD|PLACEHOLDER|INSERT[_ -]?HERE)\b)",
    re.IGNORECASE,
)
_INTERNAL_LABEL_RE = re.compile(
    r"\b(?:teaching[_ -]?block[_ -]?id|task[_ -]?spec[_ -]?id|section[_ -]?slot|"
    r"composition[_ -]?plan|semantic[_ -]?role|source[_ -]?ids?|must[_ -]?establish|"
    r"avoid[_ -]?repeating|bridge[_ -]?from[_ -]?previous)\b",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "that",
    "their",
    "this",
    "to",
    "use",
    "what",
    "when",
    "with",
}


def _tokens(value: str | None) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(value or "")
        if token.casefold() not in _STOP_WORDS and len(token) > 1
    }


def _meaningful(value: str | None) -> bool:
    return bool((value or "").strip())


def coerce_expected_node_shape(
    value: ExpectedNodeShape | Mapping[str, Any] | Any,
) -> ExpectedNodeShape:
    """Accept the composer equivalent without importing its module."""
    if isinstance(value, ExpectedNodeShape):
        return value
    if isinstance(value, Mapping):
        return ExpectedNodeShape.model_validate(value)
    payload = {
        "id": getattr(value, "id"),
        "kind": getattr(value, "kind"),
        "teaching_block_id": getattr(value, "teaching_block_id"),
        "semantic_role": getattr(value, "semantic_role", None),
        "task_spec_id": getattr(value, "task_spec_id", None),
    }
    return ExpectedNodeShape.model_validate(payload)


def _node_text(node: SharedLessonNode) -> str:
    if isinstance(node, (ParagraphNode, HeadingNode)):
        return node.display.text
    if isinstance(node, ListNode):
        return " ".join(node.display.items)
    if isinstance(node, FigureNode):
        return " ".join((node.display.caption, node.accessibility.alt_text))
    if isinstance(node, TableNode):
        return " ".join(
            (
                *node.display.headers,
                *(cell for row in node.display.rows for cell in row),
                node.display.caption,
            )
        )
    if isinstance(node, CalloutNode):
        return " ".join((node.display.title, node.display.body))
    return ""


def _node_parts(section: SharedSection) -> tuple[_TextPart, ...]:
    return tuple(
        _TextPart(node.id, _node_text(node))
        for node in section.nodes
        if not isinstance(node, TaskAnchor)
    )


def _all_text(section: SharedSection) -> str:
    return " ".join((section.title, *(part.text for part in _node_parts(section))))


def _coverage(statement: str | None, text: str) -> bool:
    expected = _tokens(statement)
    if not expected:
        return False
    observed = _tokens(text)
    overlap = len(expected & observed)
    return overlap >= 1 and overlap / len(expected) >= (0.5 if len(expected) > 2 else 1.0)


def _issue(
    code: str,
    section_id: str,
    explanation: str,
    correction: str,
    node_ids: Sequence[str] = (),
) -> ContinuityIssue:
    return ContinuityIssue(
        issue_code=code,
        affected_section_id=section_id,
        affected_node_ids=tuple(node_ids),
        explanation=explanation,
        required_correction=correction,
    )


def _shape_issues(
    section: SharedSection,
    expected_nodes: Sequence[ExpectedNodeShape | Mapping[str, Any] | Any],
) -> list[ContinuityIssue]:
    expected = tuple(coerce_expected_node_shape(item) for item in expected_nodes)
    actual = tuple(section.nodes)
    issues: list[ContinuityIssue] = []
    if len(actual) != len(expected):
        issues.append(
            _issue(
                "section_shape_mismatch",
                section.id,
                f"expected {len(expected)} nodes but received {len(actual)}",
                "Return exactly the accepted node count and preserve its order.",
                [node.id for node in actual],
            )
        )
    for position, (actual_node, expected_node) in enumerate(zip(actual, expected, strict=False)):
        node_ids = (actual_node.id,)
        if actual_node.id != expected_node.id:
            issues.append(
                _issue(
                    "node_id_mismatch",
                    section.id,
                    f"node {position} has id {actual_node.id!r}; expected {expected_node.id!r}",
                    "Restore the code-owned node ID from the accepted composition plan.",
                    node_ids,
                )
            )
        if actual_node.kind != expected_node.kind:
            issues.append(
                _issue(
                    "node_kind_mismatch",
                    section.id,
                    f"node {actual_node.id!r} is {actual_node.kind!r}; expected {expected_node.kind!r}",
                    "Restore the code-owned node kind from the accepted composition plan.",
                    node_ids,
                )
            )
        actual_owner = getattr(actual_node, "teaching_block_id", None)
        if actual_owner != expected_node.teaching_block_id:
            issues.append(
                _issue(
                    "node_owner_mismatch",
                    section.id,
                    f"node {actual_node.id!r} has owner {actual_owner!r}; expected {expected_node.teaching_block_id!r}",
                    "Restore the code-owned Teaching Plan block owner.",
                    node_ids,
                )
            )
        if expected_node.kind == "task_anchor" and isinstance(actual_node, TaskAnchor):
            if actual_node.task_spec_id != expected_node.task_spec_id:
                issues.append(
                    _issue(
                        "task_anchor_mismatch",
                        section.id,
                        f"anchor {actual_node.id!r} names {actual_node.task_spec_id!r}; expected {expected_node.task_spec_id!r}",
                        "Restore the accepted TaskAnchor task_spec_id and keep it adjacent to its block content.",
                        node_ids,
                    )
                )
    return issues


def _primitive_issues(section: SharedSection) -> list[ContinuityIssue]:
    issues: list[ContinuityIssue] = []
    known_ids = {section.id, *(node.id for node in section.nodes)}
    known_ids.update(
        owner for node in section.nodes if (owner := getattr(node, "teaching_block_id", None))
    )
    known_ids.update(
        task_id
        for node in section.nodes
        if isinstance(node, TaskAnchor) and (task_id := node.task_spec_id)
    )
    for node in section.nodes:
        if isinstance(node, TaskAnchor):
            if not _meaningful(node.id) or not _meaningful(node.task_spec_id):
                issues.append(
                    _issue(
                        "incomplete_task_anchor",
                        section.id,
                        "TaskAnchor identity is incomplete.",
                        "Provide the accepted task_spec_id, teaching_block_id, and stable anchor id.",
                        [node.id],
                    )
                )
            continue
        text = _node_text(node)
        if _PLACEHOLDER_RE.search(text) or _INTERNAL_LABEL_RE.search(text):
            issues.append(
                _issue(
                    "metadata_or_placeholder_leak",
                    section.id,
                    f"learner-facing fields on node {node.id!r} contain placeholder or planning metadata",
                    "Rewrite only this node's learner-facing fields using approved content.",
                    [node.id],
                )
            )
        if any(
            len(identifier) >= 3
            and re.search(
                rf"(?<![A-Za-z0-9]){re.escape(identifier)}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            )
            for identifier in known_ids
        ):
            issues.append(
                _issue(
                    "internal_id_leak",
                    section.id,
                    f"learner-facing fields on node {node.id!r} contain an internal artifact identifier",
                    "Remove internal IDs from learner-facing text while preserving the node identity in code.",
                    [node.id],
                )
            )
        if isinstance(node, HeadingNode) and node.display.level != 3:
            issues.append(
                _issue(
                    "heading_hierarchy_invalid",
                    section.id,
                    f"ordinary heading {node.id!r} uses level {node.display.level}; section title is the structural H2",
                    "Use level 3 for an ordinary subsection heading.",
                    [node.id],
                )
            )
        if isinstance(node, ListNode) and any(not _meaningful(item) for item in node.display.items):
            issues.append(
                _issue(
                    "list_item_blank",
                    section.id,
                    f"list {node.id!r} contains a blank item",
                    "Provide meaningful learner-facing text for every list item.",
                    [node.id],
                )
            )
        if isinstance(node, FigureNode) and not _meaningful(node.accessibility.alt_text):
            issues.append(
                _issue(
                    "figure_alt_text_missing",
                    section.id,
                    f"figure {node.id!r} has no meaningful alternative text",
                    "Add concise alternative text that conveys the figure's instructional meaning.",
                    [node.id],
                )
            )
        if isinstance(node, TableNode):
            widths = {len(row) for row in node.display.rows}
            if widths and (
                len(widths) != 1
                or (node.display.headers and next(iter(widths)) != len(node.display.headers))
            ):
                issues.append(
                    _issue(
                        "table_shape_invalid",
                        section.id,
                        f"table {node.id!r} has inconsistent row and header widths",
                        "Return a rectangular table with row cells matching the header count.",
                        [node.id],
                    )
                )
    if not _meaningful(section.title):
        issues.append(
            _issue(
                "section_title_missing",
                section.id,
                "section title is blank",
                "Use the approved learner-facing section title.",
            )
        )
    return issues


def validate_section_continuity(
    *,
    section: SharedSection,
    teaching_plan_section: TeachingPlanSection,
    expected_nodes: Sequence[ExpectedNodeShape | Mapping[str, Any] | Any],
    approved_source_ids: Sequence[str] = (),
    source_facts: Sequence[str] = (),
) -> tuple[ContinuityIssue, ...]:
    """Return deterministic and continuity issues for one accepted section."""
    issues = _shape_issues(section, expected_nodes)
    issues.extend(_primitive_issues(section))
    if teaching_plan_section.display_title and section.title != teaching_plan_section.display_title:
        issues.append(
            _issue(
                "section_title_mismatch",
                section.id,
                f"section title {section.title!r} does not match approved title {teaching_plan_section.display_title!r}",
                "Use the approved Teaching Plan display_title exactly.",
            )
        )
    if approved_source_ids:
        approved = set(approved_source_ids)
        unknown = set(section.provenance.source_ids) - approved
        if unknown:
            issues.append(
                _issue(
                    "source_lineage_mismatch",
                    section.id,
                    f"section cites source IDs that are not approved: {sorted(unknown)!r}",
                    "Remove unsupported source references or use approved source IDs.",
                )
            )

    block_ids = {block.id for block in teaching_plan_section.blocks}
    owned_blocks = {
        owner for node in section.nodes if (owner := getattr(node, "teaching_block_id", None))
    }
    for missing_block in sorted(block_ids - owned_blocks):
        issues.append(
            _issue(
                "teaching_block_unrealized",
                section.id,
                f"Teaching Plan block {missing_block!r} has no authored node",
                "Add the accepted composition's node for this block, or repair only this section.",
            )
        )

    text = _all_text(section)
    for statement in teaching_plan_section.must_establish or ():
        if not _coverage(statement, text):
            issues.append(
                _issue(
                    "must_establish_uncovered",
                    section.id,
                    f"approved continuity requirement {statement!r} is not realized by the section",
                    "Add learner-facing content that establishes the approved requirement.",
                    [node.id for node in section.nodes if not isinstance(node, TaskAnchor)],
                )
            )
    for statement in teaching_plan_section.avoid_repeating or ():
        if _coverage(statement, text):
            issues.append(
                _issue(
                    "avoid_repeating_violated",
                    section.id,
                    f"section repeats an approved avoided concept: {statement!r}",
                    "Remove repeated explanatory content while preserving new instructional work.",
                    [node.id for node in section.nodes if not isinstance(node, TaskAnchor)],
                )
            )
    if teaching_plan_section.bridge_from_previous and not _coverage(
        teaching_plan_section.bridge_from_previous, text
    ):
        issues.append(
            _issue(
                "bridge_unrealized",
                section.id,
                "approved bridge_from_previous is absent from learner-facing section content",
                "Add the approved bridge in the first affected section nodes.",
                [node.id for node in section.nodes[:2]],
            )
        )
    if teaching_plan_section.exit_state and not any(
        _coverage(statement, text) for statement in teaching_plan_section.exit_state
    ):
        issues.append(
            _issue(
                "exit_state_unrealized",
                section.id,
                "the authored section does not show a path toward any approved exit state",
                "Close the section with learner-facing content that reaches an approved exit state.",
                [node.id for node in section.nodes[-2:]],
            )
        )
    if source_facts:
        facts = " ".join(source_facts)
        for statement in teaching_plan_section.must_establish or ():
            if _coverage(statement, text) and not _coverage(statement, facts):
                issues.append(
                    _issue(
                        "unsupported_required_fact",
                        section.id,
                        f"required statement {statement!r} is not represented in approved source facts",
                        "Use only the approved source facts or correct the Teaching Plan source boundary.",
                    )
                )
    return tuple(issues)


def validate_section_boundary(
    *,
    previous_section: SharedSection,
    previous_plan: TeachingPlanSection,
    next_section: SharedSection,
    next_plan: TeachingPlanSection,
    lookaround_nodes: int = 3,
) -> tuple[ContinuityIssue, ...]:
    """Check one adjacent section boundary using deterministic token signals."""
    previous_text = " ".join(
        _node_text(node)
        for node in previous_section.nodes[-lookaround_nodes:]
        if not isinstance(node, TaskAnchor)
    )
    next_text = " ".join(
        _node_text(node)
        for node in next_section.nodes[:lookaround_nodes]
        if not isinstance(node, TaskAnchor)
    )
    issues: list[ContinuityIssue] = []
    bridge = next_plan.bridge_from_previous
    if bridge and not _coverage(bridge, next_text):
        issues.append(
            _issue(
                "boundary_bridge_missing",
                next_section.id,
                "the next section's opening nodes do not realize bridge_from_previous",
                "Repair the opening nodes of this section with the approved bridge.",
                [node.id for node in next_section.nodes[:lookaround_nodes]],
            )
        )
    if next_plan.entry_state and not all(
        _coverage(statement, f"{previous_text} {next_text}") for statement in next_plan.entry_state
    ):
        issues.append(
            _issue(
                "boundary_prerequisite_gap",
                next_section.id,
                "the adjacent sections do not establish the next section's entry state",
                "Add a concise prerequisite bridge in the next section opening.",
                [node.id for node in next_section.nodes[:lookaround_nodes]],
            )
        )
    if previous_plan.exit_state and not all(
        _coverage(statement, previous_text) for statement in previous_plan.exit_state
    ):
        issues.append(
            _issue(
                "boundary_exit_state_missing",
                previous_section.id,
                "the previous section's closing nodes do not realize its approved exit state",
                "Repair the previous section's closing nodes before relying on this boundary.",
                [node.id for node in previous_section.nodes[-lookaround_nodes:]],
            )
        )
    previous_tokens = _tokens(previous_text)
    next_tokens = _tokens(next_text)
    if previous_tokens and next_tokens:
        overlap = len(previous_tokens & next_tokens) / max(
            1, min(len(previous_tokens), len(next_tokens))
        )
        if overlap >= 0.75 and len(previous_tokens & next_tokens) >= 3:
            issues.append(
                _issue(
                    "boundary_repetition",
                    next_section.id,
                    "the adjacent opening repeats too much of the previous section's closing terminology",
                    "Retain the bridge while removing repeated explanatory wording.",
                    [node.id for node in previous_section.nodes[-lookaround_nodes:]]
                    + [node.id for node in next_section.nodes[:lookaround_nodes]],
                )
            )
    return tuple(issues)


class SectionRepairRequest(BaseModel):
    """Bounded input to an outer AuthoringEngine repair adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str = Field(min_length=1)
    section: SharedSection
    issues: tuple[ContinuityIssue, ...] = Field(min_length=1)


class SectionRepairEngine(Protocol):
    async def repair_section(self, request: SectionRepairRequest) -> SharedSection:
        """Return only the affected section using the configured authoring stack."""


class BoundedRepairExhausted(ValueError):
    """The one allowed targeted repair did not produce a valid section."""

    def __init__(self, issues: Sequence[ContinuityIssue]):
        self.issues = tuple(issues)
        super().__init__(
            "targeted section repair exhausted: "
            + "; ".join(issue.issue_code for issue in self.issues)
        )


async def repair_affected_section_once(
    *,
    request: SectionRepairRequest,
    engine: SectionRepairEngine,
    validate: Any,
) -> SharedSection:
    """Run exactly one affected-section repair, then revalidate it."""
    repaired = await engine.repair_section(request)
    if repaired.id != request.section_id:
        issue = _issue(
            "repair_changed_section_identity",
            request.section_id,
            f"repair returned section {repaired.id!r}",
            "Return the same affected section ID and preserve sibling sections.",
        )
        raise BoundedRepairExhausted((issue,))
    remaining = tuple(validate(repaired))
    if remaining:
        raise BoundedRepairExhausted(remaining)
    return repaired


__all__ = [
    "BoundedRepairExhausted",
    "ContinuityIssue",
    "ExpectedNodeShape",
    "SectionRepairEngine",
    "SectionRepairRequest",
    "coerce_expected_node_shape",
    "repair_affected_section_once",
    "validate_section_boundary",
    "validate_section_continuity",
]

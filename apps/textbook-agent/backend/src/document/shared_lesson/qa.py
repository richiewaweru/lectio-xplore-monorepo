"""Final deterministic QA for an immutable SharedLessonDocument."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.continuity import (
    ContinuityIssue,
    ExpectedNodeShape,
    validate_section_boundary,
    validate_section_continuity,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from infra.config import settings

# Boundary WorkItems and final semantic QA own narrative judgments. Keep this
# exact allowlist narrow so metadata, shape, source, and future unknown issues
# continue to block deterministic readiness.
_SEMANTIC_CONTINUITY_ISSUE_CODES = frozenset(
    {
        "must_establish_uncovered",
        "avoid_repeating_violated",
        "bridge_unrealized",
        "exit_state_unrealized",
        "boundary_bridge_missing",
        "boundary_prerequisite_gap",
        "boundary_exit_state_missing",
        "boundary_repetition",
    }
)


#: Public alias: narrative boundary/continuity codes that are advisory, never hard.
NARRATIVE_CONTINUITY_ISSUE_CODES = _SEMANTIC_CONTINUITY_ISSUE_CODES


#: Explicit hard/advisory classification of every deterministic document QA
#: issue code. "hard" means the document is structurally broken (missing or
#: mismatched nodes, lineage, hash, contract, media): it can never be READY.
#: "advisory" means a learner-content quality opinion that the Learn/Print
#: adapters do not depend on: in ``document_quality_gate="advisory"`` mode it is
#: recorded as a teacher-visible flag instead of blocking READY. A code absent
#: from this table is treated as hard.
DETERMINISTIC_ISSUE_CLASSIFICATION: dict[str, str] = {
    "section_count_mismatch": "hard",
    "document_title_mismatch": "hard",
    "document_hash_mismatch": "hard",
    "section_order_mismatch": "hard",
    "unplanned_section": "hard",
    "expected_shape_missing": "hard",
    "section_shape_mismatch": "hard",
    "node_id_mismatch": "hard",
    "node_kind_mismatch": "hard",
    "node_owner_mismatch": "hard",
    "task_anchor_mismatch": "hard",
    "incomplete_task_anchor": "hard",
    "table_shape_invalid": "hard",
    "list_item_blank": "hard",
    "figure_alt_text_missing": "hard",
    "section_title_missing": "hard",
    "section_title_mismatch": "hard",
    "source_lineage_mismatch": "hard",
    "required_media_missing": "hard",
    # Retries exhausted: the lesson ships with a labelled placeholder. Only a
    # figure with NO media outcome at all is ``required_media_missing`` (hard).
    "figure_media_unavailable": "advisory",
    "repair_changed_section_identity": "hard",
    "metadata_or_placeholder_leak": "advisory",
    "internal_id_leak": "advisory",
    "heading_hierarchy_invalid": "advisory",
    "teaching_block_unrealized": "hard",
    "unsupported_required_fact": "advisory",
    # Narrative judgments already excluded from final deterministic QA (see
    # ``_SEMANTIC_CONTINUITY_ISSUE_CODES``); listed so the table is exhaustive.
    **{code: "advisory" for code in _SEMANTIC_CONTINUITY_ISSUE_CODES},
}


def is_advisory_deterministic_code(code: str) -> bool:
    return DETERMINISTIC_ISSUE_CLASSIFICATION.get(code) == "advisory"


def split_media_outcomes(
    results: Sequence[Any],
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Split bound media outcomes into ready figure ids and unavailable ``id -> reason``.

    Duck-typed on ``status`` so QA keeps no import dependency on the media contract.
    """
    ready: list[str] = []
    unavailable: dict[str, str] = {}
    for result in results:
        if getattr(result, "status", "ready") == "unavailable":
            unavailable[result.figure_node_id] = result.reason
        else:
            ready.append(result.figure_node_id)
    return tuple(ready), unavailable


class DocumentQAResult(BaseModel):
    """The complete final QA result; READY is derived from zero blocking issues.

    ``advisory_issues`` (only populated in advisory quality-gate mode) are
    recorded quality findings that do not block READY.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str = Field(min_length=1)
    document_revision: int = Field(ge=1)
    issues: tuple[ContinuityIssue, ...] = ()
    advisory_issues: tuple[ContinuityIssue, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.issues


class DocumentQAError(ValueError):
    """Raised when a document cannot become READY after deterministic QA."""

    def __init__(self, result: DocumentQAResult):
        self.result = result
        super().__init__(
            "shared lesson document is not ready: "
            + "; ".join(issue.issue_code for issue in result.issues)
        )


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


def _expected_for_section(
    expected_shapes: Mapping[str, Sequence[ExpectedNodeShape | Mapping[str, Any] | Any]],
    section_id: str,
    plan_section: TeachingPlanSection,
) -> Sequence[ExpectedNodeShape | Mapping[str, Any] | Any] | None:
    if section_id in expected_shapes:
        return expected_shapes[section_id]
    if plan_section.slot_id in expected_shapes:
        return expected_shapes[plan_section.slot_id]
    return None


def qa_shared_lesson_document(
    *,
    document: SharedLessonDocument,
    teaching_plan_sections: Sequence[TeachingPlanSection],
    expected_shapes: Mapping[str, Sequence[ExpectedNodeShape | Mapping[str, Any] | Any]],
    expected_title: str | None = None,
    approved_source_ids: Sequence[str] = (),
    source_facts_by_section: Mapping[str, Sequence[str]] | None = None,
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    available_media_ids: Sequence[str] = (),
    unavailable_media: Mapping[str, str] | None = None,
) -> DocumentQAResult:
    """Run final section, boundary, lineage, media and hash checks.

    This helper only reports issues. It never edits the document or performs a
    whole-lesson rewrite. A caller may target a single returned section ID for
    the bounded repair contract.
    """
    issues: list[ContinuityIssue] = []
    #: Always advisory (in every quality-gate mode): an exhausted figure must
    #: never stop the lesson from shipping.
    unavailable_issues: list[ContinuityIssue] = []
    sections = tuple(document.sections)
    plans = tuple(teaching_plan_sections)
    source_facts_by_section = source_facts_by_section or {}
    required_media_by_section = required_media_by_section or {}
    unavailable_media = unavailable_media or {}

    if len(sections) != len(plans):
        issues.append(
            _issue(
                "section_count_mismatch",
                sections[0].id if sections else "document",
                f"document has {len(sections)} sections but the approved plan has {len(plans)}",
                "Assemble exactly one authored section per approved Teaching Plan section.",
            )
        )

    if expected_title is not None and document.title != expected_title:
        issues.append(
            _issue(
                "document_title_mismatch",
                sections[0].id if sections else "document",
                f"document title {document.title!r} does not match approved title {expected_title!r}",
                "Use the approved learner-facing title exactly.",
            )
        )

    if shared_lesson_content_hash(document) != document.content_hash:
        issues.append(
            _issue(
                "document_hash_mismatch",
                sections[0].id if sections else "document",
                "document content_hash does not match canonical learner-significant content",
                "Reject this artifact and rebuild from the accepted immutable inputs.",
            )
        )

    for index, section in enumerate(sections):
        if section.position != index:
            issues.append(
                _issue(
                    "section_order_mismatch",
                    section.id,
                    f"section position is {section.position}; expected {index}",
                    "Restore the accepted section order before marking the document READY.",
                )
            )
        if index >= len(plans):
            issues.append(
                _issue(
                    "unplanned_section",
                    section.id,
                    "document contains a section without an approved Teaching Plan section",
                    "Remove the unplanned section and preserve only approved section identities.",
                )
            )
            continue
        plan_section = plans[index]
        shape = _expected_for_section(expected_shapes, section.id, plan_section)
        if shape is None:
            issues.append(
                _issue(
                    "expected_shape_missing",
                    section.id,
                    "no accepted composition shape was supplied for this section",
                    "Supply the code-owned accepted shape before writing or QA.",
                )
            )
            continue
        section_issues = validate_section_continuity(
            section=section,
            teaching_plan_section=plan_section,
            expected_nodes=shape,
            approved_source_ids=approved_source_ids,
            source_facts=source_facts_by_section.get(section.id, ()),
        )
        issues.extend(
            issue
            for issue in section_issues
            if issue.issue_code not in _SEMANTIC_CONTINUITY_ISSUE_CODES
        )

        required_media = set(required_media_by_section.get(section.id, ()))
        if required_media:
            available = set(available_media_ids)
            unavailable_here = sorted((required_media - available) & set(unavailable_media))
            missing = sorted(required_media - available - set(unavailable_media))
            for figure_id in unavailable_here:
                unavailable_issues.append(
                    _issue(
                        "figure_media_unavailable",
                        section.id,
                        unavailable_media[figure_id],
                        "Retry figure generation, or replace the figure in the editor.",
                        [figure_id],
                    )
                )
            if missing:
                issues.append(
                    _issue(
                        "required_media_missing",
                        section.id,
                        f"required media is not ready: {missing!r}",
                        "Complete required media generation or fail the document before READY.",
                        [node.id for node in section.nodes if isinstance(node, FigureNode)],
                    )
                )

    for previous, previous_plan, current, current_plan in zip(
        sections,
        plans,
        sections[1:],
        plans[1:],
        strict=False,
    ):
        boundary_issues = validate_section_boundary(
            previous_section=previous,
            previous_plan=previous_plan,
            next_section=current,
            next_plan=current_plan,
        )
        issues.extend(
            issue
            for issue in boundary_issues
            if issue.issue_code not in _SEMANTIC_CONTINUITY_ISSUE_CODES
        )

    advisory: list[ContinuityIssue] = list(unavailable_issues)
    if settings.document_quality_gate == "advisory":
        gated = [issue for issue in issues if is_advisory_deterministic_code(issue.issue_code)]
        advisory = advisory + gated
        issues = [issue for issue in issues if issue not in gated]
    return DocumentQAResult(
        document_id=document.id,
        document_revision=document.revision,
        issues=tuple(issues),
        advisory_issues=tuple(advisory),
    )


def require_ready_document(result: DocumentQAResult) -> None:
    """Enforce the final READY gate without mutating the immutable artifact."""
    if not result.ready:
        raise DocumentQAError(result)


__all__ = [
    "DocumentQAError",
    "DETERMINISTIC_ISSUE_CLASSIFICATION",
    "DocumentQAResult",
    "is_advisory_deterministic_code",
    "qa_shared_lesson_document",
    "require_ready_document",
    "split_media_outcomes",
]

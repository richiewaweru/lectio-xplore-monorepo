from __future__ import annotations

import pytest

from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson import (
    SharedLessonAssemblyError,
    SharedSection,
    assemble_shared_lesson_document,
)
from document.shared_lesson.models import (
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    ParagraphDisplay,
    ParagraphNode,
)
from document.shared_lesson.qa import DocumentQAError
from document.shared_lesson.continuity import ExpectedNodeShape


PLAN_HASH = "a" * 64


def _plan(slot_id: str, title: str, block_id: str) -> TeachingPlanSection:
    return TeachingPlanSection(
        slot_id=slot_id,
        display_title=title,
        blocks=[
            TeachingPlanBlock(
                id=block_id,
                position=0,
                intent="Explain the concept",
                brief="Give a concise explanation",
                evidence="The learner can explain the concept",
            )
        ],
    )


def _paragraph_section(
    slot_id: str,
    title: str,
    block_id: str,
    position: int,
    text: str = "Plants use light.",
) -> SharedSection:
    return SharedSection(
        id=slot_id,
        title=title,
        position=position,
        nodes=(
            ParagraphNode(
                id=f"{slot_id}-paragraph",
                teaching_block_id=block_id,
                display=ParagraphDisplay(text=text),
            ),
        ),
    )


def _shape(slot_id: str, block_id: str) -> tuple[ExpectedNodeShape, ...]:
    return (
        ExpectedNodeShape(
            id=f"{slot_id}-paragraph",
            kind="paragraph",
            teaching_block_id=block_id,
            semantic_role="explanation",
        ),
    )


def _assemble(
    sections: list[SharedSection] | dict[str, SharedSection],
    *,
    approval: str = "approved",
    expected_content_hash: str | None = None,
    required_media_by_section: dict[str, tuple[str, ...]] | None = None,
):
    plans = (
        _plan("section-1", "Introduction", "block-1"),
        _plan("section-2", "Application", "block-2"),
    )
    return assemble_shared_lesson_document(
        document_id="document-1",
        revision=1,
        teaching_plan_id="plan-1",
        teaching_plan_revision=3,
        teaching_plan_hash=PLAN_HASH,
        teaching_plan_approval_status=approval,  # type: ignore[arg-type]
        title="Light and energy",
        teaching_plan_sections=plans,
        accepted_sections=sections,
        created_at="2026-09-24T09:00:00+03:00",
        expected_shapes={
            "section-1": _shape("section-1", "block-1"),
            "section-2": _shape("section-2", "block-2"),
        },
        required_media_by_section=required_media_by_section,
        expected_content_hash=expected_content_hash,
    )


def test_mapping_sections_are_assembled_in_teaching_plan_order_and_ready() -> None:
    section_one = _paragraph_section("section-1", "Introduction", "block-1", 0)
    section_two = _paragraph_section("section-2", "Application", "block-2", 1)

    result = _assemble({"section-2": section_two, "section-1": section_one})

    assert result.ready
    assert [section.id for section in result.document.sections] == ["section-1", "section-2"]
    assert result.require_ready() == result.document


@pytest.mark.parametrize(
    ("sections", "issue_code"),
    [
        (
            lambda: [
                _paragraph_section("section-2", "Application", "block-2", 1),
                _paragraph_section("section-1", "Introduction", "block-1", 0),
            ],
            "section_order_mismatch",
        ),
        (
            lambda: [
                _paragraph_section("section-1", "Introduction", "block-1", 0),
            ],
            "section_count_mismatch",
        ),
        (
            lambda: [
                _paragraph_section("section-1", "Introduction", "block-1", 0),
                _paragraph_section("section-1", "Introduction", "block-1", 0),
            ],
            "duplicate_section",
        ),
    ],
)
def test_section_identity_and_order_fail_closed(sections, issue_code: str) -> None:
    with pytest.raises(SharedLessonAssemblyError) as raised:
        _assemble(sections())

    assert issue_code in {issue.issue_code for issue in raised.value.issues}


def test_pending_teaching_plan_cannot_be_treated_as_approved() -> None:
    sections = [
        _paragraph_section("section-1", "Introduction", "block-1", 0),
        _paragraph_section("section-2", "Application", "block-2", 1),
    ]

    with pytest.raises(SharedLessonAssemblyError) as raised:
        _assemble(sections, approval="pending")

    assert raised.value.issues[0].issue_code == "teaching_plan_not_approved"


def test_expected_hash_mismatch_blocks_assembly() -> None:
    sections = [
        _paragraph_section("section-1", "Introduction", "block-1", 0),
        _paragraph_section("section-2", "Application", "block-2", 1),
    ]

    with pytest.raises(SharedLessonAssemblyError) as raised:
        _assemble(sections, expected_content_hash="b" * 64)

    assert raised.value.issues[0].issue_code == "content_hash_mismatch"


def test_required_media_failure_returns_blocked_draft_and_preserves_siblings() -> None:
    plans = (
        _plan("section-1", "Introduction", "block-1"),
        _plan("section-2", "Application", "block-2"),
    )
    figure = SharedSection(
        id="section-1",
        title="Introduction",
        position=0,
        nodes=(
            FigureNode(
                id="section-1-figure",
                teaching_block_id="block-1",
                display=FigureDisplay(asset_id="figure-1", caption="A leaf"),
                accessibility=FigureAccessibility(alt_text="A leaf exposed to light"),
            ),
        ),
    )
    sibling = _paragraph_section("section-2", "Application", "block-2", 1)

    result = assemble_shared_lesson_document(
        document_id="document-1",
        revision=1,
        teaching_plan_id="plan-1",
        teaching_plan_revision=3,
        teaching_plan_hash=PLAN_HASH,
        teaching_plan_approval_status="approved",
        title="Light and energy",
        teaching_plan_sections=plans,
        accepted_sections={"section-1": figure, "section-2": sibling},
        created_at="2026-09-24T09:00:00+03:00",
        expected_shapes={
            "section-1": (
                ExpectedNodeShape(
                    id="section-1-figure",
                    kind="figure",
                    teaching_block_id="block-1",
                    semantic_role="explanation",
                ),
            ),
            "section-2": _shape("section-2", "block-2"),
        },
        required_media_by_section={"section-1": ("figure-1",)},
    )

    assert not result.ready
    assert any(issue.issue_code == "required_media_missing" for issue in result.qa.issues)
    assert result.document.sections[1] == sibling
    with pytest.raises(DocumentQAError):
        result.require_ready()


def test_qa_issue_returns_immutable_draft_without_rewriting_sibling() -> None:
    sections = [
        _paragraph_section("section-1", "Introduction", "block-1", 0, text="TODO"),
        _paragraph_section("section-2", "Application", "block-2", 1),
    ]

    result = _assemble(sections)

    assert not result.ready
    assert any(issue.issue_code == "metadata_or_placeholder_leak" for issue in result.qa.issues)
    assert result.document.sections[0].nodes[0].display.text == "TODO"
    assert result.document.sections[1] == sections[1]

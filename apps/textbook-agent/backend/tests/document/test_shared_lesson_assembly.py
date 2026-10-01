from __future__ import annotations

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import (
    SharedLessonAssemblyError,
    SharedSection,
    assemble_shared_lesson_document,
)
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.models import (
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    ParagraphDisplay,
    ParagraphNode,
)
from document.shared_lesson.qa import DocumentQAError
from document.shared_lesson.runtime import TeachingPlanSource


def _plan(slot_id: str, title: str, block_id: str) -> TeachingPlanSection:
    return TeachingPlanSection(
        slot_id=slot_id,
        specific_purpose=f"Teach {title}",
        display_title=title,
        entry_state=(
            ["The learner is ready to learn"]
            if slot_id == "section-1"
            else ["The learner can explain Introduction"]
        ),
        must_establish=[
            f"The learner knows {title}"
            if slot_id == "section-1"
            else f"The learner understands {title}"
        ],
        avoid_repeating=[],
        bridge_from_previous=None if slot_id == "section-1" else "Build on the prior section",
        exit_state=[
            "The learner can explain Introduction"
            if slot_id == "section-1"
            else "The learner can apply Application"
        ],
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


def _source(plans: tuple[TeachingPlanSection, ...]) -> TeachingPlanSource:
    plan = TeachingPlan(
        arc="Teach light and energy",
        contract_version=2,
        learner_title="Light and energy",
        starting_state=["The learner is ready to learn"],
        target_state=["The learner can explain the idea"],
        teaching_plan_id="plan-1",
        revision=3,
        sections=list(plans),
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id="plan-1",
        revision=3,
        status="approved",
        preparation_hash="preparation-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T09:00:00Z",
        approved_at="2026-09-24T09:01:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id="plan-1",
        revision=3,
        content_hash=digest,
    )


def _paragraph_section(
    slot_id: str,
    title: str,
    block_id: str,
    position: int,
    text: str = "Plants use light.",
) -> SharedSection:
    if text == "Plants use light.":
        text = (
            f"{title}: The learner knows {title} and can explain {title}."
            if slot_id == "section-1"
            else f"{title}: The learner understands {title} and can apply {title}. "
            "Build on the prior section."
        )
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
    expected_content_hash: str | None = None,
    required_media_by_section: dict[str, tuple[str, ...]] | None = None,
):
    plans = (
        _plan("section-1", "Introduction", "block-1"),
        _plan("section-2", "Application", "block-2"),
    )
    source = _source(plans)
    return assemble_shared_lesson_document(
        document_id="document-1",
        revision=1,
        source=source,
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

    plans = (
        _plan("section-1", "Introduction", "block-1"),
        _plan("section-2", "Application", "block-2"),
    )
    source = _source(plans)
    pending_record = source.revision_record.model_copy(update={"status": "pending"})
    pending_source = source.model_copy(update={"revision_record": pending_record})

    with pytest.raises(SharedLessonAssemblyError) as raised:
        assemble_shared_lesson_document(
            document_id="document-1",
            revision=1,
            source=pending_source,
            accepted_sections=sections,
            created_at="2026-09-24T09:00:00+03:00",
        )

    assert raised.value.issues[0].issue_code == "teaching_plan_source_invalid"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda source: source.model_copy(update={"content_hash": "b" * 64}),
        lambda source: source.model_copy(update={"revision": 4}),
        lambda source: source.model_copy(
            update={
                "revision_record": source.revision_record.model_copy(
                    update={"content_hash": "c" * 64}
                )
            }
        ),
        lambda source: source.model_copy(
            update={"plan": source.plan.model_copy(update={"learner_title": "Forged title"})}
        ),
        lambda source: source.model_copy(
            update={"plan": source.plan.model_copy(update={"approval_status": "pending"})}
        ),
    ],
)
def test_forged_or_stale_teaching_plan_source_fails_before_draft(mutate) -> None:
    plans = (
        _plan("section-1", "Introduction", "block-1"),
        _plan("section-2", "Application", "block-2"),
    )
    source = mutate(_source(plans))
    with pytest.raises(SharedLessonAssemblyError, match="teaching_plan_source_invalid"):
        assemble_shared_lesson_document(
            document_id="document-1",
            revision=1,
            source=source,
            accepted_sections={},
            created_at="2026-09-24T09:00:00+03:00",
        )


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
        source=_source(plans),
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


@pytest.mark.usefixtures("blocking_quality_gate")
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

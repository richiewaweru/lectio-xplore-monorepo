from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.composer import (
    CompositionChoice,
    SectionCompositionPlan,
    validate_and_build_composition,
)
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.handoff import (
    SharedLessonHandoffError,
    handoff_accepted_sections_to_document,
)
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource


def _source() -> TeachingPlanSource:
    section = TeachingPlanSection(
        slot_id="explain",
        specific_purpose="Explain energy transfer",
        display_title="Energy transfer",
        entry_state=["recognize energy"],
        must_establish=["explain energy transfer"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["explain energy transfer"],
        blocks=[
            TeachingPlanBlock(
                id="explain-block",
                position=0,
                intent="Explain energy transfer",
                brief="Explain energy transfer clearly",
                evidence="The learner can explain energy transfer",
            )
        ],
    )
    plan = TeachingPlan(
        arc="Energy",
        contract_version=2,
        learner_title="Energy transfer",
        starting_state=["recognize energy"],
        target_state=["explain energy transfer"],
        teaching_plan_id="plan-1",
        revision=3,
        sections=[section],
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id="plan-1",
        revision=3,
        status="approved",
        preparation_hash="c" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-25T09:00:00Z",
        approved_at="2026-09-25T09:01:00Z",
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


def _accepted() -> tuple[TeachingPlanSource, SectionCompositionPlan, SharedSection]:
    source = _source()
    plan_section = source.plan.sections[0]
    composition = validate_and_build_composition(
        section=plan_section,
        choices=(
            CompositionChoice(
                teaching_block_id="explain-block",
                kind="paragraph",
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    node = composition.items[0]
    section = SharedSection(
        id="explain",
        title="Energy transfer",
        position=0,
        nodes=(
            ParagraphNode(
                id=node.id,
                teaching_block_id=node.teaching_block_id,
                display=ParagraphDisplay(
                    text="Energy transfer explains how energy moves from one system to another."
                ),
            ),
        ),
    )
    return source, composition, section


async def _handoff(
    *,
    source: TeachingPlanSource | None = None,
    composition: SectionCompositionPlan | None = None,
    section: SharedSection | None = None,
    semantic_validator=None,
):
    default_source, default_composition, default_section = _accepted()
    return await handoff_accepted_sections_to_document(
        source=source or default_source,
        compositions={"explain": composition or default_composition},
        sections={"explain": section or default_section},
        document_id="document-1",
        document_revision=1,
        created_at=datetime(2026, 9, 25, 12, tzinfo=UTC),
        semantic_validator=semantic_validator,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [
        _source().model_copy(update={"content_hash": "b" * 64}),
        _source().model_copy(
            update={"plan": _source().plan.model_copy(update={"approval_status": "pending"})}
        ),
    ],
)
async def test_handoff_rejects_unapproved_or_hash_mismatched_source(source) -> None:
    with pytest.raises(SharedLessonHandoffError, match="approved|hash"):
        await _handoff(source=source)


@pytest.mark.asyncio
async def test_handoff_rejects_forged_composition_shape() -> None:
    _, composition, _ = _accepted()
    forged = composition.model_copy(
        update={"items": (composition.items[0].model_copy(update={"id": "forged-node"}),)}
    )

    with pytest.raises(SharedLessonHandoffError, match="composition"):
        await _handoff(composition=forged)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("compositions", "sections", "message"),
    [
        ({}, {"explain": _accepted()[2]}, "missing composition"),
        (
            {"explain": _accepted()[1], "extra": _accepted()[1]},
            {"explain": _accepted()[2]},
            "unplanned composition",
        ),
        ([*_accepted()[1:2], _accepted()[1]], {"explain": _accepted()[2]}, "duplicate composition"),
        ({"explain": _accepted()[1]}, {}, "missing accepted section"),
    ],
)
async def test_handoff_rejects_missing_extra_or_duplicate_section_identity(
    compositions, sections, message: str
) -> None:
    with pytest.raises(SharedLessonHandoffError, match=message):
        await handoff_accepted_sections_to_document(
            source=_source(),
            compositions=compositions,
            sections=sections,
            document_id="document-1",
            document_revision=1,
            created_at=datetime(2026, 9, 25, 12, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_handoff_returns_blocked_evidence_for_semantic_issue() -> None:
    _, composition, section = _accepted()

    async def reviewer(_request):
        return {
            "status": "issue",
            "issues": [
                {
                    "issue_code": "progression_gap",
                    "affected_section_id": "explain",
                    "affected_node_ids": [composition.items[0].id],
                    "explanation": "The explanation is incomplete.",
                    "required_correction": "Explain the transfer step.",
                }
            ],
        }

    evidence = await _handoff(
        composition=composition,
        section=section,
        semantic_validator=reviewer,
    )

    assert evidence.status == "blocked"
    assert not evidence.ready
    assert evidence.semantic_qa.status == "issue"
    assert evidence.semantic_qa.semantic_calls == 1
    assert evidence.document.sections[0].nodes[0].id == composition.items[0].id


@pytest.mark.asyncio
async def test_handoff_rejects_stale_semantic_evidence(monkeypatch) -> None:
    import document.shared_lesson.handoff as handoff
    from document.shared_lesson.document_semantic import DocumentSemanticQAResult

    async def stale(**_kwargs):
        return DocumentSemanticQAResult(
            document_id="old-document",
            document_revision=9,
            document_hash="d" * 64,
            status="pass",
            semantic_calls=1,
        )

    monkeypatch.setattr(handoff, "qa_shared_lesson_document_semantics", stale)
    with pytest.raises(SharedLessonHandoffError, match="stale"):
        await _handoff()


@pytest.mark.asyncio
async def test_handoff_success_binds_source_document_and_exact_shapes() -> None:
    calls = 0

    async def reviewer(_request):
        nonlocal calls
        calls += 1
        return DocumentSemanticVerdict(status="pass")

    evidence = await _handoff(semantic_validator=reviewer)

    assert evidence.ready
    assert evidence.status == "ready"
    assert calls == 1
    assert evidence.teaching_plan_id == "plan-1"
    assert evidence.teaching_plan_revision == 3
    assert evidence.teaching_plan_hash == evidence.document.teaching_plan_hash
    assert evidence.semantic_qa.document_hash == evidence.document.content_hash
    assert tuple(evidence.expected_shapes) == ("explain",)
    assert evidence.expected_shapes["explain"][0] == ExpectedNodeShape(
        id=evidence.document.sections[0].nodes[0].id,
        kind="paragraph",
        teaching_block_id="explain-block",
        semantic_role="explanation",
    )
    with pytest.raises(TypeError):
        evidence.expected_shapes["explain"] = ()

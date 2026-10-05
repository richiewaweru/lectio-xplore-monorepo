from __future__ import annotations

import pytest

import document.shared_lesson.qa as qa_module
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson.continuity import (
    BoundedRepairExhausted,
    ContinuityIssue,
    ExpectedNodeShape,
    SectionRepairRequest,
    repair_affected_section_once,
    validate_section_boundary,
    validate_section_continuity,
)
from document.shared_lesson.models import (
    HeadingDisplay,
    HeadingNode,
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
    TableDisplay,
    TableNode,
    TaskAnchor,
    build_shared_lesson_document,
)
from document.shared_lesson.qa import (
    DocumentQAError,
    qa_shared_lesson_document,
    require_ready_document,
)


def _plan(
    slot_id: str,
    *,
    title: str,
    bridge: str | None = None,
    entry: list[str] | None = None,
    must: list[str] | None = None,
    avoid: list[str] | None = None,
    exit_state: list[str] | None = None,
    block_id: str = "b1",
) -> TeachingPlanSection:
    return TeachingPlanSection(
        slot_id=slot_id,
        display_title=title,
        bridge_from_previous=bridge,
        entry_state=entry or [],
        must_establish=must or [],
        avoid_repeating=avoid or [],
        exit_state=exit_state or [],
        blocks=[
            TeachingPlanBlock(
                id=block_id,
                position=0,
                intent="explain the concept",
                brief="explain the approved concept",
                evidence="learner can explain the concept",
            )
        ],
    )


def _section(
    section_id: str = "section-1",
    *,
    title: str = "Light and energy",
    text: str = "Light provides energy for photosynthesis.",
    block_id: str = "b1",
) -> SharedSection:
    return SharedSection(
        id=section_id,
        title=title,
        position=0,
        nodes=(
            ParagraphNode(
                id="node-1",
                teaching_block_id=block_id,
                display=ParagraphDisplay(text=text),
            ),
            TaskAnchor(
                id="anchor-1",
                task_spec_id="task-1",
                teaching_block_id=block_id,
            ),
        ),
    )


def _shape() -> tuple[ExpectedNodeShape, ...]:
    return (
        ExpectedNodeShape(
            id="node-1",
            kind="paragraph",
            teaching_block_id="b1",
            semantic_role="explanation",
        ),
        ExpectedNodeShape(
            id="anchor-1",
            kind="task_anchor",
            teaching_block_id="b1",
            task_spec_id="task-1",
        ),
    )


def test_valid_section_covers_plan_and_exact_composer_shape() -> None:
    issues = validate_section_continuity(
        section=_section(),
        teaching_plan_section=_plan(
            "section-1",
            title="Light and energy",
            must=["light energy"],
            exit_state=["explain light energy"],
        ),
        expected_nodes=_shape(),
    )

    assert issues == ()


def test_avoid_repetition_does_not_reject_topic_terms_required_for_new_content() -> None:
    section = _section(
        text=(
            "Glucose and oxygen are reactants; carbon dioxide, water, and ATP are products. "
            "Reactants are taken in and used up, while products are released or produced."
        )
    )
    plan = _plan(
        "section-1",
        title="Light and energy",
        avoid=[
            "Do not re-recall what glucose, oxygen, carbon dioxide, water, or ATP are; "
            "that recall happened in the opening section"
        ],
        must=[
            "Glucose and oxygen are reactants, while carbon dioxide, water, and ATP are products"
        ],
    )

    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=plan,
        expected_nodes=_shape(),
    )

    assert "avoid_repeating_violated" not in {issue.issue_code for issue in issues}


def test_avoid_repetition_still_rejects_repeated_content_without_required_detail() -> None:
    section = _section(text="Light energy supports photosynthesis and plant growth.")
    plan = _plan(
        "section-1",
        title="Light and energy",
        avoid=["Light energy supports photosynthesis and plant growth"],
    )

    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=plan,
        expected_nodes=_shape(),
    )

    assert "avoid_repeating_violated" in {issue.issue_code for issue in issues}


def test_avoid_repetition_still_rejects_repeat_in_another_sentence_with_required_detail() -> None:
    section = _section(
        text=(
            "Glucose and oxygen are reactants taken in and used up by the reaction. "
            "Recall: glucose is a sugar used for energy."
        )
    )
    plan = _plan(
        "section-1",
        title="Light and energy",
        avoid=["Do not repeat that glucose is a sugar used for energy"],
        must=["Glucose and oxygen are reactants taken in and used up by the reaction"],
    )

    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=plan,
        expected_nodes=_shape(),
    )

    assert "avoid_repeating_violated" in {issue.issue_code for issue in issues}


def test_shape_mismatch_reports_typed_issues_without_rewriting() -> None:
    section = _section()
    section = section.model_copy(
        update={
            "nodes": (
                HeadingNode(
                    id="wrong-node",
                    teaching_block_id="other-block",
                    display=HeadingDisplay(text="Light", level=3),
                ),
                section.nodes[1],
            )
        }
    )

    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=_plan("section-1", title="Light and energy"),
        expected_nodes=_shape(),
    )

    codes = {issue.issue_code for issue in issues}
    assert {"node_id_mismatch", "node_kind_mismatch", "node_owner_mismatch"} <= codes
    assert section.nodes[0].id == "wrong-node"


def test_placeholder_internal_metadata_and_heading_hierarchy_are_rejected() -> None:
    section = _section(
        text="TODO explain teaching_block_id b1",
    ).model_copy(
        update={
            "nodes": (
                HeadingNode(
                    id="node-1",
                    teaching_block_id="b1",
                    display=HeadingDisplay(text="TODO teaching_block_id", level=2),
                ),
                _section().nodes[1],
            )
        }
    )

    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=_plan("section-1", title="Light and energy"),
        expected_nodes=(
            ExpectedNodeShape(
                id="node-1",
                kind="heading",
                teaching_block_id="b1",
                semantic_role="subsection",
            ),
            *_shape()[1:],
        ),
    )

    codes = {issue.issue_code for issue in issues}
    assert "metadata_or_placeholder_leak" in codes
    assert "heading_hierarchy_invalid" in codes


def test_primitive_table_shape_is_reported() -> None:
    section = SharedSection(
        id="section-1",
        title="Light and energy",
        position=0,
        nodes=(
            TableNode(
                id="table-1",
                teaching_block_id="b1",
                display=TableDisplay(
                    headers=("Input", "Role"),
                    rows=(("Light",),),
                ),
            ),
        ),
    )
    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=_plan("section-1", title="Light and energy"),
        expected_nodes=(
            ExpectedNodeShape(
                id="table-1",
                kind="table",
                teaching_block_id="b1",
                semantic_role="comparison",
            ),
        ),
    )

    assert any(issue.issue_code == "table_shape_invalid" for issue in issues)


def test_boundary_reports_missing_bridge_and_entry_prerequisite() -> None:
    previous = _section(text="Plants grow in sunlight.")
    current = _section(
        section_id="section-2",
        title="Photosynthesis",
        text="Photosynthesis makes food.",
    ).model_copy(update={"position": 1})
    issues = validate_section_boundary(
        previous_section=previous,
        previous_plan=_plan("section-1", title="Light and energy"),
        next_section=current,
        next_plan=_plan(
            "section-2",
            title="Photosynthesis",
            bridge="connect sunlight energy to photosynthesis",
            entry=["learners know sunlight energy"],
        ),
    )

    codes = {issue.issue_code for issue in issues}
    assert {"boundary_bridge_missing", "boundary_prerequisite_gap"} <= codes
    assert all(issue.affected_section_id == "section-2" for issue in issues)


def test_boundary_reports_repeated_closing_terminology() -> None:
    previous = _section(text="Light energy supports photosynthesis and plant growth.")
    current = _section(
        section_id="section-2",
        title="Using light energy",
        text="Light energy supports photosynthesis and plant growth.",
    ).model_copy(update={"position": 1})
    issues = validate_section_boundary(
        previous_section=previous,
        previous_plan=_plan("section-1", title="Light and energy"),
        next_section=current,
        next_plan=_plan("section-2", title="Using light energy"),
    )

    assert any(issue.issue_code == "boundary_repetition" for issue in issues)


def test_final_qa_returns_ready_for_valid_document() -> None:
    section = _section()
    document = build_shared_lesson_document(
        {
            "id": "document-1",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [section.model_dump(mode="json")],
            "tasks": [
                {
                    "id": "task-1",
                    "teaching_plan_id": "plan-1",
                    "teaching_plan_revision": 1,
                    "teaching_plan_hash": "a" * 64,
                    "teaching_block_id": "b1",
                    "mode": "formative",
                    "action": "select-one",
                    "purpose": "Check understanding",
                    "prompt": "What does light provide?",
                    "difficulty": "guided",
                    "expected_evidence": "Light provides energy",
                    "response": {
                        "type": "single_choice",
                        "options": [
                            {"id": "light", "text": "Light"},
                            {"id": "sand", "text": "Sand"},
                        ],
                    },
                    "evaluation": {"type": "exact_match", "correct_option_id": "light"},
                }
            ],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )
    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(
            _plan(
                "section-1",
                title="Light and energy",
                must=["light energy"],
                exit_state=["explain light energy"],
            ),
        ),
        expected_shapes={"section-1": _shape()},
        expected_title="Light and energy",
    )

    assert result.ready
    require_ready_document(result)


def test_final_qa_blocks_required_media_and_ready_gate() -> None:
    section = _section(text="Light provides energy.")
    document = build_shared_lesson_document(
        {
            "id": "document-1",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [section.model_dump(mode="json")],
            "tasks": [
                {
                    "id": "task-1",
                    "teaching_plan_id": "plan-1",
                    "teaching_plan_revision": 1,
                    "teaching_plan_hash": "a" * 64,
                    "teaching_block_id": "b1",
                    "mode": "formative",
                    "action": "select-one",
                    "purpose": "Check understanding",
                    "prompt": "What does light provide?",
                    "difficulty": "guided",
                    "expected_evidence": "Light provides energy",
                    "response": {
                        "type": "single_choice",
                        "options": [
                            {"id": "light", "text": "Light"},
                            {"id": "sand", "text": "Sand"},
                        ],
                    },
                    "evaluation": {"type": "exact_match", "correct_option_id": "light"},
                }
            ],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )
    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(
            _plan("section-1", title="Light and energy", must=["light energy"]),
        ),
        expected_shapes={"section-1": _shape()},
        required_media_by_section={"section-1": ("figure-1",)},
    )

    assert any(issue.issue_code == "required_media_missing" for issue in result.issues)
    with pytest.raises(DocumentQAError):
        require_ready_document(result)


def test_final_qa_defers_narrative_coverage_and_ignores_natural_section_id() -> None:
    section = SharedSection(
        id="check",
        title="Light and energy",
        position=0,
        nodes=(
            ParagraphNode(
                id="node-check-1",
                teaching_block_id="b1",
                display=ParagraphDisplay(
                    text="This check is yours alone. A learner sorts a new case independently."
                ),
            ),
        ),
    )
    document = build_shared_lesson_document(
        {
            "id": "document-check",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [section.model_dump(mode="json")],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )

    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(
            _plan(
                "check",
                title="Light and energy",
                must=["Whether each learner working alone can classify an unseen decision"],
                bridge="Connect the previous example to a new decision",
                exit_state=["Learners explain why their classification is supported"],
            ),
        ),
        expected_shapes={
            "check": (
                ExpectedNodeShape(
                    id="node-check-1",
                    kind="paragraph",
                    teaching_block_id="b1",
                    semantic_role="explanation",
                ),
            )
        },
    )

    assert result.ready


def test_final_qa_defers_boundary_narrative_checks_to_boundary_evidence() -> None:
    previous = SharedSection(
        id="section-1",
        title="Light and energy",
        position=0,
        nodes=(
            ParagraphNode(
                id="node-prev",
                teaching_block_id="b1",
                display=ParagraphDisplay(text="Plants can grow in sunlight."),
            ),
        ),
    )
    current = SharedSection(
        id="section-2",
        title="Photosynthesis",
        position=1,
        nodes=(
            ParagraphNode(
                id="node-current",
                teaching_block_id="b1",
                display=ParagraphDisplay(text="Food is made through photosynthesis."),
            ),
        ),
    )
    document = build_shared_lesson_document(
        {
            "id": "document-boundary-check",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [previous.model_dump(mode="json"), current.model_dump(mode="json")],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )

    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(
            _plan(
                "section-1",
                title="Light and energy",
                exit_state=["Learners understand sunlight's role in plant growth"],
            ),
            _plan(
                "section-2",
                title="Photosynthesis",
                bridge="Connect sunlight's role to food production",
                entry=["Learners know plants use light"],
            ),
        ),
        expected_shapes={
            "section-1": (
                ExpectedNodeShape(
                    id="node-prev",
                    kind="paragraph",
                    teaching_block_id="b1",
                    semantic_role="explanation",
                ),
            ),
            "section-2": (
                ExpectedNodeShape(
                    id="node-current",
                    kind="paragraph",
                    teaching_block_id="b1",
                    semantic_role="explanation",
                ),
            ),
        },
    )

    assert result.ready


@pytest.mark.usefixtures("blocking_quality_gate")
def test_final_qa_retains_hard_metadata_and_source_failures() -> None:
    section = _section(text="TODO chlorophyll captures light energy.")
    document = build_shared_lesson_document(
        {
            "id": "document-hard-checks",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [section.model_dump(mode="json")],
            "tasks": [
                {
                    "id": "task-1",
                    "teaching_plan_id": "plan-1",
                    "teaching_plan_revision": 1,
                    "teaching_plan_hash": "a" * 64,
                    "teaching_block_id": "b1",
                    "mode": "formative",
                    "action": "select-one",
                    "purpose": "Check understanding",
                    "prompt": "What captures light energy?",
                    "difficulty": "guided",
                    "expected_evidence": "Chlorophyll captures light energy",
                    "response": {
                        "type": "single_choice",
                        "options": [
                            {"id": "chlorophyll", "text": "Chlorophyll"},
                            {"id": "water", "text": "Water"},
                        ],
                    },
                    "evaluation": {"type": "exact_match", "correct_option_id": "chlorophyll"},
                }
            ],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )

    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(
            _plan(
                "section-1",
                title="Light and energy",
                must=["Chlorophyll captures light energy"],
            ),
        ),
        expected_shapes={"section-1": _shape()},
        source_facts_by_section={"section-1": ("Sunlight provides energy to plants.",)},
    )

    assert {
        "metadata_or_placeholder_leak",
        "unsupported_required_fact",
    } <= {issue.issue_code for issue in result.issues}
    assert not result.ready


def test_final_qa_keeps_unknown_continuity_issues_blocking(monkeypatch) -> None:
    section = SharedSection(
        id="section-1",
        title="Light and energy",
        position=0,
        nodes=(
            ParagraphNode(
                id="node-1",
                teaching_block_id="b1",
                display=ParagraphDisplay(text="Light provides energy for photosynthesis."),
            ),
        ),
    )
    document = build_shared_lesson_document(
        {
            "id": "document-unknown-check",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Light and energy",
            "sections": [section.model_dump(mode="json")],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )

    def unknown_issue(**_kwargs):
        return (
            ContinuityIssue(
                issue_code="future_unknown_contract",
                affected_section_id="section-1",
                explanation="unknown continuity contract",
                required_correction="resolve the unknown contract",
            ),
        )

    monkeypatch.setattr(qa_module, "validate_section_continuity", unknown_issue)
    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=(_plan("section-1", title="Light and energy"),),
        expected_shapes={
            "section-1": (
                ExpectedNodeShape(
                    id="node-1",
                    kind="paragraph",
                    teaching_block_id="b1",
                    semantic_role="explanation",
                ),
            )
        },
    )

    assert [issue.issue_code for issue in result.issues] == ["future_unknown_contract"]
    assert not result.ready


class _RepairEngine:
    def __init__(self, repaired: SharedSection) -> None:
        self.repaired = repaired
        self.calls = 0

    async def repair_section(self, request: SectionRepairRequest) -> SharedSection:
        self.calls += 1
        assert request.section_id == request.section.id
        return self.repaired


@pytest.mark.asyncio
async def test_repair_is_one_targeted_call_and_preserves_section_identity() -> None:
    section = _section(text="TODO")
    request = SectionRepairRequest(
        section_id=section.id,
        section=section,
        issues=(
            ContinuityIssue(
                issue_code="metadata_or_placeholder_leak",
                affected_section_id=section.id,
                explanation="placeholder",
                required_correction="rewrite",
            ),
        ),
    )
    repaired = _section(text="Light provides energy for photosynthesis.")
    engine = _RepairEngine(repaired)
    result = await repair_affected_section_once(
        request=request,
        engine=engine,
        validate=lambda candidate: validate_section_continuity(
            section=candidate,
            teaching_plan_section=_plan(
                "section-1",
                title="Light and energy",
                must=["light energy"],
                exit_state=["explain light energy"],
            ),
            expected_nodes=_shape(),
        ),
    )

    assert result == repaired
    assert engine.calls == 1


@pytest.mark.asyncio
async def test_repair_failure_is_bounded_and_does_not_loop() -> None:
    section = _section(text="TODO")
    request = SectionRepairRequest(
        section_id=section.id,
        section=section,
        issues=(
            ContinuityIssue(
                issue_code="metadata_or_placeholder_leak",
                affected_section_id=section.id,
                explanation="placeholder",
                required_correction="rewrite",
            ),
        ),
    )
    engine = _RepairEngine(section)
    with pytest.raises(BoundedRepairExhausted) as raised:
        await repair_affected_section_once(
            request=request,
            engine=engine,
            validate=lambda candidate: (
                ContinuityIssue(
                    issue_code="metadata_or_placeholder_leak",
                    affected_section_id=candidate.id,
                    explanation="still present",
                    required_correction="rewrite",
                ),
            ),
        )

    assert engine.calls == 1
    assert raised.value.issues[0].issue_code == "metadata_or_placeholder_leak"


def _figure_section(*, asset_id: str | None, alt_text: str) -> SharedSection:
    from document.shared_lesson.models import FigureAccessibility, FigureDisplay, FigureNode

    section = _section()
    return section.model_copy(
        update={
            "nodes": (
                section.nodes[0],
                FigureNode(
                    id="figure-1",
                    teaching_block_id="b1",
                    display=FigureDisplay(asset_id=asset_id, caption="A light diagram"),
                    accessibility=FigureAccessibility(alt_text=alt_text),
                ),
                section.nodes[1],
            )
        }
    )


def _figure_shape() -> tuple[ExpectedNodeShape, ...]:
    shape = _shape()
    return (
        shape[0],
        ExpectedNodeShape(
            id="figure-1",
            kind="figure",
            teaching_block_id="b1",
            semantic_role="visual_model",
        ),
        shape[1],
    )


def test_pending_figure_with_empty_alt_is_not_an_issue_but_bound_figure_needs_alt() -> None:
    plan = _plan("section-1", title="Light and energy")

    pending = validate_section_continuity(
        section=_figure_section(asset_id=None, alt_text=""),
        teaching_plan_section=plan,
        expected_nodes=_figure_shape(),
    )
    assert "figure_alt_text_missing" not in {issue.issue_code for issue in pending}

    bound = validate_section_continuity(
        section=_figure_section(asset_id="asset-1", alt_text=""),
        teaching_plan_section=plan,
        expected_nodes=_figure_shape(),
    )
    assert "figure_alt_text_missing" in {issue.issue_code for issue in bound}

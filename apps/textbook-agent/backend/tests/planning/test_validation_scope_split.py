"""Section-local vs lesson-wide validator split is behaviour-preserving."""

from __future__ import annotations

import copy

from application.unit_lesson import teaching_planner as tp
from curriculum.teaching_plan.models import VisualSpec
from print.generation.whole_lesson.validation import (
    LESSON_WIDE_ISSUE_CODES,
    SECTION_LOCAL_ISSUE_CODES,
    TeachingValidationContext,
    validate_teaching_plan,
    validate_teaching_plan_lesson,
    validate_teaching_plan_structure,
    validate_teaching_section,
)
from tests.planning.test_backbone_figure_link import _packet, _plan

KW = dict(
    permitted_intents={"orient", "check-understanding"},
    excluded_intents=set(),
    typical_by_slot={"orient": {"orient"}, "check": {"check-understanding"}},
    assessment_intents={"check-understanding"},
)


def _tuples(issues):
    return [(i.code, i.message, i.path, i.blocking) for i in issues]


def _composed(plan, packet):
    ctx = TeachingValidationContext(packet)
    issues = list(validate_teaching_plan_structure(plan, packet))
    for section in plan.sections:
        issues += validate_teaching_section(section, packet, context=ctx, **KW)
    issues += validate_teaching_plan_lesson(plan, packet, ctx)
    return issues


def _plans():
    bad_visual = VisualSpec(
        figure_ref="fig-zzz", purpose="", must_show=[], labels_required=["nope"]
    )
    dup = _plan(["q1"])
    dup.sections[0].blocks[0].id = dup.sections[1].blocks[0].id
    shape = _plan(["q1"])
    shape.sections.reverse()
    return [
        (_plan(["q1"]), _packet()),
        (_plan(["q2"], bad_visual), _packet()),
        (dup, _packet()),
        (shape, _packet()),
    ]


def test_validate_teaching_plan_equals_composition() -> None:
    for plan, packet in _plans():
        combined = validate_teaching_plan(plan, packet, **KW)
        assert _tuples(combined.issues) == _tuples(_composed(plan, packet))
        assert combined.ok == (not any(i.blocking for i in combined.issues))


def test_section_validation_returns_section_issues() -> None:
    plan, packet = _plans()[0]
    issues = validate_teaching_section(plan.sections[1], packet, **KW)
    assert [i.code for i in issues] == ["FIGURE_REF_MISSING"]
    assert issues[0].path == "sections.check.blocks[0].visual"
    assert validate_teaching_section(plan.sections[0], packet, **KW) == []

    plan, packet = _plans()[1]
    issues = validate_teaching_section(plan.sections[1], packet, **KW)
    codes = [i.code for i in issues]
    assert "FIGURE_REF_UNKNOWN" in codes and "VISUAL_SPEC_INVALID" in codes
    assert {i.code for i in issues} <= SECTION_LOCAL_ISSUE_CODES
    combined = validate_teaching_plan(plan, packet, **KW)
    assert [i for i in combined.issues if i.path.startswith("sections.check")] == issues


def test_cross_section_duplicates_need_shared_context() -> None:
    plan, packet = _plans()[2]
    alone = validate_teaching_section(plan.sections[1], packet, **KW)
    assert "DUPLICATE_BLOCK_ID" not in [i.code for i in alone]
    ctx = TeachingValidationContext(packet)
    validate_teaching_section(plan.sections[0], packet, context=ctx, **KW)
    shared = validate_teaching_section(plan.sections[1], packet, context=ctx, **KW)
    assert "DUPLICATE_BLOCK_ID" in [i.code for i in shared]
    assert ctx.total_blocks == 2


def test_lesson_wide_codes_and_ordering() -> None:
    plan, packet = _plans()[3]
    structure = validate_teaching_plan_structure(plan, packet)
    assert "SLOT_ORDER" in {i.code for i in structure}
    assert {i.code for i in structure} <= LESSON_WIDE_ISSUE_CODES
    combined = validate_teaching_plan(plan, packet, **KW)
    assert [i.code for i in combined.issues][: len(structure)] == [i.code for i in structure]
    for plan, packet in _plans():
        ctx = TeachingValidationContext(packet)
        for s in plan.sections:
            validate_teaching_section(s, packet, context=ctx, **KW)
        lesson = validate_teaching_plan_lesson(plan, packet, ctx)
        assert {i.code for i in lesson} <= LESSON_WIDE_ISSUE_CODES
    assert SECTION_LOCAL_ISSUE_CODES & LESSON_WIDE_ISSUE_CODES == {"OBJECT_LEAK"}


def test_planner_section_helpers_match_plan_level() -> None:
    for plan, packet in _plans():
        pairs = [
            (tp._task_source_contract_errors(plan),
             lambda s: tp._task_source_contract_errors_for_section(s)),
            (tp._unknown_learner_action_errors(plan),
             lambda s: tp._unknown_learner_action_errors_for_section(s)),
            (tp._action_source_compatibility_errors(plan, packet),
             lambda s: tp._action_source_compatibility_errors_for_section(s, packet)),
            (tp._frozen_assessment_reuse_errors(plan, packet),
             lambda s: tp._frozen_assessment_reuse_errors_for_section(s, packet)),
            (tp._frozen_assessment_reuse_findings(plan, packet),
             lambda s: tp._frozen_assessment_reuse_findings_for_section(s, packet)),
        ]
        for whole, per in pairs:
            assert whole == [x for s in plan.sections for x in per(s)]


def test_planner_repair_section_variants_match_plan_level() -> None:
    packet = _packet()
    for sources in (["q1"], ["q1", "q2"], ["q2"], ["nope"]):
        whole, split = _plan(sources), _plan(sources)
        split = copy.deepcopy(split)
        tp._repair_briefs_missing_anchor_grounding(whole, packet)
        tp._repair_sources_outside_structural_slots(whole, packet)
        tp._repair_incompatible_assessment_sources(whole, packet)
        tp._repair_invalid_evidence_refs(whole, packet)
        changes = tp._repair_missing_figure_visuals(whole, packet)
        split_changes = []
        for s in split.sections:
            tp._repair_briefs_missing_anchor_grounding_for_section(s, packet)
            tp._repair_sources_outside_structural_slots_for_section(s, packet)
            tp._repair_incompatible_assessment_sources_for_section(s, packet)
            tp._repair_invalid_evidence_refs_for_section(s, packet)
            split_changes += tp._repair_missing_figure_visuals_for_section(s, packet)
        assert whole.model_dump() == split.model_dump()
        assert changes == split_changes

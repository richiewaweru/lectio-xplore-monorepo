"""Contract ownership tests: FormDecision, join, envelopes, WriterOutcome."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from generation.page_objects import WriterContext, WriterOutcome, dispatch_writer, validate_content
from generation.page_objects.document_assembly import assemble_section, assemble_document_v2
from planning.catalogue_projections import build_form_candidate_map, project_form_guidance
from planning.whole_lesson.form_plan import (
    FormDecision,
    FormPlan,
    FormPlanSection,
    coerce_form_plan,
)
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.legality import build_lesson_legality_snapshot
from planning.whole_lesson.prompt_render import build_form_planner_payload
from planning.whole_lesson.resolved_block_plan import resolve_block_plans
from planning.whole_lesson.teaching_plan import (
    AnchorUsage,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from planning.whole_lesson.validation import validate_form_plan
from tests.planning.contract_fixtures import teaching_and_form
from v3_blueprint.planning.models import PlannedBlock


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-contract",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="a1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause"]),
        ],
        limits=LessonLimits(),
        resource_id="lesson",
    )


def _compat() -> dict[str, list[str]]:
    return build_lesson_legality_snapshot(_packet()).compatible_objects_by_intent


def test_form_decision_rejects_teaching_owned_fields() -> None:
    with pytest.raises(ValidationError):
        FormDecision.model_validate(
            {
                "block_id": "b1",
                "object": "prose",
                "placement": "main",
                "reason": "ok",
                "intent": "explain",
            }
        )


def test_form_decision_requires_escalation_field_and_forbids_extra() -> None:
    decision = FormDecision(
        block_id="b1",
        object="list",
        placement="main",
        reason="brief has enumerated parts",
        escalation="prose would bury the sequence",
    )
    assert decision.escalation is not None
    with pytest.raises(ValidationError):
        FormDecision.model_validate(
            {
                "block_id": "b1",
                "object": "prose",
                "placement": "main",
                "reason": "ok",
                "escalation": None,
                "brief": "nope",
            }
        )


def test_coerce_legacy_fat_form_plan() -> None:
    legacy = {
        "sections": [
            {
                "slot_id": "orient",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Open",
                        "evidence": "anchor",
                        "object": "prose",
                        "placement": "spanning",
                        "reason": "legacy",
                    }
                ],
            }
        ]
    }
    plan = coerce_form_plan(legacy)
    decision = plan.sections[0].forms[0]
    assert decision.block_id == "orient-b1"
    assert decision.object == "prose"
    assert decision.placement == "main"
    assert not hasattr(decision, "intent") or "intent" not in decision.model_fields_set


def test_validate_form_plan_uses_shared_candidate_map() -> None:
    teaching, form = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    candidates = build_form_candidate_map(
        teaching, compatible_objects_by_intent=_compat()
    )
    report = validate_form_plan(form, teaching, candidate_map=candidates)
    assert report.ok

    bad = FormPlan(
        sections=[
            FormPlanSection(
                slot_id="orient",
                forms=[
                    FormDecision(
                        block_id="orient-b1",
                        object="heading",
                        placement="main",
                        reason="bad",
                    )
                ],
            )
        ]
    )
    report_bad = validate_form_plan(bad, teaching, candidate_map=candidates)
    assert not report_bad.ok
    codes = {issue.code for issue in report_bad.issues}
    assert "HEADING_OBJECT" in codes or "INCOMPATIBLE_OBJECT" in codes


def test_validate_form_plan_rejects_unknown_and_duplicate_blocks() -> None:
    teaching, _ = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    candidates = build_form_candidate_map(
        teaching, compatible_objects_by_intent=_compat()
    )
    unknown = FormPlan(
        sections=[
            FormPlanSection(
                slot_id="orient",
                forms=[
                    FormDecision(
                        block_id="missing",
                        object="prose",
                        placement="main",
                        reason="x",
                    )
                ],
            )
        ]
    )
    report = validate_form_plan(unknown, teaching, candidate_map=candidates)
    assert not report.ok
    assert any(issue.code in {"UNKNOWN_BLOCK", "BLOCK_SET"} for issue in report.issues)

    duplicate = FormPlan(
        sections=[
            FormPlanSection(
                slot_id="orient",
                forms=[
                    FormDecision(
                        block_id="orient-b1",
                        object="prose",
                        placement="main",
                        reason="a",
                    ),
                    FormDecision(
                        block_id="orient-b1",
                        object="list",
                        placement="main",
                        reason="b",
                    ),
                ],
            )
        ]
    )
    report_dup = validate_form_plan(duplicate, teaching, candidate_map=candidates)
    assert not report_dup.ok
    assert any(issue.code == "DUPLICATE_FORM_BLOCK" for issue in report_dup.issues)


def test_form_planner_input_envelope_has_required_context() -> None:
    teaching, _ = teaching_and_form(
        sections=[
            ("orient", [("orient-b1", "orient", "prose")]),
            ("explain", [("explain-b1", "explain-cause", "prose")]),
        ]
    )
    guidance = project_form_guidance().to_dict()
    candidates = build_form_candidate_map(
        teaching, compatible_objects_by_intent=_compat()
    )
    payload = build_form_planner_payload(
        _packet(), teaching, guidance, candidate_map=candidates
    )
    assert payload["arc"]
    block = payload["sections"][0]["blocks"][0]
    assert block["intent"]
    assert block["brief"]
    assert isinstance(block["legal_object_candidates"], list)
    assert block["legal_object_candidates"]


def test_resolve_block_plans_joins_ownership() -> None:
    teaching, form = teaching_and_form(
        sections=[
            ("explain", [("explain-b1", "explain-cause", "table")]),
        ]
    )
    # Override brief on teaching to prove join source.
    teaching.sections[0].blocks[0].brief = "Teaching brief owns this"
    form.sections[0].forms[0].reason = "table earns comparison"
    resolved = resolve_block_plans(teaching, form)
    block = resolved.sections[0].blocks[0]
    assert block.brief == "Teaching brief owns this"
    assert block.intent == "explain-cause"
    assert block.object == "table"
    assert block.placement == "main"
    assert block.reason == "table earns comparison"


def test_writer_outcome_has_no_authoritative_object_intent() -> None:
    outcome = WriterOutcome(block_id="b1", content={"paragraphs": ["hi"]})
    assert outcome.block_id == "b1"
    assert not hasattr(outcome, "object")
    assert not hasattr(outcome, "intent")


def test_writer_input_envelope_requires_brief_and_object_contract() -> None:
    planned = PlannedBlock(
        id="b1",
        position=0,
        intent="explain-cause",
        object="prose",
        evidence="cause",
        brief="Light is the differing condition.",
    )
    assert planned.brief
    assert planned.object
    ctx = WriterContext(planned=planned)
    result = dispatch_writer(ctx)
    assert result.block_id == "b1"
    validate_content(planned.object, result.content)


def test_writer_rejects_wrong_content_type() -> None:
    with pytest.raises(Exception):
        validate_content("prose", {"items": [{"text": "nope"}]})


def test_e2e_join_assemble_persist_shape() -> None:
    teaching, form = teaching_and_form(
        sections=[
            ("orient", [("orient-b1", "orient", "prose")]),
            ("explain", [("explain-b1", "explain-cause", "list")]),
        ]
    )
    resolved = resolve_block_plans(teaching, form)
    section_plans = resolved.to_section_block_plans()
    sections = []
    outcomes: list[WriterOutcome] = []
    for section in resolved.sections:
        writer_results = []
        for block in section.blocks:
            ctx = WriterContext(planned=block.to_planned_block())
            result = dispatch_writer(ctx)
            writer_results.append(result)
            outcomes.append(result)
        sections.append(
            assemble_section(
                section_id=section.slot_id,
                title=section.specific_purpose or section.slot_id,
                plan=section_plans[section.slot_id],
                writer_results=writer_results,
            )
        )
    document = assemble_document_v2(
        title="Contract e2e",
        sections=sections,
        writer_results=outcomes,
    )
    assert document["document_version"] == 2
    assert len(document["sections"]) == 2
    first = document["sections"][0]["blocks"][0]
    assert first["object"] == "prose"
    assert first["intent"] == "orient"
    assert first["content"]
    # Form plan never carried teaching fields.
    dumped = form.model_dump(mode="json")
    assert "intent" not in dumped["sections"][0]["forms"][0]
    assert "brief" not in dumped["sections"][0]["forms"][0]

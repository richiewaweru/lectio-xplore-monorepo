from __future__ import annotations

import pytest
from tests.planning.legality_fixtures import make_snapshot as _make_snapshot
from tests.planning.legality_fixtures import packet as _packet

from core.llm import ModelSlot
from core.prompts.loader import closeout_prompt_hashes, get_manifest_entry
from curriculum.teaching_plan import semantic_review
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlanDraftV2,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticFinding,
    TeachingPlanSemanticReviewDraft,
    TeachingPlanSemanticReviewError,
    TeachingPlanSemanticReviewResult,
)
from infra.authoring.model_policy import (
    TEACHING_PLAN_SEMANTIC_REVIEWER,
    get_v3_slot,
)


@pytest.fixture(autouse=True)
def _blocking_quality_gate(monkeypatch):
    """These tests pin the strict (blocking) gate; advisory is covered in
    test_teaching_plan_quality_gate.py."""
    from core.config import settings

    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")


def _draft(*, task: bool = False) -> TeachingPlanDraftV2:
    block = {
        "intent": "explain-cause",
        "brief": (
            "Compare the lit and covered plants in anchor a1 to identify light as "
            "the condition that enables food production in each leaf."
        ),
        "evidence_refs": ["lesson.objective", "anchor.a1"],
        "evidence": (
            "The objective requires a causal account, so isolating light connects "
            "the observed difference to food production."
        ),
    }
    if task:
        block.update(
            {
                "task_mode": "formative",
                "learner_action": {
                    "action": "select-one",
                    "target": "which plant can make food",
                    "purpose": "Check the learner's causal understanding",
                    "expected_evidence": "The learner identifies light as necessary",
                    "difficulty": "guided",
                },
            }
        )
    return TeachingPlanDraftV2.model_validate(
        {
            "contract_version": 2,
            "learner_title": "Why plants need light",
            "arc": "Notice the plant difference, then explain how light enables food production.",
            "starting_state": ["Learners know plants grow."],
            "target_state": ["Learners can explain why plants need light to make food."],
            "anchor_usage": [
                {"slot_id": "orient", "usage": "Introduce the plant contrast."},
                {"slot_id": "explain", "usage": "Use the contrast to identify light's role."},
            ],
            "misconception_focus_ids": [],
            "sections": [
                {
                    "display_title": "Notice what differs",
                    "specific_purpose": "Make the changed condition visible.",
                    "entry_state": ["Learners know plants grow."],
                    "must_establish": ["The plants receive different amounts of light."],
                    "avoid_repeating": [],
                    "bridge_from_previous": None,
                    "exit_state": ["Learners notice that light differs."],
                    "transition": None,
                    "blocks": [
                        {
                            "intent": "orient",
                            "brief": (
                                "Use anchor a1's two plants grown under different light "
                                "conditions so learners notice the growth difference before "
                                "learning its cause."
                            ),
                            "evidence_refs": ["lesson.objective", "anchor.a1"],
                            "evidence": (
                                "The objective asks why light matters, so the contrast "
                                "makes the changed condition visible first."
                            ),
                        }
                    ],
                },
                {
                    "display_title": "Explain the role of light",
                    "specific_purpose": "Connect the observed difference to its cause.",
                    "entry_state": ["Learners notice that light differs."],
                    "must_establish": ["Light enables plants to make food."],
                    "avoid_repeating": [],
                    "bridge_from_previous": "The observed contrast raises a question about light.",
                    "exit_state": ["Learners can explain why light enables food production."],
                    "transition": "Use the plant contrast to explain the causal role of light.",
                    "blocks": [block],
                },
            ],
        }
    )


def _finding(code: str, section_ids: list[str], block_ids: list[str] | None = None):
    return TeachingPlanSemanticFinding(
        code=code,
        section_ids=section_ids,
        block_ids=block_ids or [],
        message=f"Concrete {code} defect in the draft.",
        repair_instruction=f"Repair the {code} defect without changing slot ownership.",
    )


def test_semantic_reviewer_uses_registered_standard_model_and_locked_prompt() -> None:
    assert get_v3_slot(TEACHING_PLAN_SEMANTIC_REVIEWER) is ModelSlot.STANDARD
    prompt = get_manifest_entry("teaching-plan-semantic-reviewer")
    assert prompt.editable is False
    assert "teaching-plan-semantic-reviewer" in closeout_prompt_hashes()


def test_semantic_reviewer_prompt_carves_out_backbone_for_item_reuse() -> None:
    from core.prompts import effective_prompt_text

    prompt = " ".join(effective_prompt_text("teaching-plan-semantic-reviewer").split())
    assert "item_backbone_refs" in prompt
    assert "lesson_context.backbone" in prompt
    assert "sharing the anchor scenario or its data is NOT reuse" in prompt


def test_semantic_reviewer_runs_with_deepseek_thinking_enabled() -> None:
    from infra.authoring.model_policy import V3_NODE_REASONING

    assert V3_NODE_REASONING[TEACHING_PLAN_SEMANTIC_REVIEWER] == "medium"


@pytest.mark.asyncio
async def test_reviewer_rejects_unbound_section_finding(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    unbound = TeachingPlanSemanticReviewDraft(
        reviewed=True,
        findings=[_finding("target_coverage_gap", ["section-that-does-not-exist"])],
    )

    async def _fake_structured(**_kwargs):
        return unbound

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await semantic_review.review_teaching_plan_draft(
            draft=draft,
            plan=plan,
            lesson_context={},
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"


@pytest.mark.asyncio
async def test_reviewer_rejects_new_codes_with_wrong_binding_shape(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])

    async def _fake_structured(**_kwargs):
        return TeachingPlanSemanticReviewDraft(
            reviewed=True,
            findings=[
                _finding("assessment_item_reused", ["orient", "explain"], []),
            ],
        )

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await semantic_review.review_teaching_plan_draft(
            draft=draft,
            plan=plan,
            lesson_context={},
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"


@pytest.mark.asyncio
async def test_reviewer_rejects_factual_inaccuracy_with_two_sections(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])

    async def _fake_structured(**_kwargs):
        return TeachingPlanSemanticReviewDraft(
            reviewed=True,
            findings=[
                _finding("factual_inaccuracy", ["orient", "explain"], []),
            ],
        )

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await semantic_review.review_teaching_plan_draft(
            draft=draft,
            plan=plan,
            lesson_context={},
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"


@pytest.mark.asyncio
async def test_reviewer_uses_existing_structured_run_and_exact_identity_map(monkeypatch) -> None:
    draft = _draft(task=True)
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    captured = {}

    async def _fake_structured(**kwargs):
        captured.update(kwargs)
        return TeachingPlanSemanticReviewDraft(reviewed=True, findings=[])

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    result = await semantic_review.review_teaching_plan_draft(
        draft=draft,
        plan=plan,
        lesson_context={"objective": "Explain why plants need light."},
    )

    assert captured["node"] == TEACHING_PLAN_SEMANTIC_REVIEWER
    assert captured["caller"] == "teaching_plan_semantic_reviewer"
    assert captured["output_type"] is TeachingPlanSemanticReviewDraft
    assert captured["user_payload"]["section_block_identity_map"] == [
        {"section_id": "orient", "block_ids": ["orient-b1"]},
        {"section_id": "explain", "block_ids": ["explain-b1"]},
    ]
    assert captured["user_payload"]["materialized_candidate"]["contract_version"] == 2
    assert result.clean is True
    assert result.content_hash == teaching_plan_content_hash(plan)


@pytest.mark.asyncio
async def test_reviewer_provider_failure_is_terminal_and_never_returns_plan(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])

    async def _failed_structured(**_kwargs):
        raise PermissionError("reviewer credential unavailable")

    monkeypatch.setattr(semantic_review, "_run_structured", _failed_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await semantic_review.review_teaching_plan_draft(
            draft=draft,
            plan=plan,
            lesson_context={},
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_FAILED"


@pytest.mark.asyncio
async def test_invalid_reviewer_code_is_not_treated_as_clean(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])

    async def _fake_structured(**_kwargs):
        return {
            "reviewed": True,
            "findings": [
                {
                    "code": "probably-fine",
                    "section_ids": ["explain"],
                    "block_ids": [],
                    "message": "Unexpected code",
                    "repair_instruction": "Ignore.",
                }
            ],
        }

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await semantic_review.review_teaching_plan_draft(
            draft=draft,
            plan=plan,
            lesson_context={},
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"


def test_frozen_assessment_reuse_flags_verbatim_stem_leak() -> None:
    from print.generation.whole_lesson.packet import ApprovedItemRef
    from application.unit_lesson.teaching_planner import _frozen_assessment_reuse_errors

    packet = _packet().model_copy(
        update={
            "approved_items": [
                ApprovedItemRef(id="mcq-1", card_id="card", stem="Solve for x: 7x = 56", options=[])
            ]
        }
    )
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    plan.sections[1].blocks[0].brief = (
        "Work through the model: Solve for x: 7x = 56, showing each step."
    )

    errors = _frozen_assessment_reuse_errors(plan, packet)

    assert len(errors) == 1
    assert "TEACHING_FROZEN_ITEM_REUSED" in errors[0]
    assert "mcq-1" in errors[0]


def test_frozen_assessment_reuse_allows_different_values() -> None:
    from print.generation.whole_lesson.packet import ApprovedItemRef
    from application.unit_lesson.teaching_planner import _frozen_assessment_reuse_errors

    packet = _packet().model_copy(
        update={
            "approved_items": [
                ApprovedItemRef(id="mcq-1", card_id="card", stem="Solve for x: 7x = 56", options=[])
            ]
        }
    )
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    plan.sections[1].blocks[0].brief = (
        "Work through the model: solve for x: 3x = 12, showing each step."
    )

    errors = _frozen_assessment_reuse_errors(plan, packet)

    assert errors == []


def test_frozen_assessment_reuse_ignores_the_owning_assessment_block() -> None:
    from print.generation.whole_lesson.packet import ApprovedItemRef
    from application.unit_lesson.teaching_planner import _frozen_assessment_reuse_errors

    packet = _packet().model_copy(
        update={
            "approved_items": [
                ApprovedItemRef(id="mcq-1", card_id="card", stem="Solve for x: 7x = 56", options=[])
            ]
        }
    )
    draft = _draft(task=True)
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    plan.sections[1].blocks[0].brief = "Solve for x: 7x = 56"
    plan.sections[1].blocks[0].task_mode = "assessment"
    plan.sections[1].blocks[0].source_question_ids = ["mcq-1"]

    errors = _frozen_assessment_reuse_errors(plan, packet)

    assert errors == []


@pytest.mark.asyncio
async def test_reviewer_reasks_once_after_unbound_finding(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    unbound = TeachingPlanSemanticReviewDraft(
        reviewed=True,
        findings=[_finding("target_coverage_gap", ["section-that-does-not-exist"])],
    )
    clean = TeachingPlanSemanticReviewDraft(reviewed=True, findings=[])
    payloads: list[dict] = []

    async def _fake_structured(**kwargs):
        payloads.append(kwargs["user_payload"])
        return unbound if len(payloads) == 1 else clean

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    result = await semantic_review.review_teaching_plan_draft(
        draft=draft,
        plan=plan,
        lesson_context={},
    )
    assert result.findings == []
    assert len(payloads) == 2
    assert "previous_attempt_binding_error" not in payloads[0]
    assert "previous_attempt_binding_error" in payloads[1]


@pytest.mark.asyncio
async def test_visual_missing_finding_is_lesson_level_and_rejects_block_binding(
    monkeypatch,
) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    findings_by_call = [
        [_finding("visual_missing_for_figure_objective", ["explain"], [])],
        [_finding("visual_missing_for_figure_objective", ["explain"], ["explain-b1"])],
    ]

    async def _fake_structured(**_kwargs):
        return TeachingPlanSemanticReviewDraft(reviewed=True, findings=findings_by_call.pop(0))

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)
    result = await semantic_review.review_teaching_plan_draft(
        draft=draft, plan=plan, lesson_context={}
    )
    assert [finding.code for finding in result.findings] == [
        "visual_missing_for_figure_objective"
    ]
    assert "visual_missing_for_figure_objective" in semantic_review.ADVISORY_ONLY_SEMANTIC_CODES

    with pytest.raises(TeachingPlanSemanticReviewError):
        await semantic_review.review_teaching_plan_draft(
            draft=draft, plan=plan, lesson_context={}
        )

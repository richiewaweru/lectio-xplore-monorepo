"""Section and whole-lesson reviews reuse the semantic reviewer by import."""

from __future__ import annotations

import pytest
from tests.planning.test_teaching_plan_semantic_review import _draft, _finding

from curriculum.prompts import teaching_plan_semantic_reviewer_prompt
from curriculum.teaching_plan import semantic_review, staged_review
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlanDraftV2, materialize_teaching_plan
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticReviewDraft,
    TeachingPlanSemanticReviewError,
)
from curriculum.teaching_plan.staged import TeachingSpine
from curriculum.teaching_plan.staged_review import (
    LESSON_REVIEW_CODES,
    SECTION_REVIEW_CODES,
    review_teaching_lesson,
    review_teaching_section,
)

SLOTS = ["orient", "explain"]


def _spine() -> TeachingSpine:
    d = _draft()
    return TeachingSpine.model_validate(
        {
            "learner_title": d.learner_title,
            "arc": d.arc,
            "starting_state": d.starting_state,
            "target_state": d.target_state,
            "sections": [
                {
                    "slot_id": slot,
                    "display_title": s.display_title,
                    "entry_state": s.entry_state,
                    "must_establish": s.must_establish,
                    "avoid_repeating": s.avoid_repeating,
                    "bridge_from_previous": s.bridge_from_previous,
                    "exit_state": s.exit_state,
                    "planned_block_count": len(s.blocks),
                }
                for slot, s in zip(SLOTS, d.sections, strict=True)
            ],
        }
    )


def _section_inputs():
    d = _draft(task=True)
    data = d.model_dump(mode="json")
    data["sections"] = data["sections"][1:]
    data["anchor_usage"] = data["anchor_usage"][1:]
    data["sections"][0]["bridge_from_previous"] = None
    sd = TeachingPlanDraftV2.model_validate(data)
    return sd, materialize_teaching_plan(sd, slot_ids=["explain"])


def _fake(monkeypatch, reviews):
    calls = []

    async def _run(**kwargs):
        calls.append(kwargs)
        return reviews.pop(0)

    monkeypatch.setattr(semantic_review, "_run_structured", _run)
    return calls


def _review(*findings):
    return TeachingPlanSemanticReviewDraft(reviewed=True, findings=list(findings))


@pytest.mark.asyncio
async def test_section_review_prompt_payload_caller_and_scope_filter(monkeypatch) -> None:
    sd, sp = _section_inputs()
    block_id = sp.sections[0].blocks[0].id
    calls = _fake(
        monkeypatch,
        [
            _review(
                _finding("task_evidence_gap", ["explain"], [block_id]),
                _finding("progression_gap", ["explain"]),
                _finding("visual_missing_for_figure_objective", ["explain"]),
            )
        ],
    )
    findings = await review_teaching_section(
        spine=_spine(), slot_id="explain", section_plan=sp, section_draft=sd, lesson_context={}
    )
    assert [f.code for f in findings] == ["task_evidence_gap"]
    call = calls[0]
    assert call["caller"] == "teaching_section_reviewer"
    base = teaching_plan_semantic_reviewer_prompt()
    assert call["system_prompt"].startswith(base)
    assert "## REVIEW SCOPE" in call["system_prompt"][len(base):]
    payload = call["user_payload"]
    assert payload["teaching_spine"] == _spine().model_dump(mode="json")
    assert payload["review_scope"] == {
        "kind": "section",
        "slot_id": "explain",
        "allowed_codes": sorted(SECTION_REVIEW_CODES),
    }
    assert payload["section_block_identity_map"] == [
        {"section_id": "explain", "block_ids": [block_id]}
    ]


@pytest.mark.asyncio
async def test_section_review_binding_reask_still_works(monkeypatch) -> None:
    sd, sp = _section_inputs()
    block_id = sp.sections[0].blocks[0].id
    calls = _fake(
        monkeypatch,
        [
            _review(_finding("task_evidence_gap", ["orient"], ["x"])),
            _review(_finding("task_evidence_gap", ["explain"], [block_id])),
        ],
    )
    findings = await review_teaching_section(
        spine=_spine(), slot_id="explain", section_plan=sp, section_draft=sd, lesson_context={}
    )
    assert len(findings) == 1 and len(calls) == 2
    assert "previous_attempt_binding_error" in calls[1]["user_payload"]
    assert "previous_attempt_binding_error" not in calls[0]["user_payload"]


@pytest.mark.asyncio
async def test_section_review_persistent_binding_error_and_wrong_slot(monkeypatch) -> None:
    sd, sp = _section_inputs()
    bad = _review(_finding("task_evidence_gap", ["orient"], ["x"]))
    _fake(monkeypatch, [bad, bad])
    with pytest.raises(TeachingPlanSemanticReviewError) as exc:
        await review_teaching_section(
            spine=_spine(), slot_id="explain", section_plan=sp, section_draft=sd, lesson_context={}
        )
    assert exc.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"
    with pytest.raises(TeachingPlanSemanticReviewError):
        await review_teaching_section(
            spine=_spine(), slot_id="orient", section_plan=sp, section_draft=sd, lesson_context={}
        )


@pytest.mark.asyncio
async def test_lesson_review_binds_hash_drops_section_codes(monkeypatch) -> None:
    draft = _draft(task=True)
    plan = materialize_teaching_plan(draft, slot_ids=SLOTS)
    block_id = plan.sections[1].blocks[0].id
    calls = _fake(
        monkeypatch,
        [
            _review(
                _finding("adjacent_exit_entry", SLOTS),
                _finding("task_evidence_gap", ["explain"], [block_id]),
                _finding("factual_inaccuracy", ["explain"]),
            )
        ],
    )
    result = await review_teaching_lesson(
        spine=_spine(), plan=plan, draft=draft, lesson_context={}
    )
    assert result.content_hash == teaching_plan_content_hash(plan)
    assert [f.code for f in result.findings] == ["adjacent_exit_entry"]
    call = calls[0]
    assert call["caller"] == "teaching_lesson_reviewer"
    assert call["system_prompt"].startswith(teaching_plan_semantic_reviewer_prompt())
    assert call["system_prompt"].endswith(staged_review.LESSON_REVIEW_SCOPE)
    assert call["user_payload"]["review_scope"] == {
        "kind": "lesson",
        "allowed_codes": sorted(LESSON_REVIEW_CODES),
    }
    assert "teaching_spine" in call["user_payload"]


def test_code_sets_are_disjoint_and_cover_all_codes() -> None:
    from typing import get_args

    assert not SECTION_REVIEW_CODES & LESSON_REVIEW_CODES
    assert SECTION_REVIEW_CODES | LESSON_REVIEW_CODES == set(
        get_args(semantic_review.SemanticFindingCode)
    )

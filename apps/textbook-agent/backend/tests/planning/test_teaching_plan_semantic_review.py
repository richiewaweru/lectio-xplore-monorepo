from __future__ import annotations

from unittest.mock import patch

import pytest
from tests.planning.test_contract_hardening import _make_snapshot, _packet

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
from print.generation.whole_lesson import teaching_agent
from print.generation.whole_lesson.teaching_agent import run_lesson_approach_planner
from print.generation.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError


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


async def _run_with_reviewer(monkeypatch, *, reviews, task: bool = False):
    packet = _packet()
    legality = _make_snapshot()
    draft = _draft(task=task)
    planner_calls = []
    reviewer_calls = []

    async def _planner_call(**kwargs):
        planner_calls.append(kwargs)
        return draft, draft.model_dump_json()

    async def _review(**kwargs):
        reviewer_calls.append(kwargs)
        response = reviews.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(teaching_agent, "_call_teaching_model", _planner_call)
    monkeypatch.setattr(teaching_agent, "review_teaching_plan_draft", _review)
    result = await run_lesson_approach_planner(packet, legality=legality, require_items=False)
    return result, planner_calls, reviewer_calls


@pytest.mark.asyncio
async def test_semantic_reviewer_clean_pass_binds_exact_plan_hash(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    clean = TeachingPlanSemanticReviewResult(
        content_hash=teaching_plan_content_hash(plan), findings=[]
    )
    result, planner_calls, reviewer_calls = await _run_with_reviewer(monkeypatch, reviews=[clean])

    assert len(planner_calls) == len(reviewer_calls) == 1
    assert result.semantic_review.clean is True
    assert result.semantic_review.content_hash == teaching_plan_content_hash(result.plan)
    assert any(
        item.get("code") == "TEACHING_PLAN_SEMANTIC_REVIEW_PASS"
        and item.get("content_hash") == result.semantic_review.content_hash
        for item in result.qc
    )


@pytest.mark.parametrize(
    ("code", "section_ids", "block_ids", "task"),
    [
        ("progression_gap", ["orient", "explain"], [], False),
        ("adjacent_exit_entry", ["orient", "explain"], [], False),
        ("target_coverage_gap", ["explain"], [], False),
        ("duplicate_section_responsibility", ["orient", "explain"], [], False),
        ("task_evidence_gap", ["explain"], ["explain-b1"], True),
    ],
)
@pytest.mark.asyncio
async def test_blocking_semantic_finding_repairs_once_then_accepts_clean_v2(
    monkeypatch, code, section_ids, block_ids, task
) -> None:
    finding = _finding(code, section_ids, block_ids)
    candidate_hash = teaching_plan_content_hash(
        materialize_teaching_plan(_draft(task=task), slot_ids=["orient", "explain"])
    )
    clean = TeachingPlanSemanticReviewResult(
        content_hash=candidate_hash,
        findings=[],
    )
    result, planner_calls, reviewer_calls = await _run_with_reviewer(
        monkeypatch,
        reviews=[
            TeachingPlanSemanticReviewResult(
                content_hash=candidate_hash,
                findings=[finding],
            ),
            clean,
        ],
        task=task,
    )

    assert len(planner_calls) == len(reviewer_calls) == 2
    assert result.plan.contract_version == 2
    assert result.semantic_review.clean is True
    assert code.upper() in str(planner_calls[1]["user_payload"]["repair"]["validation_errors"])


@pytest.mark.asyncio
async def test_semantic_findings_after_second_candidate_reject_plan(monkeypatch) -> None:
    finding = _finding("target_coverage_gap", ["explain"])
    candidate_hash = teaching_plan_content_hash(
        materialize_teaching_plan(_draft(), slot_ids=["orient", "explain"])
    )
    repeated = TeachingPlanSemanticReviewResult(
        content_hash=candidate_hash,
        findings=[finding],
    )
    packet = _packet()
    draft = _draft()
    planner_calls = 0
    reviewer_calls = 0

    async def _planner_call(**_kwargs):
        nonlocal planner_calls
        planner_calls += 1
        return draft, draft.model_dump_json()

    async def _review(**_kwargs):
        nonlocal reviewer_calls
        reviewer_calls += 1
        return repeated

    with (
        patch.object(teaching_agent, "_call_teaching_model", new=_planner_call),
        patch.object(teaching_agent, "review_teaching_plan_draft", new=_review),
        pytest.raises(TeachingPlanOutputInvalidError, match="SEMANTIC_TARGET_COVERAGE_GAP"),
    ):
        await run_lesson_approach_planner(
            packet, legality=_make_snapshot(), require_items=False
        )
    assert planner_calls == reviewer_calls == 2


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
async def test_planner_stops_after_reviewer_provider_failure(monkeypatch) -> None:
    draft = _draft()
    planner_calls = 0

    async def _planner_call(**_kwargs):
        nonlocal planner_calls
        planner_calls += 1
        return draft, draft.model_dump_json()

    async def _failed_structured(**_kwargs):
        raise PermissionError("reviewer credential unavailable")

    monkeypatch.setattr(teaching_agent, "_call_teaching_model", _planner_call)
    monkeypatch.setattr(semantic_review, "_run_structured", _failed_structured)
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await run_lesson_approach_planner(
            _packet(), legality=_make_snapshot(), require_items=False
        )
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_FAILED"
    assert planner_calls == 1


@pytest.mark.asyncio
async def test_planner_rejects_review_hash_mismatch(monkeypatch) -> None:
    candidate_hash = teaching_plan_content_hash(
        materialize_teaching_plan(_draft(), slot_ids=["orient", "explain"])
    )
    mismatched = TeachingPlanSemanticReviewResult(
        content_hash=("0" * 64 if candidate_hash != "0" * 64 else "1" * 64),
        findings=[],
    )
    with pytest.raises(TeachingPlanSemanticReviewError) as raised:
        await _run_with_reviewer(monkeypatch, reviews=[mismatched])
    assert raised.value.code == "TEACHING_SEMANTIC_REVIEW_INVALID"


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

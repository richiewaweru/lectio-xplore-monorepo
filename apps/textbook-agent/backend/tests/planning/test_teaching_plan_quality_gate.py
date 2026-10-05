"""Advisory vs blocking Teaching Plan quality gate (providers are stubbed)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.planning.legality_fixtures import make_snapshot as _make_snapshot
from tests.planning.legality_fixtures import packet as _packet
from tests.planning.test_teaching_plan_semantic_review import _draft, _finding

from application.unit_lesson import teaching_planner as teaching_agent
from application.unit_lesson.teaching_planner import run_lesson_approach_planner
from core.config import settings
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import materialize_teaching_plan
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticReviewError,
    TeachingPlanSemanticReviewResult,
)
from print.generation.whole_lesson import validation as validation_module
from print.generation.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError
from print.generation.whole_lesson.validation import (
    ADVISORY_PLAN_ISSUE_CODES,
    HARD_PLAN_ISSUE_CODES,
    ValidationIssue,
    is_hard_plan_issue,
)


def _candidate_hash() -> str:
    return teaching_plan_content_hash(
        materialize_teaching_plan(_draft(), slot_ids=["orient", "explain"])
    )


def _install(monkeypatch, *, reviews, extra_issues=None):
    """Stub the planner + reviewer; optionally inject validator issues per attempt."""
    draft = _draft()
    planner_calls: list[dict] = []
    reviewer_calls: list[dict] = []

    async def _planner_call(**kwargs):
        planner_calls.append(kwargs)
        return draft, draft.model_dump_json()

    async def _review(**kwargs):
        reviewer_calls.append(kwargs)
        response = reviews.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    real_validate = teaching_agent.validate_teaching_plan

    def _validate(*args, **kwargs):
        report = real_validate(*args, **kwargs)
        for issue in (extra_issues or {}).get(len(planner_calls), []):
            report.issues.append(issue)
            report.ok = report.ok and not issue.blocking
        return report

    monkeypatch.setattr(teaching_agent, "_call_teaching_model", _planner_call)
    monkeypatch.setattr(teaching_agent, "review_teaching_plan_draft", _review)
    monkeypatch.setattr(teaching_agent, "validate_teaching_plan", _validate)
    return planner_calls, reviewer_calls


@pytest.fixture
def advisory_gate(monkeypatch):
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "advisory")


@pytest.fixture
def blocking_gate(monkeypatch):
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")


def test_setting_defaults_to_advisory() -> None:
    from infra.config import Settings

    assert Settings.model_fields["teaching_plan_quality_gate"].default == "advisory"


def test_every_validator_code_is_explicitly_classified() -> None:
    assert not (HARD_PLAN_ISSUE_CODES & ADVISORY_PLAN_ISSUE_CODES)
    source = Path(validation_module.__file__).read_text(encoding="utf-8")
    emitted = set(re.findall(r'code="([A-Z_]+)"', source))
    emitted.add("ACTION_SOURCE_INCOMPATIBLE")  # ActionSourceIncompatibleError.code
    unclassified = emitted - HARD_PLAN_ISSUE_CODES - ADVISORY_PLAN_ISSUE_CODES
    assert not unclassified, f"classify these validator codes: {sorted(unclassified)}"


def test_classification_keeps_contract_rules_hard_and_unknown_codes_closed() -> None:
    for code in ("UNKNOWN_ITEM", "DUPLICATE_ITEM_SOURCE", "DUPLICATE_BLOCK_ID", "TASK_MODE_REQUIRED",
                 "SLOT_ORDER", "EMPTY_SECTION", "EVIDENCE_REF", "ASSESSMENT_SOURCE_INTENT"):
        assert is_hard_plan_issue(code)
    for code in ("SECTION_BLOCK_LIMIT", "LESSON_BLOCK_LIMIT", "BRIEF_GENERIC", "OBJECT_LEAK",
                 "MUST_ESTABLISH_UNCOVERED", "INTENT_LEGALITY"):
        assert not is_hard_plan_issue(code)
    assert is_hard_plan_issue("SOME_FUTURE_RULE")


@pytest.mark.asyncio
async def test_advisory_findings_flag_and_pass_on_first_attempt(monkeypatch, advisory_gate) -> None:
    reviewed = TeachingPlanSemanticReviewResult(
        content_hash=_candidate_hash(),
        findings=[
            _finding("assessment_item_reused", ["explain"], ["explain-b1"]),
            _finding("target_coverage_gap", ["explain"]),
        ],
    )
    planner_calls, reviewer_calls = _install(
        monkeypatch,
        reviews=[reviewed],
        extra_issues={
            1: [
                ValidationIssue(
                    code="SECTION_BLOCK_LIMIT",
                    message="section exceeds max_blocks_per_section",
                    path="sections.explain",
                )
            ]
        },
    )

    result = await run_lesson_approach_planner(
        _packet(), legality=_make_snapshot(), require_items=False
    )

    assert len(planner_calls) == len(reviewer_calls) == 1
    assert result.validation.ok is True
    by_code = {flag["code"]: flag for flag in result.flags}
    assert {"assessment_item_reused", "target_coverage_gap", "SECTION_BLOCK_LIMIT"} <= set(by_code)
    reused = by_code["assessment_item_reused"]
    assert reused["source"] == "reviewer" and reused["severity"] == "warning"
    assert reused["section_ids"] == ["explain"] and reused["block_ids"] == ["explain-b1"]
    assert reused["repair_instruction"]
    limit = by_code["SECTION_BLOCK_LIMIT"]
    assert limit["source"] == "validator" and limit["section_ids"] == ["explain"]
    # Flags never change the hashed plan content.
    assert teaching_plan_content_hash(result.plan) == _candidate_hash()
    issue = next(i for i in result.validation.issues if i.code == "SECTION_BLOCK_LIMIT")
    assert issue.blocking is False


@pytest.mark.asyncio
async def test_advisory_hard_issue_still_repairs_and_flags_are_not_repair_work(
    monkeypatch, advisory_gate
) -> None:
    clean = TeachingPlanSemanticReviewResult(
        content_hash=_candidate_hash(),
        findings=[_finding("factual_inaccuracy", ["explain"])],
    )
    planner_calls, reviewer_calls = _install(
        monkeypatch,
        reviews=[clean],
        extra_issues={
            1: [
                ValidationIssue(code="UNKNOWN_ITEM", message="unknown source_question_id 'x'"),
                ValidationIssue(code="BRIEF_GENERIC", message="banned generic phrase"),
            ]
        },
    )

    result = await run_lesson_approach_planner(
        _packet(), legality=_make_snapshot(), require_items=False
    )

    # Attempt 1 has a hard issue: no reviewer call, one repair round, then pass.
    assert len(planner_calls) == 2
    assert len(reviewer_calls) == 1
    errors = planner_calls[1]["user_payload"]["repair"]["validation_errors"]
    assert any(error.startswith("UNKNOWN_ITEM") for error in errors)
    assert not any("BRIEF_GENERIC" in error for error in errors)
    assert [flag["code"] for flag in result.flags] == ["factual_inaccuracy"]


@pytest.mark.asyncio
async def test_advisory_persistent_hard_issue_still_fails(monkeypatch, advisory_gate) -> None:
    hard = ValidationIssue(code="DUPLICATE_BLOCK_ID", message="duplicate block id 'x'")
    _install(monkeypatch, reviews=[], extra_issues={1: [hard], 2: [hard]})
    with pytest.raises(TeachingPlanOutputInvalidError, match="DUPLICATE_BLOCK_ID"):
        await run_lesson_approach_planner(
            _packet(), legality=_make_snapshot(), require_items=False
        )


@pytest.mark.asyncio
async def test_advisory_reviewer_failure_is_still_a_hard_failure(
    monkeypatch, advisory_gate
) -> None:
    error = TeachingPlanSemanticReviewError("TEACHING_SEMANTIC_REVIEW_FAILED", "provider down")
    _install(monkeypatch, reviews=[error])
    with pytest.raises(TeachingPlanSemanticReviewError):
        await run_lesson_approach_planner(
            _packet(), legality=_make_snapshot(), require_items=False
        )


@pytest.mark.asyncio
async def test_blocking_mode_rejects_semantic_findings_as_before(
    monkeypatch, blocking_gate
) -> None:
    finding = TeachingPlanSemanticReviewResult(
        content_hash=_candidate_hash(),
        findings=[_finding("target_coverage_gap", ["explain"])],
    )
    planner_calls, reviewer_calls = _install(monkeypatch, reviews=[finding, finding])
    with pytest.raises(TeachingPlanOutputInvalidError, match="SEMANTIC_TARGET_COVERAGE_GAP"):
        await run_lesson_approach_planner(
            _packet(), legality=_make_snapshot(), require_items=False
        )
    assert len(planner_calls) == len(reviewer_calls) == 2


@pytest.mark.asyncio
async def test_blocking_mode_rejects_advisory_validator_issues_and_has_no_flags(
    monkeypatch, blocking_gate
) -> None:
    clean = TeachingPlanSemanticReviewResult(content_hash=_candidate_hash(), findings=[])
    limit = ValidationIssue(code="SECTION_BLOCK_LIMIT", message="too many", path="sections.explain")
    planner_calls, _ = _install(
        monkeypatch, reviews=[clean], extra_issues={1: [limit]}
    )
    result = await run_lesson_approach_planner(
        _packet(), legality=_make_snapshot(), require_items=False
    )
    assert len(planner_calls) == 2  # attempt 1 blocked, attempt 2 clean
    assert result.flags == []


@pytest.mark.asyncio
async def test_visual_missing_finding_is_only_a_flag_even_in_blocking_mode(
    monkeypatch, blocking_gate
) -> None:
    review = TeachingPlanSemanticReviewResult(
        content_hash=_candidate_hash(),
        findings=[_finding("visual_missing_for_figure_objective", ["explain"])],
    )
    planner_calls, reviewer_calls = _install(monkeypatch, reviews=[review])
    result = await run_lesson_approach_planner(
        _packet(), legality=_make_snapshot(), require_items=False
    )
    assert len(planner_calls) == len(reviewer_calls) == 1  # no repair round
    flags = [flag for flag in result.flags if flag["code"] == "visual_missing_for_figure_objective"]
    assert len(flags) == 1
    assert flags[0]["source"] == "reviewer" and flags[0]["severity"] == "warning"
    assert flags[0]["section_ids"] == ["explain"] and flags[0]["block_ids"] == []


def test_visual_spec_invalid_is_a_hard_plan_issue() -> None:
    assert "VISUAL_SPEC_INVALID" in HARD_PLAN_ISSUE_CODES
    assert is_hard_plan_issue("VISUAL_SPEC_INVALID")

"""Advisory vs blocking Teaching Plan quality gate (providers are stubbed)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests.planning.test_teaching_plan_semantic_review import _draft

from application.unit_lesson import teaching_planner as teaching_agent
from core.config import settings
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import materialize_teaching_plan
from print.generation.whole_lesson import validation as validation_module
from print.generation.whole_lesson.validation import (
    ADVISORY_PLAN_ISSUE_CODES,
    HARD_PLAN_ISSUE_CODES,
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


def test_visual_spec_invalid_is_a_hard_plan_issue() -> None:
    assert "VISUAL_SPEC_INVALID" in HARD_PLAN_ISSUE_CODES
    assert is_hard_plan_issue("VISUAL_SPEC_INVALID")

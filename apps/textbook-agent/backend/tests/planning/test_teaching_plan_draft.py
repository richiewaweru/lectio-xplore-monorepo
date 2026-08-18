from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.llm.deepseek_schema import to_deepseek_strict_schema
from planning.whole_lesson.teaching_plan import (
    AnchorUsage,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
    materialize_teaching_plan,
)


def _draft_block(**overrides: object) -> TeachingPlanDraftBlock:
    payload = {
        "intent": "explain",
        "brief": "Explain why light matters for food making.",
        "evidence_refs": ["lesson.objective"],
        "evidence": "The objective requires a causal explanation.",
        "departure_reason": None,
        "source_question_ids": [],
    }
    payload.update(overrides)
    return TeachingPlanDraftBlock.model_validate(payload)


def _draft(**overrides: object) -> TeachingPlanDraft:
    payload = {
        "arc": "Open on two plants, explain the changed condition, and check understanding.",
        "anchor_usage": AnchorUsage(
            orient="Introduce the two plants.",
            explain="Use the plants to isolate light.",
            check="Return to the plants.",
        ),
        "misconception_focus_ids": [],
        "sections": [
            TeachingPlanDraftSection(
                specific_purpose="Open the lesson.",
                transition=None,
                blocks=[
                    _draft_block(intent="compare", brief="Show what stayed the same."),
                    _draft_block(intent="explain", brief="State the role of light."),
                ],
            ),
            TeachingPlanDraftSection(
                specific_purpose="Check understanding.",
                transition="Learners are ready to explain the role of light.",
                blocks=[_draft_block(intent="check-understanding", brief="Check the explanation.")],
            ),
        ],
    }
    payload.update(overrides)
    return TeachingPlanDraft.model_validate(payload)


def test_teaching_draft_schema_excludes_upstream_identity_fields() -> None:
    schema = TeachingPlanDraft.model_json_schema()
    defs = schema["$defs"]
    assert "slot_id" not in defs["TeachingPlanDraftSection"]["properties"]
    block_props = defs["TeachingPlanDraftBlock"]["properties"]
    assert "id" not in block_props
    assert "position" not in block_props
    projected = to_deepseek_strict_schema(schema)
    projected_defs = projected["$defs"]
    assert "slot_id" not in projected_defs["TeachingPlanDraftSection"]["properties"]
    assert "id" not in projected_defs["TeachingPlanDraftBlock"]["properties"]
    assert "position" not in projected_defs["TeachingPlanDraftBlock"]["properties"]


def test_teaching_draft_rejects_upstream_identity_fields() -> None:
    with pytest.raises(ValidationError):
        TeachingPlanDraftSection.model_validate(
            {
                "slot_id": "orient",
                "specific_purpose": "Open",
                "blocks": [],
            }
        )
    with pytest.raises(ValidationError):
        TeachingPlanDraftBlock.model_validate(
            {
                "id": "orient-b1",
                "position": 0,
                "intent": "explain",
                "brief": "Explain.",
                "evidence_refs": ["lesson.objective"],
                "evidence": "Because the objective requires explanation.",
            }
        )


def test_materialize_teaching_plan_stamps_slot_and_block_ids() -> None:
    plan = materialize_teaching_plan(
        _draft(),
        slot_ids=["orient", "check"],
    )

    assert [section.slot_id for section in plan.sections] == ["orient", "check"]
    assert [block.id for block in plan.sections[0].blocks] == ["orient-b1", "orient-b2"]
    assert [block.position for block in plan.sections[0].blocks] == [0, 1]
    assert plan.sections[1].blocks[0].id == "check-b1"
    assert plan.sections[1].blocks[0].position == 0


def test_materialize_teaching_plan_rejects_section_count_mismatch() -> None:
    with pytest.raises(ValueError, match="exactly 1 sections"):
        materialize_teaching_plan(_draft(), slot_ids=["orient"])

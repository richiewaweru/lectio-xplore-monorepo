from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.prompts.loader import get_manifest_entry
from curriculum.backbone.models import ANCHOR_ID
from curriculum.prompts import teaching_section_prompt, teaching_spine_prompt
from curriculum.teaching_plan.models import TeachingPlanDraftBlock, materialize_teaching_plan
from curriculum.teaching_plan.staged import (
    TeachingSectionDraft,
    TeachingSpineDraft,
    TeachingSpineSectionDraft,
    assemble_teaching_plan_draft,
    materialize_teaching_spine,
)
from infra.authoring.model_policy import (
    TEACHING_SECTION_PLANNER,
    TEACHING_SPINE_PLANNER,
    get_v3_slot,
)
from print.generation.whole_lesson.prompt_render import assert_no_page_object_ids


def _section(index: int, **overrides) -> dict:
    data = {
        "display_title": f"Section {index}",
        "specific_purpose": "Do one job.",
        "transition": None if index == 0 else "Now we move on.",
        "entry_state": [f"entry {index}"],
        "must_establish": [f"establish {index}"],
        "avoid_repeating": [],
        "bridge_from_previous": None if index == 0 else f"bridge {index}",
        "exit_state": [f"exit {index}"],
        "anchor_usage": f"anchor use {index}",
        "planned_block_count": 1,
    }
    data.update(overrides)
    return data


def _spine_draft(sections: list[dict] | None = None, **overrides) -> TeachingSpineDraft:
    data = {
        "learner_title": "Why plants need light",
        "arc": "Notice, then explain.",
        "starting_state": ["start"],
        "target_state": ["target"],
        "sections": sections if sections is not None else [_section(0), _section(1)],
    }
    data.update(overrides)
    return TeachingSpineDraft.model_validate(data)


def _block(**overrides) -> TeachingPlanDraftBlock:
    data = {
        "intent": "explain-cause",
        "brief": "Compare the two plants and name light as the changed condition.",
        "evidence_refs": ["lesson.objective"],
        "evidence": "The objective asks why light matters.",
    }
    data.update(overrides)
    return TeachingPlanDraftBlock.model_validate(data)


def test_section_validators_reject_bad_states() -> None:
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, display_title="  "))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, entry_state=[]))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, exit_state=["a", "a"]))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, misconception_ids=["m", "m"]))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, approved_item_ids=["i", "i"]))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, planned_block_count=0))
    with pytest.raises(ValidationError):
        TeachingSpineSectionDraft.model_validate(_section(0, unknown="x"))
    TeachingSpineSectionDraft.model_validate(_section(0, avoid_repeating=[]))


def test_spine_validators_enforce_bridges() -> None:
    assert _spine_draft().sections[1].bridge_from_previous == "bridge 1"
    with pytest.raises(ValidationError):
        _spine_draft([_section(0, bridge_from_previous="x"), _section(1)])
    with pytest.raises(ValidationError):
        _spine_draft([_section(0), _section(1, bridge_from_previous=" ")])
    with pytest.raises(ValidationError):
        _spine_draft(learner_title=" ")
    with pytest.raises(ValidationError):
        _spine_draft(starting_state=[])
    with pytest.raises(ValidationError):
        _spine_draft(misconception_focus_ids=["m", "m"])
    with pytest.raises(ValidationError):
        _spine_draft(sections=[])


def test_materialize_spine_slot_ids_and_backbone_targets() -> None:
    draft = _spine_draft(
        [
            _section(0, approved_item_ids=["q1", "q2"]),
            _section(1, approved_item_ids=["q3"]),
        ]
    )
    refs = {
        "q1": {"target": "variant-1"},
        "q2": {"target": "variant-1"},
        "q3": {"target": "variant-2"},
    }
    spine = materialize_teaching_spine(
        draft, slot_ids=["orient", "explain"], item_backbone_refs=refs
    )
    assert [s.slot_id for s in spine.sections] == ["orient", "explain"]
    assert spine.sections[0].backbone_targets == ["variant-1"]
    assert spine.sections[1].backbone_targets == ["variant-2"]


def test_materialize_spine_anchor_fallback_and_length_mismatch() -> None:
    spine = materialize_teaching_spine(
        _spine_draft(), slot_ids=["a", "b"], item_backbone_refs={}
    )
    assert all(s.backbone_targets == [ANCHOR_ID] for s in spine.sections)
    with pytest.raises(ValueError):
        materialize_teaching_spine(_spine_draft(), slot_ids=["a"], item_backbone_refs={})


def test_assemble_materializes_with_block_ids_and_anchor_order() -> None:
    spine = materialize_teaching_spine(
        _spine_draft([_section(0, planned_block_count=2), _section(1)]),
        slot_ids=["orient", "explain"],
        item_backbone_refs={},
    )
    draft = assemble_teaching_plan_draft(
        spine,
        {"explain": [_block()], "orient": [_block(intent="orient"), _block()]},
    )
    assert [e.slot_id for e in draft.anchor_usage] == ["orient", "explain"]
    assert draft.anchor_usage[1].usage == "anchor use 1"
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    assert [b.id for b in plan.sections[0].blocks] == ["orient-b1", "orient-b2"]
    assert [b.id for b in plan.sections[1].blocks] == ["explain-b1"]
    assert plan.sections[1].bridge_from_previous == "bridge 1"


def test_assemble_names_missing_slot() -> None:
    spine = materialize_teaching_spine(
        _spine_draft(), slot_ids=["orient", "explain"], item_backbone_refs={}
    )
    with pytest.raises(ValueError, match="explain"):
        assemble_teaching_plan_draft(spine, {"orient": [_block()]})


def test_section_draft_requires_blocks() -> None:
    with pytest.raises(ValidationError):
        TeachingSectionDraft.model_validate({"blocks": []})
    with pytest.raises(ValidationError):
        TeachingSectionDraft.model_validate({"blocks": [_block().model_dump()], "id": "x"})


def test_prompts_manifest_and_no_object_leak() -> None:
    spine = teaching_spine_prompt()
    section = teaching_section_prompt()
    assert "{resource_identity}" in spine
    assert "{resource_identity}" in section
    assert "planned_block_count" in section and "figure_ref" in section
    assert_no_page_object_ids(spine, where="teaching-spine")
    assert_no_page_object_ids(section, where="teaching-section")
    for prompt_id in ("teaching-spine", "teaching-section"):
        entry = get_manifest_entry(prompt_id)
        assert entry is not None and entry.editable is False


def test_model_policy_spine_and_section_share_the_standard_slot() -> None:
    from core.llm import ModelSlot

    assert get_v3_slot(TEACHING_SPINE_PLANNER) == ModelSlot.STANDARD
    assert get_v3_slot(TEACHING_SECTION_PLANNER) == ModelSlot.STANDARD

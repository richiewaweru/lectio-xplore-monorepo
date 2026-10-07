"""Staged teaching planner schema: spine, per-section drafts, and assembly.

The spine fixes lesson-wide continuity (titles, state chains, item and
misconception placement, block budgets). Each section call then writes only
that section's blocks. Pure models and functions; slot identity is code-owned.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum.backbone.models import ANCHOR_ID
from curriculum.teaching_plan.instance_ids import normalize_slot_instance_ids
from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSectionV2,
    TeachingPlanDraftV2,
    _require_meaningful,
    _require_unique_state_list,
)


def _require_unique_ids(values: list[str], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")


class SpineFigurePlan(BaseModel):
    """One figure a section must carry; optionally a reused backbone figure."""

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=1)
    backbone_figure_id: str | None = None


class TeachingSpineSectionDraft(BaseModel):
    """Provider-owned spine section. Slot identity is code-owned (by position)."""

    model_config = ConfigDict(extra="forbid")

    display_title: str = Field(min_length=1)
    specific_purpose: str = ""
    transition: str | None = None
    entry_state: list[str]
    must_establish: list[str]
    avoid_repeating: list[str]
    bridge_from_previous: str | None
    exit_state: list[str]
    anchor_usage: str = ""
    planned_block_count: int = Field(ge=1)
    misconception_ids: list[str] = Field(default_factory=list)
    approved_item_ids: list[str] = Field(default_factory=list)
    figure_plan: list[SpineFigurePlan] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_continuity(self) -> TeachingSpineSectionDraft:
        _require_meaningful(self.display_title, "section display_title")
        _require_unique_state_list(self.entry_state, "section entry_state")
        _require_unique_state_list(self.must_establish, "section must_establish")
        _require_unique_state_list(
            self.avoid_repeating,
            "section avoid_repeating",
            allow_empty=True,
        )
        _require_unique_state_list(self.exit_state, "section exit_state")
        _require_unique_ids(self.misconception_ids, "section misconception_ids")
        _require_unique_ids(self.approved_item_ids, "section approved_item_ids")
        return self


class TeachingSpineDraft(BaseModel):
    """LLM output of the spine call."""

    model_config = ConfigDict(extra="forbid")

    learner_title: str = Field(min_length=1)
    arc: str = Field(min_length=1)
    starting_state: list[str]
    target_state: list[str]
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingSpineSectionDraft] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_continuity(self) -> TeachingSpineDraft:
        _require_meaningful(self.learner_title, "learner_title")
        _require_unique_state_list(self.starting_state, "starting_state")
        _require_unique_state_list(self.target_state, "target_state")
        _require_unique_ids(self.misconception_focus_ids, "misconception_focus_ids")
        for index, section in enumerate(self.sections):
            if index == 0 and section.bridge_from_previous is not None:
                raise ValueError("first spine section bridge_from_previous must be null")
            if index > 0:
                _require_meaningful(section.bridge_from_previous, "bridge_from_previous")
        return self


class TeachingSpineSection(TeachingSpineSectionDraft):
    """Materialized spine section: slot identity and backbone targets are code-owned."""

    slot_id: str = Field(min_length=1)
    backbone_targets: list[str] = Field(default_factory=list)


class TeachingSpine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_title: str = Field(min_length=1)
    arc: str = Field(min_length=1)
    starting_state: list[str]
    target_state: list[str]
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingSpineSection] = Field(min_length=1)


class TeachingSectionDraft(BaseModel):
    """LLM output of each section call: blocks only."""

    model_config = ConfigDict(extra="forbid")

    blocks: list[TeachingPlanDraftBlock] = Field(min_length=1)


def materialize_teaching_spine(
    draft: TeachingSpineDraft,
    *,
    slot_ids: list[str],
    item_backbone_refs: dict[str, dict],
) -> TeachingSpine:
    """Attach slot ids by position and derive each section's backbone targets."""
    slot_ids = normalize_slot_instance_ids(slot_ids)
    if len(draft.sections) != len(slot_ids):
        raise ValueError(
            f"spine has {len(draft.sections)} sections but packet has {len(slot_ids)} slots"
        )
    sections: list[TeachingSpineSection] = []
    for slot_id, section in zip(slot_ids, draft.sections, strict=True):
        targets: list[str] = []
        for item_id in section.approved_item_ids:
            target = (item_backbone_refs.get(item_id) or {}).get("target")
            if target and target not in targets:
                targets.append(target)
        sections.append(
            TeachingSpineSection(
                **section.model_dump(),
                slot_id=slot_id,
                backbone_targets=targets or [ANCHOR_ID],
            )
        )
    return TeachingSpine(
        learner_title=draft.learner_title,
        arc=draft.arc,
        starting_state=list(draft.starting_state),
        target_state=list(draft.target_state),
        misconception_focus_ids=list(draft.misconception_focus_ids),
        sections=sections,
    )


def assemble_teaching_plan_draft(
    spine: TeachingSpine,
    section_blocks: dict[str, list[TeachingPlanDraftBlock]],
) -> TeachingPlanDraftV2:
    """Combine the spine's continuity fields with per-section blocks."""
    sections: list[TeachingPlanDraftSectionV2] = []
    for section in spine.sections:
        if section.slot_id not in section_blocks:
            raise ValueError(f"missing blocks for slot {section.slot_id}")
        sections.append(
            TeachingPlanDraftSectionV2(
                display_title=section.display_title,
                specific_purpose=section.specific_purpose,
                transition=section.transition,
                entry_state=list(section.entry_state),
                must_establish=list(section.must_establish),
                avoid_repeating=list(section.avoid_repeating),
                bridge_from_previous=section.bridge_from_previous,
                exit_state=list(section.exit_state),
                blocks=list(section_blocks[section.slot_id]),
            )
        )
    return TeachingPlanDraftV2(
        learner_title=spine.learner_title,
        arc=spine.arc,
        starting_state=list(spine.starting_state),
        target_state=list(spine.target_state),
        anchor_usage=[
            AnchorUsageEntry(slot_id=s.slot_id, usage=s.anchor_usage) for s in spine.sections
        ],
        misconception_focus_ids=list(spine.misconception_focus_ids),
        sections=sections,
    )


__all__ = [
    "SpineFigurePlan",
    "TeachingSectionDraft",
    "TeachingSpine",
    "TeachingSpineDraft",
    "TeachingSpineSection",
    "TeachingSpineSectionDraft",
    "assemble_teaching_plan_draft",
    "materialize_teaching_spine",
]

"""Whole-lesson teaching plan schema (proposal §7.1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TeachingPlanBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position: int = Field(ge=0)
    intent: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=1)
    departure_reason: str | None = None
    source_question_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Approved assessment-item ownership. Leave empty for a non-assessment "
            "block. A multiple-choice source must be the only ID in this array."
        ),
    )

    @model_validator(mode="after")
    def _normalize_departure(self) -> TeachingPlanBlock:
        if self.departure_reason is not None and not self.departure_reason.strip():
            self.departure_reason = None
        return self


class TeachingPlanSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    specific_purpose: str = ""
    transition: str | None = None
    blocks: list[TeachingPlanBlock] = Field(default_factory=list)


class AnchorUsageEntry(BaseModel):
    """Provider-authored mapping of one packet slot_id to its anchor usage."""

    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(min_length=1)
    usage: str = ""


def _reject_duplicate_anchor_usages(entries: list[AnchorUsageEntry]) -> None:
    slot_ids = [e.slot_id for e in entries]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("anchor_usage slot_id values must be unique")


class TeachingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    anchor_usage: list[AnchorUsageEntry] = Field(default_factory=list)
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingPlanSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_anchor_usages(self) -> TeachingPlan:
        _reject_duplicate_anchor_usages(self.anchor_usage)
        return self


class TeachingPlanDraftBlock(BaseModel):
    """Provider-owned semantic block payload. Technical identity is code-owned."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=1)
    departure_reason: str | None = None
    source_question_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Approved assessment-item ownership. Leave empty for a non-assessment "
            "block. A multiple-choice source must be the only ID in this array."
        ),
    )


class TeachingPlanDraftSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specific_purpose: str = ""
    transition: str | None = None
    blocks: list[TeachingPlanDraftBlock] = Field(default_factory=list)


class TeachingPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    anchor_usage: list[AnchorUsageEntry] = Field(default_factory=list)
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingPlanDraftSection] = Field(default_factory=list)


def materialize_teaching_plan(
    draft: TeachingPlanDraft,
    *,
    slot_ids: list[str],
) -> TeachingPlan:
    if len(draft.sections) != len(slot_ids):
        raise ValueError(
            f"Teaching draft must return exactly {len(slot_ids)} sections; "
            f"got {len(draft.sections)}"
        )
    return TeachingPlan(
        arc=draft.arc,
        anchor_usage=draft.anchor_usage,
        misconception_focus_ids=list(draft.misconception_focus_ids),
        sections=[
            TeachingPlanSection(
                slot_id=slot_id,
                specific_purpose=section.specific_purpose,
                transition=section.transition,
                blocks=[
                    TeachingPlanBlock(
                        id=f"{slot_id}-b{position + 1}",
                        position=position,
                        intent=block.intent,
                        brief=block.brief,
                        evidence_refs=list(block.evidence_refs),
                        evidence=block.evidence,
                        departure_reason=block.departure_reason,
                        source_question_ids=list(block.source_question_ids),
                    )
                    for position, block in enumerate(section.blocks)
                ],
            )
            for slot_id, section in zip(slot_ids, draft.sections, strict=True)
        ],
    )

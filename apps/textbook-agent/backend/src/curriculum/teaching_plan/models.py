"""Shared teaching plan models (instructional meaning, not native presentation)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Difficulty = Literal["guided", "independent"]
TaskMode = Literal["none", "formative", "assessment"]
LearnerActionId = Literal[
    "select-one",
    "select-many",
    "complete-missing-values",
    "classify-items",
    "match-pairs",
    "order-items",
    "reconstruct-order",
    "enter-number",
    "enter-text",
    "compare-without-response",
    "read-explanation",
]


class LearnerActionBrief(BaseModel):
    """Path-agnostic learner-task meaning — never a native component or form id.

    Minimum semantic fields only. Provenance (approved item ids, stimulus deps)
    lives on the TeachingPlanBlock, not here. ``action`` is a closed enum so
    structured-output providers cannot invent vocabulary that downstream paths
    do not understand.
    """

    model_config = ConfigDict(extra="forbid")

    action: LearnerActionId
    target: str = Field(
        min_length=1,
        description="What the learner acts on (concept, items, structure) — not a UI id.",
    )
    purpose: str = Field(
        min_length=1,
        description="Why the learner is asked to do this.",
    )
    expected_evidence: str = Field(
        min_length=1,
        description="What successful performance should show.",
    )
    difficulty: Difficulty


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
        max_length=6,
        description=(
            "Approved assessment-item ownership. Leave empty for a non-assessment "
            "block. A multiple-choice source must be the only ID in this array."
        ),
    )
    task_mode: TaskMode = "none"
    sourcebook_needs: list[str] = Field(default_factory=list)
    sourcebook_refs: list[str] = Field(default_factory=list)
    stimulus_dependencies: list[str] = Field(
        default_factory=list,
        description="Stimulus or content asset ids this block's learner task depends on.",
    )
    learner_action: LearnerActionBrief | None = None

    @model_validator(mode="after")
    def _normalize_and_check_provenance(self) -> TeachingPlanBlock:
        if self.departure_reason is not None and not self.departure_reason.strip():
            self.departure_reason = None
        if len(self.source_question_ids) != len(set(self.source_question_ids)):
            raise ValueError("source_question_ids must not contain duplicates")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must not contain duplicates")
        if self.task_mode == "formative" and self.source_question_ids:
            raise ValueError("formative tasks cannot own approved assessment sources")
        if self.task_mode == "assessment" and self.learner_action is None:
            raise ValueError("assessment tasks require a learner_action")
        if self.task_mode == "assessment" and not self.source_question_ids:
            raise ValueError("assessment tasks require approved source_question_ids")
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
    # Code-owned identity fields (optional on legacy records).
    teaching_plan_id: str | None = None
    revision: int | None = None
    preparation_hash: str | None = None
    approval_status: str | None = None

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
        max_length=6,
        description=(
            "Approved assessment-item ownership. Leave empty for a non-assessment "
            "block. A multiple-choice source must be the only ID in this array."
        ),
    )
    task_mode: TaskMode = "none"
    sourcebook_needs: list[str] = Field(default_factory=list)
    sourcebook_refs: list[str] = Field(default_factory=list)
    stimulus_dependencies: list[str] = Field(
        default_factory=list,
        description="Stimulus or content asset ids this block's learner task depends on.",
    )
    learner_action: LearnerActionBrief | None = None

    @model_validator(mode="after")
    def _reject_duplicate_refs(self) -> TeachingPlanDraftBlock:
        if len(self.source_question_ids) != len(set(self.source_question_ids)):
            raise ValueError("source_question_ids must not contain duplicates")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must not contain duplicates")
        if self.task_mode == "formative" and self.source_question_ids:
            raise ValueError("formative tasks cannot own approved assessment sources")
        if self.task_mode == "assessment" and self.learner_action is None:
            raise ValueError("assessment tasks require a learner_action")
        if self.task_mode == "assessment" and not self.source_question_ids:
            raise ValueError("assessment tasks require approved source_question_ids")
        return self


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


class TeachingRevisionRecord(BaseModel):
    """Immutable snapshot of one approved (or pending) teaching revision."""

    model_config = ConfigDict(extra="forbid")

    teaching_plan_id: str
    revision: int = Field(ge=1)
    status: Literal["pending", "approved", "superseded", "rejected"]
    preparation_hash: str
    content_hash: str | None = None
    approval_hash_binding: Literal["submitted", "server_current_compat"] | None = None
    plan: dict[str, Any]
    created_at: str
    approved_at: str | None = None
    reviewed_by: str | None = None
    teacher_note: str | None = None
    supersedes_revision: int | None = None


def materialize_teaching_plan(
    draft: TeachingPlanDraft,
    *,
    slot_ids: list[str],
    teaching_plan_id: str | None = None,
    revision: int | None = None,
    preparation_hash: str | None = None,
) -> TeachingPlan:
    if len(draft.sections) != len(slot_ids):
        raise ValueError(
            f"Teaching draft must return exactly {len(slot_ids)} sections; "
            f"got {len(draft.sections)}"
        )
    return TeachingPlan(
        teaching_plan_id=teaching_plan_id,
        revision=revision,
        preparation_hash=preparation_hash,
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
                        stimulus_dependencies=list(block.stimulus_dependencies),
                        task_mode=block.task_mode,
                        sourcebook_needs=list(block.sourcebook_needs),
                        sourcebook_refs=list(block.sourcebook_refs),
                        learner_action=block.learner_action,
                    )
                    for position, block in enumerate(section.blocks)
                ],
            )
            for slot_id, section in zip(slot_ids, draft.sections, strict=True)
        ],
    )


__all__ = [
    "AnchorUsageEntry",
    "Difficulty",
    "LearnerActionBrief",
    "LearnerActionId",
    "TaskMode",
    "TeachingPlan",
    "TeachingPlanBlock",
    "TeachingPlanDraft",
    "TeachingPlanDraftBlock",
    "TeachingPlanDraftSection",
    "TeachingPlanSection",
    "TeachingRevisionRecord",
    "materialize_teaching_plan",
]

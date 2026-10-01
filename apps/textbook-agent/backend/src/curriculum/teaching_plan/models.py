"""Shared teaching plan models (instructional meaning, not native presentation)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

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
    display_title: str | None = None
    entry_state: list[str] | None = None
    must_establish: list[str] | None = None
    avoid_repeating: list[str] | None = None
    bridge_from_previous: str | None = None
    exit_state: list[str] | None = None


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
    contract_version: Literal[1, 2] = 1
    learner_title: str | None = None
    starting_state: list[str] | None = None
    target_state: list[str] | None = None
    # Code-owned identity fields (optional on legacy records).
    teaching_plan_id: str | None = None
    revision: int | None = None
    preparation_hash: str | None = None
    approval_status: str | None = None

    @model_validator(mode="after")
    def _validate_anchor_usages(self) -> TeachingPlan:
        _reject_duplicate_anchor_usages(self.anchor_usage)
        enriched_plan_values = (
            self.learner_title,
            self.starting_state,
            self.target_state,
        )
        enriched_section_values = [
            value
            for section in self.sections
            for value in (
                section.display_title,
                section.entry_state,
                section.must_establish,
                section.avoid_repeating,
                section.bridge_from_previous,
                section.exit_state,
            )
        ]
        if self.contract_version == 1:
            if any(
                value is not None for value in enriched_plan_values + tuple(enriched_section_values)
            ):
                raise ValueError("Teaching Plan v1 cannot include v2 continuity fields")
            return self

        _require_meaningful(self.learner_title, "learner_title")
        _require_unique_state_list(self.starting_state, "starting_state")
        _require_unique_state_list(self.target_state, "target_state")
        slot_ids = [section.slot_id for section in self.sections]
        if not slot_ids or any(not slot_id.strip() for slot_id in slot_ids):
            raise ValueError("v2 Teaching Plans require non-empty section slot_ids")
        if any(slot_id != slot_id.strip() for slot_id in slot_ids):
            raise ValueError("v2 section slot_ids cannot have surrounding whitespace")
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("v2 Teaching Plan section slot_ids must be unique")
        if any(entry.slot_id != entry.slot_id.strip() for entry in self.anchor_usage):
            raise ValueError("anchor_usage slot_id cannot have surrounding whitespace")
        if any(entry.slot_id not in set(slot_ids) for entry in self.anchor_usage):
            raise ValueError("anchor_usage slot_id must belong to a Teaching Plan section")
        for index, section in enumerate(self.sections):
            for field_name in (
                "display_title",
                "entry_state",
                "must_establish",
                "avoid_repeating",
                "exit_state",
            ):
                if field_name not in section.model_fields_set:
                    raise ValueError(f"v2 section requires {field_name}")
            _require_meaningful(section.display_title, "section display_title")
            _require_unique_state_list(section.entry_state, "section entry_state")
            _require_unique_state_list(section.must_establish, "section must_establish")
            _require_unique_state_list(
                section.avoid_repeating,
                "section avoid_repeating",
                allow_empty=True,
            )
            _require_unique_state_list(section.exit_state, "section exit_state")
            if "bridge_from_previous" not in section.model_fields_set:
                raise ValueError("v2 section requires bridge_from_previous")
            if index == 0:
                if section.bridge_from_previous is not None:
                    raise ValueError("first v2 section bridge_from_previous must be null")
            else:
                _require_meaningful(section.bridge_from_previous, "bridge_from_previous")
        return self

    @model_serializer(mode="wrap")
    def _serialize_versioned_plan(self, handler):
        payload = handler(self)
        if self.contract_version == 1:
            payload.pop("contract_version", None)
            payload.pop("learner_title", None)
            payload.pop("starting_state", None)
            payload.pop("target_state", None)
            for section in payload.get("sections", []):
                for field_name in (
                    "display_title",
                    "entry_state",
                    "must_establish",
                    "avoid_repeating",
                    "bridge_from_previous",
                    "exit_state",
                ):
                    section.pop(field_name, None)
        return payload


def _validate_sourcebook_need_refs(needs: list[str], refs: list[str]) -> None:
    """Require explicit approved identities whenever a block needs sourcebook content."""

    if needs and not refs:
        raise ValueError("sourcebook_needs require approved sourcebook_refs")
    if any(not ref.strip() or ref != ref.strip() for ref in refs):
        raise ValueError("sourcebook_refs must be non-empty canonical identities")


def validate_sourcebook_need_refs(plan: TeachingPlan) -> None:
    """Validate sourcebook bindings at the Teaching Plan approval boundary."""

    for section in plan.sections:
        for block in section.blocks:
            _validate_sourcebook_need_refs(block.sourcebook_needs, block.sourcebook_refs)


def _require_meaningful(value: str | None, name: str) -> None:
    if value is None or not value.strip():
        raise ValueError(f"{name} must be meaningful and non-empty")


def _require_unique_state_list(
    values: list[str] | None,
    name: str,
    *,
    allow_empty: bool = False,
) -> None:
    if values is None or (not allow_empty and not values):
        raise ValueError(f"{name} must contain meaningful entries")
    normalized = [value.strip() for value in values]
    if any(not value for value in normalized):
        raise ValueError(f"{name} entries must be meaningful and non-empty")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} entries must be unique")


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
        _validate_sourcebook_need_refs(self.sourcebook_needs, self.sourcebook_refs)
        return self


class TeachingPlanDraftSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specific_purpose: str = ""
    transition: str | None = None
    blocks: list[TeachingPlanDraftBlock] = Field(default_factory=list)


class TeachingPlanDraftSectionV2(TeachingPlanDraftSection):
    """Strict enriched section draft; section identity remains code-owned."""

    display_title: str = Field(min_length=1)
    entry_state: list[str]
    must_establish: list[str]
    avoid_repeating: list[str]
    bridge_from_previous: str | None
    exit_state: list[str]

    @model_validator(mode="after")
    def _validate_continuity(self) -> TeachingPlanDraftSectionV2:
        _require_meaningful(self.display_title, "section display_title")
        _require_unique_state_list(self.entry_state, "section entry_state")
        _require_unique_state_list(self.must_establish, "section must_establish")
        _require_unique_state_list(
            self.avoid_repeating,
            "section avoid_repeating",
            allow_empty=True,
        )
        _require_unique_state_list(self.exit_state, "section exit_state")
        return self


class TeachingPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    anchor_usage: list[AnchorUsageEntry] = Field(default_factory=list)
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingPlanDraftSection] = Field(default_factory=list)


class TeachingPlanDraftV2(BaseModel):
    """Closed enriched planner output contract for the Phase 2 cutover."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[2] = 2
    learner_title: str = Field(min_length=1)
    arc: str = Field(min_length=1)
    starting_state: list[str]
    target_state: list[str]
    anchor_usage: list[AnchorUsageEntry] = Field(default_factory=list)
    misconception_focus_ids: list[str] = Field(default_factory=list)
    sections: list[TeachingPlanDraftSectionV2] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_continuity(self) -> TeachingPlanDraftV2:
        _require_meaningful(self.learner_title, "learner_title")
        _require_unique_state_list(self.starting_state, "starting_state")
        _require_unique_state_list(self.target_state, "target_state")
        _reject_duplicate_anchor_usages(self.anchor_usage)
        for index, section in enumerate(self.sections):
            if index == 0 and section.bridge_from_previous is not None:
                raise ValueError("first v2 section bridge_from_previous must be null")
            if index > 0:
                _require_meaningful(section.bridge_from_previous, "bridge_from_previous")
        return self


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
    # Revision-bound approved assessment records.  These fields are optional so
    # rows written before shared-task authoring was introduced remain readable;
    # the shared-task verifier requires them when a plan owns source items.
    approved_item_snapshot: dict[str, Any] | None = None
    approved_item_snapshot_hash: str | None = None
    # Advisory quality flags recorded with this revision. Deliberately outside
    # ``plan`` so they never affect the approval content hash.
    flags: list[dict[str, Any]] = Field(default_factory=list)


def materialize_teaching_plan(
    draft: TeachingPlanDraft | TeachingPlanDraftV2,
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
    is_v2 = isinstance(draft, TeachingPlanDraftV2)
    if is_v2:
        if any(not slot_id.strip() for slot_id in slot_ids):
            raise ValueError("Teaching Plan slot_ids must be non-empty")
        if any(slot_id != slot_id.strip() for slot_id in slot_ids):
            raise ValueError("Teaching Plan slot_ids cannot have surrounding whitespace")
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("Teaching Plan slot_ids must be unique")
        if any(
            entry.slot_id != entry.slot_id.strip() or entry.slot_id not in set(slot_ids)
            for entry in draft.anchor_usage
        ):
            raise ValueError("anchor_usage slot_id must belong to a materialized section")
    return TeachingPlan(
        teaching_plan_id=teaching_plan_id,
        revision=revision,
        preparation_hash=preparation_hash,
        contract_version=2 if is_v2 else 1,
        learner_title=draft.learner_title if is_v2 else None,
        starting_state=list(draft.starting_state) if is_v2 else None,
        target_state=list(draft.target_state) if is_v2 else None,
        arc=draft.arc,
        anchor_usage=draft.anchor_usage,
        misconception_focus_ids=list(draft.misconception_focus_ids),
        sections=[
            TeachingPlanSection(
                slot_id=slot_id,
                specific_purpose=section.specific_purpose,
                transition=section.transition,
                display_title=section.display_title if is_v2 else None,
                entry_state=list(section.entry_state) if is_v2 else None,
                must_establish=list(section.must_establish) if is_v2 else None,
                avoid_repeating=list(section.avoid_repeating) if is_v2 else None,
                bridge_from_previous=section.bridge_from_previous if is_v2 else None,
                exit_state=list(section.exit_state) if is_v2 else None,
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
    "TeachingPlanDraftSectionV2",
    "TeachingPlanDraftV2",
    "TeachingPlanSection",
    "TeachingRevisionRecord",
    "materialize_teaching_plan",
]

"""Deterministic TeachingPlan + FormPlan join → ResolvedBlockPlan."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planning.whole_lesson.form_plan import FormDecision, FormPlan, Placement
from planning.whole_lesson.teaching_plan import TeachingPlan, TeachingPlanBlock
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan


class ResolvedBlockPlan(BaseModel):
    """Code-owned join of teaching pedagogy and form decisions."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position: int = Field(ge=0)
    intent: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    evidence: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    departure_reason: str | None = None
    source_question_ids: list[str] = Field(default_factory=list)
    object: str = Field(min_length=1)
    placement: Placement = "main"
    reason: str = ""
    escalation: str | None = None

    def to_planned_block(self) -> PlannedBlock:
        """Adapter for existing writer dispatch (PlannedBlock)."""
        return PlannedBlock(
            id=self.id,
            position=self.position,
            intent=self.intent,
            object=self.object,  # type: ignore[arg-type]
            evidence=self.evidence or "Resolved block.",
            brief=self.brief,
            placement=self.placement,
            # Never mask teaching-owned item IDs. PlannedBlock validation rejects
            # an incompatible form decision instead of silently dropping ownership.
            source_question_ids=list(self.source_question_ids),
        )


class ResolvedSectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    specific_purpose: str = ""
    blocks: list[ResolvedBlockPlan] = Field(default_factory=list)


class ResolvedLessonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[ResolvedSectionPlan] = Field(default_factory=list)

    def block_map(self) -> dict[str, ResolvedBlockPlan]:
        return {
            block.id: block
            for section in self.sections
            for block in section.blocks
        }

    def to_section_block_plans(self) -> dict[str, SectionBlockPlan]:
        return {
            section.slot_id: SectionBlockPlan(
                blocks=[block.to_planned_block() for block in section.blocks]
            )
            for section in self.sections
        }


def _join_block(
    teaching: TeachingPlanBlock,
    decision: FormDecision,
) -> ResolvedBlockPlan:
    return ResolvedBlockPlan(
        id=teaching.id,
        position=teaching.position,
        intent=teaching.intent,
        brief=teaching.brief,
        evidence=teaching.evidence,
        evidence_refs=list(teaching.evidence_refs),
        departure_reason=teaching.departure_reason,
        source_question_ids=list(teaching.source_question_ids),
        object=decision.object,
        placement=decision.placement,
        reason=decision.reason,
        escalation=decision.escalation,
    )


def resolve_block_plans(
    teaching_plan: TeachingPlan,
    form_plan: FormPlan,
) -> ResolvedLessonPlan:
    """Join teaching + form decisions. Pedagogy always from TeachingPlan."""
    decisions = form_plan.decision_map()
    sections: list[ResolvedSectionPlan] = []
    for teaching_section in teaching_plan.sections:
        form_section = next(
            (
                section
                for section in form_plan.sections
                if section.slot_id == teaching_section.slot_id
            ),
            None,
        )
        # Prefer teaching section order; decisions keyed by block id.
        resolved_blocks: list[ResolvedBlockPlan] = []
        for teaching_block in teaching_section.blocks:
            decision = decisions.get(teaching_block.id)
            if decision is None:
                raise ValueError(
                    f"form plan missing decision for teaching block {teaching_block.id!r}"
                )
            if form_section is not None:
                # Ensure the decision belongs to this section when present.
                section_ids = {item.block_id for item in form_section.forms}
                if teaching_block.id not in section_ids:
                    raise ValueError(
                        f"form decision for {teaching_block.id!r} is not in "
                        f"section {teaching_section.slot_id!r}"
                    )
            resolved_blocks.append(_join_block(teaching_block, decision))
        sections.append(
            ResolvedSectionPlan(
                slot_id=teaching_section.slot_id,
                specific_purpose=teaching_section.specific_purpose,
                blocks=resolved_blocks,
            )
        )
    return ResolvedLessonPlan(sections=sections)

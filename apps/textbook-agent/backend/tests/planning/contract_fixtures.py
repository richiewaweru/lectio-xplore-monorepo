"""Shared slim FormDecision + TeachingPlan fixtures for ownership tests."""

from __future__ import annotations

from planning.whole_lesson.form_plan import FormDecision, FormPlan, FormPlanSection
from planning.whole_lesson.teaching_plan import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    AnchorUsageEntry,
)


def teaching_and_form(
    *,
    sections: list[tuple[str, list[tuple[str, str, str]]]],
) -> tuple[TeachingPlan, FormPlan]:
    """Build matching TeachingPlan + FormPlan.

    sections: [(slot_id, [(block_id, intent, object), ...]), ...]
    """
    teaching_sections: list[TeachingPlanSection] = []
    form_sections: list[FormPlanSection] = []
    for slot_id, blocks in sections:
        teaching_blocks: list[TeachingPlanBlock] = []
        forms: list[FormDecision] = []
        for position, (block_id, intent, object_id) in enumerate(blocks):
            teaching_blocks.append(
                TeachingPlanBlock(
                    id=block_id,
                    position=position,
                    intent=intent,
                    brief=f"Brief for {block_id}",
                    evidence=f"Evidence for {block_id}",
                )
            )
            forms.append(
                FormDecision(
                    block_id=block_id,
                    object=object_id,
                    placement="main",
                    reason=f"prose/default for {block_id}",
                    escalation=None if object_id == "prose" else "prose would lose structure",
                )
            )
        teaching_sections.append(
            TeachingPlanSection(
                slot_id=slot_id,
                specific_purpose=f"Purpose {slot_id}",
                blocks=teaching_blocks,
            )
        )
        form_sections.append(FormPlanSection(slot_id=slot_id, forms=forms))
    teaching = TeachingPlan(
        arc="Orient → explain → check",
        anchor_usage=[
            AnchorUsageEntry(slot_id=slot_id, usage="")
            for slot_id, _blocks in sections
        ],
        sections=teaching_sections,
    )
    return teaching, FormPlan(sections=form_sections)

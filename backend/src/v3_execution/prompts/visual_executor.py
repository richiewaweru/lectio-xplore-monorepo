from __future__ import annotations

from v3_execution.prompts.formatting import format_source_of_truth
from v3_execution.models import VisualGeneratorWorkOrder


def format_anchor_for_visual(order: VisualGeneratorWorkOrder) -> str:
    if order.visual.uses_anchor_id:
        return format_source_of_truth(order.source_of_truth)
    return "(no anchor bindings)"


def build_visual_prompt(
    order: VisualGeneratorWorkOrder,
    previous_frame_description: str | None = None,
) -> str:
    anchor_block = ""
    if order.visual.uses_anchor_id:
        anchor_block = f"""
ANCHOR FACTS (preserve exactly — do not change dimensions, units, or labels):
{format_anchor_for_visual(order)}
"""

    continuity_block = ""
    if previous_frame_description:
        continuity_block = f"""
VISUAL CONTINUITY:
This image is part of a series. The previous frame showed:
{previous_frame_description}
Maintain consistent style and geometry; only depict new information.
"""

    frame_lines = (
        "\n".join(f"- Frame {idx}: {f.description}" for idx, f in enumerate(order.visual.frames))
        if order.visual.frames
        else "- single coherent frame"
    )

    must_show_block = (
        chr(10).join(f"- {item}" for item in order.visual.must_show)
        if order.visual.must_show
        else "- follow PURPOSE"
    )
    must_not_block = (
        chr(10).join(f"- {item}" for item in order.visual.must_not_show)
        if order.visual.must_not_show
        else "- none"
    )
    locks = (
        chr(10).join(f"- {lock}" for lock in order.visual.consistency_locks)
        if order.visual.consistency_locks
        else "- none"
    )
    prints = (
        chr(10).join(f"- {req}" for req in order.visual.print_requirements)
        if order.visual.print_requirements
        else "- high contrast; large readable labels; grayscale-safe"
    )

    return f"""Generate a clear educational illustration for print.

MODE: {order.visual.mode}

PURPOSE: {order.visual.purpose}

MUST SHOW:
{must_show_block}

MUST NOT SHOW:
{must_not_block}

LABELS REQUIRED: {', '.join(order.visual.labels_required) or 'none'}
{frame_lines}
{anchor_block}{continuity_block}

CONSISTENCY LOCKS:
{locks}

PRINT REQUIREMENTS:
{prints}

RESOURCE TYPE: {order.resource_type}
"""


__all__ = ["build_visual_prompt", "format_anchor_for_visual"]

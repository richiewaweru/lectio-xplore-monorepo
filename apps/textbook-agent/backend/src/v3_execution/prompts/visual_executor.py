from __future__ import annotations

from v3_execution.prompts.formatting import format_source_of_truth
from v3_execution.models import VisualGeneratorWorkOrder

NO_CAPTION_TEXT_CONSTRAINT = (
    "Do not render any caption, title, sentence, or explanatory text inside the image. "
    "Short labels for dimensions or parts only. The caption is rendered by the document, never inside the image."
)
CLOSED_LABEL_TEXT_CONSTRAINT = (
    "For diagram_precision, visible text is a CLOSED SET: render only the exact labels "
    "listed under LABELS REQUIRED, each exactly once. Render no other visible text: "
    "no parentheses, source/lesson text, purposes, corrections, captions, titles, "
    "numbers, or explanatory words. Corrections cannot widen this set. "
    "If LABELS REQUIRED is empty, render no visible text."
)
NO_VISIBLE_TEXT_DIAGRAM_CONSTRAINT = (
    "For diagram_precision, render NO visible text. Depict semantics with shapes, "
    "arrows, geometry, and color only; all labels are added by the deterministic compositor."
)


def format_anchor_for_visual(order: VisualGeneratorWorkOrder) -> str:
    if order.visual.uses_anchor_id:
        return format_source_of_truth(order.source_of_truth)
    return "(no anchor bindings)"


def build_visual_prompt(
    order: VisualGeneratorWorkOrder,
    previous_frame_description: str | None = None,
) -> str:
    visual_style = order.visual.visual_style or "illustration"
    anchor_block = ""
    if order.visual.uses_anchor_id:
        anchor_block = f"""
ANCHOR FACTS (preserve exactly — do not change dimensions, units, or labels):
{format_anchor_for_visual(order)}
"""

    source_block = ""
    if order.source_of_truth:
        source_block = f"""
LESSON / TEACHING SOURCE OF TRUTH (metadata only; never render this text; use these persisted facts):
{format_source_of_truth(order.source_of_truth)}
"""

    continuity_block = ""
    if previous_frame_description:
        continuity_block = f"""
VISUAL CONTINUITY:
This image is part of a series. The previous frame showed:
{previous_frame_description}
Maintain consistent style and geometry; only depict new information.
"""

    qc_block = ""
    if order.qc_correction_hint and visual_style != "diagram_precision":
        qc_block = f"""
PREVIOUS QC CORRECTION (metadata only; fix this in the image structure, never render this text):
{order.qc_correction_hint}
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
    if visual_style == "diagram_precision":
        # Provider text must stay closed to the no-text contract; any labels
        # are added only by the deterministic compositor after generation.
        prints = "- high contrast; grayscale-safe; no visible text"
    else:
        prints = (
            chr(10).join(f"- {req}" for req in order.visual.print_requirements)
            if order.visual.print_requirements
            else "- high contrast; large readable labels; grayscale-safe"
        )
    if visual_style == "diagram_precision":
        style_requirements = (
            "- clean vector-style raster diagram, not SVG\n"
            "- white or very light background with high contrast\n"
            "- simple geometry, clear arrows or callouts where useful\n"
            "- no decorative clutter, photorealism, or background scenery\n"
            "- PURPOSE, MUST SHOW, source truth, and QC corrections are semantic metadata only; never render their words\n"
            f"- {NO_VISIBLE_TEXT_DIAGRAM_CONSTRAINT}"
        )
    else:
        style_requirements = (
            "- educational raster illustration\n"
            "- visually simple enough for print\n"
            "- no decorative clutter or irrelevant background detail"
        )

    return f"""Generate a clear educational illustration for print.

MODE: {order.visual.mode}

VISUAL STYLE: {visual_style}

STYLE REQUIREMENTS:
{style_requirements}
{'' if visual_style == 'diagram_precision' else NO_CAPTION_TEXT_CONSTRAINT}

PURPOSE: {order.visual.purpose}

MUST SHOW:
{must_show_block}

MUST NOT SHOW:
{must_not_block}

{('LABELS REQUIRED: ' + ', '.join(order.visual.labels_required)) if visual_style != 'diagram_precision' else ''}
{frame_lines}
{source_block}{anchor_block}{qc_block}{continuity_block}

CONSISTENCY LOCKS:
{locks}

PRINT REQUIREMENTS:
{prints}

RESOURCE TYPE: {order.resource_type}
"""


__all__ = [
    "CLOSED_LABEL_TEXT_CONSTRAINT",
    "NO_VISIBLE_TEXT_DIAGRAM_CONSTRAINT",
    "NO_CAPTION_TEXT_CONSTRAINT",
    "build_visual_prompt",
    "format_anchor_for_visual",
]

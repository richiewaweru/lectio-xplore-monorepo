from __future__ import annotations

from pipeline.media.types import VisualFrame, VisualSlot
from pipeline.state import StyleContext

_SURFACE_TO_IMAGE_STYLE: dict[str, str] = {
    "crisp": "clean vector illustration, sharp lines",
    "soft": "gentle watercolour style, soft edges",
    "minimal": "minimalist line art, essential elements",
}

_PALETTE_TO_IMAGE_COLOURS: dict[str, str] = {
    "navy, sky, parchment": "navy blue and sky blue professional scheme",
    "sand, amber, ink": "warm sand and amber with dark ink",
    "sage, pine, cream": "sage green and pine natural palette",
    "ink, ivory, signal amber": "high-contrast dark ink with amber accents",
    "white, slate, graphite": "neutral slate and graphite tones",
}


def _translate_style_to_image_keywords(ctx: StyleContext) -> str:
    style = _SURFACE_TO_IMAGE_STYLE.get(ctx.surface_style, "clean illustration")
    colours = _PALETTE_TO_IMAGE_COLOURS.get(ctx.palette, "neutral educational colours")
    return f"{style}, {colours}, textbook quality"


def build_image_generation_prompt(
    *,
    section_title: str,
    slot: VisualSlot,
    frame: VisualFrame,
    style_context: StyleContext,
) -> str:
    visual_style = _translate_style_to_image_keywords(style_context)
    must_include = ", ".join(frame.must_include) if frame.must_include else "the core idea"
    avoid = ", ".join(frame.avoid) if frame.avoid else "text overlays"
    primary_brief = slot.content_brief or frame.generation_goal
    size_hint = ""
    if frame.target_w and frame.target_h:
        ratio = f"{frame.target_w}:{frame.target_h}"
        size_hint = f"\nTarget aspect ratio: {ratio} - optimise composition for this shape"
    sizing_hint = (
        "Simple, focused composition. Single concept. Small-format educational graphic."
        if slot.sizing == "compact"
        else "Use the available frame to show the core concept clearly."
    )

    return f"""Educational image for {section_title}

Slot type: {slot.slot_type.value}
Sizing: {slot.sizing}
Target block: {slot.block_target or "section"}
Frame label: {frame.label or "n/a"}
Pedagogical intent: {slot.pedagogical_intent}
Content brief: {primary_brief}
Caption to support: {slot.caption}
Reference style: {slot.reference_style.value}
Must include: {must_include}
Avoid: {avoid}

Visual style: {visual_style}

Requirements:
- Clear, simple composition for textbook use
- Educational illustration style
- High contrast, readable
- No text overlays
- {sizing_hint}{size_hint}"""


def build_series_step_image_prompt(
    *,
    section_title: str,
    slot: VisualSlot,
    frame: VisualFrame,
    style_context: StyleContext,
) -> str:
    return build_image_generation_prompt(
        section_title=section_title,
        slot=slot,
        frame=frame,
        style_context=style_context,
    ) + "\n- Keep framing consistent with the rest of the sequence"


def build_compare_image_prompts(
    *,
    section_title: str,
    slot: VisualSlot,
    before_frame: VisualFrame,
    after_frame: VisualFrame,
    style_context: StyleContext,
) -> tuple[str, str]:
    shared = build_image_generation_prompt(
        section_title=section_title,
        slot=slot,
        frame=before_frame,
        style_context=style_context,
    ) + (
        "\n- Use the same subject, same viewpoint, same framing, same background, and same lighting in both images"
    )
    before_prompt = f"{shared}\n- Render the BEFORE state labelled '{before_frame.label or 'Before'}'"
    after_prompt = (
        build_image_generation_prompt(
            section_title=section_title,
            slot=slot,
            frame=after_frame,
            style_context=style_context,
        )
        + "\n- Use the same subject, viewpoint, framing, background, and lighting as the before state"
        + f"\n- Render the AFTER state labelled '{after_frame.label or 'After'}'"
    )
    return before_prompt, after_prompt


def build_hook_image_prompt(
    *,
    section_title: str,
    hook_headline: str,
    hook_body: str,
    style_context: StyleContext,
) -> str:
    visual_style = _translate_style_to_image_keywords(style_context)

    return (
        f"Educational visual anchor for a lesson about {section_title}. "
        f"Hook question: {hook_headline}. "
        f"Context: {hook_body[:200]}. "
        f"Style: {visual_style}, realistic educational illustration, "
        "classroom-appropriate, grounded in a real-world scene, no text overlays."
    )

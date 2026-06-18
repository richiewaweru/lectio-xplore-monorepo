from __future__ import annotations

from pipeline.media.types import VisualFrame, VisualSlot
from pipeline.state import StyleContext

SURFACE_TO_DIAGRAM_STYLE: dict[str, str] = {
    "crisp": "clean lines, sharp edges, professional weight strokes, minimal decoration",
    "soft": "slightly rounded corners, gentle stroke weight, warm and readable",
    "minimal": "outline only, no fills, bare essentials, maximum whitespace",
}

PALETTE_TO_STROKE: dict[str, str] = {
    "navy, sky, parchment": "use navy (#1e3a5f) for primary elements, sky blue (#7eb8d4) for secondary, no fills",
    "sand, amber, ink": "use ink (#2c2416) for all strokes, amber (#d97706) for emphasis only",
    "sage, pine, cream": "use pine (#2d4a2d) for primary strokes, sage (#7a9e7a) for secondary",
    "ink, ivory, signal amber": "use high-contrast ink (#111) for all strokes, amber (#f59e0b) for alerts only",
    "white, slate, graphite": "use graphite (#4b5563) for all strokes, no fills whatsoever",
}

TYPOGRAPHY_TO_LABELS: dict[str, str] = {
    "standard": "12px labels, normal weight, standard spacing",
    "reading-support": "14px labels, slightly bolder, generous spacing between elements",
}

COMPLEXITY_TO_DETAIL: dict[str, str] = {
    "simplified": "3-4 elements max, large labels, no sub-labels",
    "standard": "up to 6 labelled elements, clear hierarchy",
    "detailed": "up to 8 elements, can include sub-labels",
}


def build_diagram_style_instruction(ctx: StyleContext) -> str:
    style = SURFACE_TO_DIAGRAM_STYLE.get(ctx.surface_style, SURFACE_TO_DIAGRAM_STYLE["crisp"])
    stroke = PALETTE_TO_STROKE.get(ctx.palette, "use dark grey (#374151) for all strokes")
    labels = TYPOGRAPHY_TO_LABELS.get(ctx.typography, TYPOGRAPHY_TO_LABELS["standard"])
    detail = COMPLEXITY_TO_DETAIL.get(ctx.diagram_complexity(), COMPLEXITY_TO_DETAIL["standard"])

    return f"""Visual style: {style}
Colour: {stroke}
Labels: {labels}
Complexity: {detail}"""


def build_diagram_system_prompt(ctx: StyleContext, *, sizing: str = "full") -> str:
    style_instruction = build_diagram_style_instruction(ctx)
    coordinate_space = "400x300" if sizing == "compact" else "600x400"
    safe_zone = "x 30-370, y 40-260." if sizing == "compact" else "x 40-560, y 50-360."
    default_element_size = "90x48" if sizing == "compact" else "120x60"
    compact_guidance = (
        "- Keep the layout compact: 2-4 elements only, one focal relationship, minimal ornament."
        if sizing == "compact"
        else "- Use the full canvas deliberately for clear spacing and label readability."
    )

    return f"""You design diagrams for educational content by outputting structured JSON specs.
The specs are rendered client-side and you do NOT generate SVG or HTML.

{style_instruction}

Diagram types:
- "process-flow": steps connected by arrows (horizontal or vertical)
- "hierarchy": parent-child tree structure
- "compare": side-by-side comparison layout
- "cycle": circular process with repeating steps
- "concept-map": vocabulary terms or concept relationships only

Diagram type selection rules:
- Use "concept-map" only for vocabulary or term-relationship content.
- Do not use "concept-map" for mathematical, spatial, or graphical content.
- If the intent involves coordinates, axes, measurement, or physical space, do not represent it as a concept-map.

Element placement:
- Use a {coordinate_space} coordinate space.
- SAFE ZONE: every edge of every element must stay inside the canvas bounds.
- Valid placement range: {safe_zone}
- Never place elements outside the safe zone.
- Default element size: {default_element_size}. Adjust for label length.
- Shapes: "rect", "circle", "diamond", "rounded-rect"
- Set emphasis=true for the most important element(s)
{compact_guidance}

Connections:
- Use from_id/to_id referencing element ids
- Styles: "solid" for primary flow, "dashed" for optional/conditional, "arrow" (default) for directed

Caption: max 60 words, plain language.
alt_text: max 80 words, describes the diagram for screen readers.

Output a JSON object with exactly these fields:
  spec (object with type, title, elements, connections, layout_hint), caption, alt_text

Output only valid JSON. No preamble, no markdown fences."""


def build_diagram_user_prompt(
    *,
    section_title: str,
    slot: VisualSlot,
    frame: VisualFrame,
) -> str:
    must_include = ", ".join(frame.must_include) if frame.must_include else "None"
    avoid = ", ".join(frame.avoid) if frame.avoid else "None"
    primary_brief = slot.content_brief or frame.generation_goal
    return f"""Section: {section_title}
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

Generate a structured diagram spec that makes the planned concept visually clear.
Keep the result aligned to the slot intent and frame scope only."""

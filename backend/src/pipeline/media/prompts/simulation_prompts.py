from __future__ import annotations

from pipeline.media.types import VisualFrame, VisualSlot

_SIMULATION_SYSTEM_PROMPT = """You build one self-contained educational HTML simulation.

Return an iframe-safe HTML document with inline CSS and inline JavaScript only.
Never use external assets, CDNs, imports, network requests, or parent-window access.
Use the minimum necessary controls for the learning goal.
Use no more than four learner controls in total.
For time-dimension concepts, include Play / Pause / Reset controls.

After the HTML, you may append:
SIMULATION_META:
type: <simulation type>
goal: <student-facing goal>
explanation: <1-2 sentence explanation>
"""


def build_simulation_prompt(*, section_title: str, slot: VisualSlot, frame: VisualFrame) -> str:
    must_include = ", ".join(frame.must_include) if frame.must_include else "core concepts"
    return (
        f"Create one self-contained HTML simulation for {section_title}. "
        f"Preferred simulation type: {slot.simulation_type or 'choose the best fit'}. "
        f"Goal: {slot.simulation_goal or slot.simulation_intent or slot.pedagogical_intent}. "
        f"Anchor block: {slot.anchor_block or 'explanation'}. "
        f"Frame goal: {frame.generation_goal}. "
        f"Must include: {must_include}. "
        "Make the interaction obvious, classroom-safe, and readable on both desktop and narrow widths. "
        "Choose the minimum necessary controls. Never exceed four controls. "
        "If the concept evolves over time, include Play / Pause / Reset. "
        "Prefer semantic buttons, labels, and accessible form controls."
    )


__all__ = ["_SIMULATION_SYSTEM_PROMPT", "build_simulation_prompt"]

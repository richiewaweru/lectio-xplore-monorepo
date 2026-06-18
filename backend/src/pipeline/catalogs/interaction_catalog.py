"""
Interaction type catalog with pedagogical guidance for LLM.

Provides a structured catalog of all supported interaction types along with
guidance on when to use each one, helping the composition planner make
informed decisions.
"""

from __future__ import annotations

from typing import TypedDict


class InteractionTypeGuide(TypedDict):
    type: str
    use_when: str
    example: str
    pedagogical_strength: str
    complexity: str
    best_subjects: list[str]


INTERACTION_CATALOG: list[InteractionTypeGuide] = [
    {
        "type": "graph_slider",
        "use_when": "Concept involves continuous relationships between variables",
        "example": "y = mx + b where learner adjusts m and b to see slope/intercept effect",
        "pedagogical_strength": "Reveals how parameters affect shape/behavior in real-time",
        "complexity": "simple",
        "best_subjects": ["mathematics", "physics", "economics", "chemistry"],
    },
    {
        "type": "equation_reveal",
        "use_when": "Concept builds through discrete steps or transformations",
        "example": "Completing the square: x^2 + 6x + 5 -> (x+3)^2 - 4 shown step-by-step",
        "pedagogical_strength": "Shows logical progression and intermediate states",
        "complexity": "simple",
        "best_subjects": ["mathematics", "chemistry", "algorithms", "physics"],
    },
    {
        "type": "timeline_scrubber",
        "use_when": "Concept involves temporal sequence or causal chain",
        "example": "Steps in mitosis, events leading to WWI",
        "pedagogical_strength": "Reveals causality and temporal relationships",
        "complexity": "simple",
        "best_subjects": ["history", "biology", "earth-science", "geography"],
    },
    {
        "type": "geometry_explorer",
        "use_when": "Concept involves spatial relationships or geometric properties",
        "example": "Triangle angle sum: drag vertices to see angles always sum to 180 degrees",
        "pedagogical_strength": "Discovers invariants through manipulation",
        "complexity": "moderate",
        "best_subjects": ["mathematics", "physics", "engineering"],
    },
    {
        "type": "probability_tree",
        "use_when": "Concept involves branching outcomes or conditional probability",
        "example": "Coin flip sequences, disease testing with Bayes' theorem",
        "pedagogical_strength": "Makes probability paths visible and countable",
        "complexity": "moderate",
        "best_subjects": ["mathematics", "statistics", "biology"],
    },
    {
        "type": "molecule_viewer",
        "use_when": "Concept involves 3D molecular or structural visualisation",
        "example": "Rotating a water molecule to see bond angles and electron clouds",
        "pedagogical_strength": "Spatial reasoning for structures that cannot be shown in 2D",
        "complexity": "moderate",
        "best_subjects": ["chemistry", "biology", "materials-science"],
    },
]

FALLBACK_CRITERIA = """Use diagram fallback when:
- Concept is inherently static (anatomical structure, map, classification)
- Manipulation would not reveal insight
- Visual needs annotation more than manipulation
- Learner needs to study unchanging relationships

Examples:
- "Plant cell structure" -> diagram (static labels)
- "Enzyme kinetics" -> interaction (manipulate concentration)
- "Map of tectonic plates" -> diagram (static spatial reference)
- "Supply and demand curves" -> interaction (shift curves with sliders)"""


def get_interaction_guidance() -> str:
    """Build formatted catalog text for insertion into LLM prompts."""
    lines = ["AVAILABLE INTERACTION TYPES:\n"]
    for item in INTERACTION_CATALOG:
        lines.append(f"**{item['type']}**")
        lines.append(f"  Use when: {item['use_when']}")
        lines.append(f"  Example: {item['example']}")
        lines.append(f"  Strength: {item['pedagogical_strength']}")
        lines.append(f"  Complexity: {item['complexity']}")
        lines.append("")
    lines.append("FALLBACK TO DIAGRAM:")
    lines.append(FALLBACK_CRITERIA)
    return "\n".join(lines)

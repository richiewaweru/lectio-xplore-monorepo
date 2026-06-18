"""
Shared context and utilities used across all prompt builders.
The shared context block is small -- 3 lines max.
It appears in every system prompt.
"""

from __future__ import annotations

from pipeline.types.generation_manifest import GenerationFieldContract


def shared_context(
    template_name: str,
    template_family: str,
    subject: str,
    grade_band: str,
    learner_fit: str,
) -> str:
    """
    A small anchor block included in every system prompt.
    Keeps every node aware of the teaching context
    without duplicating the full contract into every call.
    """
    return f"""Template: {template_name} ({template_family} family)
Subject: {subject}
Learner: {grade_band} level, {learner_fit}"""


def word_count(text: str) -> int:
    return len(text.strip().split())


_CAPACITY_RULES: dict[str, str] = {
    "hook": "hook.headline 12 words · hook.body 80 words",
    "explanation": "explanation.body 350 words · emphasis 3 items max",
    "practice": "practice.problems 2 min / 5 max · hints 3 max per problem",
    "what_next": "what_next.body 50 words max",
    "definition": "definition.formal 80 words · definition.plain 60 words",
    "definition_family": "definition_family.definitions 4 max",
    "worked_example": "worked_example.steps 6 max",
    "process": "process.steps 8 max",
    "glossary": "glossary.terms 8 max (warn at 6)",
    "insight_strip": "insight_strip.cells 2\u20133",
    "comparison_grid": "comparison_grid.columns 2\u20134 · rows 6 max",
    "timeline": "timeline.events 8 max",
    "pitfall": "pitfall.misconception 20 words · correction 80 words",
    "diagram": "diagram.caption 60 words",
    "quiz": "quiz.options 3\u20134",
    "reflection": "reflection.prompt 40 words max",
    "prerequisites": "prerequisites.items 4 max",
    "interview": "interview.prompt 35 words max",
}


def _format_capacity(capacity: dict) -> str:
    if not capacity:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(capacity.items()))


def capacity_reminder_for_manifest_fields(
    active_fields: list[GenerationFieldContract],
) -> str:
    """Capacity reminders from Lectio component registry values."""
    if not active_fields:
        return ""
    lines = [
        f"- {field.field_name}: {_format_capacity(field.capacity)}"
        for field in active_fields
        if field.capacity
    ]
    if not lines:
        return ""
    return "Capacity rules (contract-derived):\n" + "\n".join(lines)


def capacity_reminder_for_fields(active_fields: list[str]) -> str:
    """
    Emit capacity rules only for fields this template actually uses.
    Pass the union of required_fields + optional_fields.
    """
    rules = [
        rule for field, rule in _CAPACITY_RULES.items()
        if field in active_fields
    ]
    if not rules:
        return ""
    lines = "\n".join(f"- {r}" for r in rules)
    return f"Capacity rules (hard limits):\n{lines}"


def capacity_reminder() -> str:
    """
    All capacity rules (backward compat for prompts that don't know their fields).
    Prefer capacity_reminder_for_fields() when active fields are known.
    """
    return capacity_reminder_for_fields(list(_CAPACITY_RULES.keys()))

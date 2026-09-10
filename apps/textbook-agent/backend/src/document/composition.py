"""Compact composition-plan decision schemas for Print/Learn document realizers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document.models import DOCUMENT_PRIMITIVE_KINDS

DocumentPrimitiveKind = Literal[
    "paragraph", "heading", "list", "figure", "table", "callout"
]

PrintTaskObject = Literal["worked-example", "questions", "choices"]

LearnRetainedInteraction = Literal[
    "choice",
    "multi-select",
    "fill-blank",
    "classify",
    "match-pairs",
    "sequence",
    "numeric",
    "short-response",
]

PRINT_TASK_OBJECTS: frozenset[str] = frozenset({"worked-example", "questions", "choices"})
LEARN_RETAINED_INTERACTIONS: frozenset[str] = frozenset(
    {
        "choice",
        "multi-select",
        "fill-blank",
        "classify",
        "match-pairs",
        "sequence",
        "numeric",
        "short-response",
    }
)

# Print-only layout/response surfaces that must never appear on Learn plans.
PRINT_ONLY_LAYOUT_OBJECTS: frozenset[str] = frozenset(
    {"ruled_lines", "page_break", "answer-key", "working-space"}
)

# Retired ordinary Learn component ids — never selectable by document realizers.
LEGACY_LEARN_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "ExplanationBlock",
        "explanation-block",
        "definition-card",
        "section-header",
        "hook-hero",
        "key-fact",
        "callout-block",
        "process-steps",
        "worked-example-card",
        "summary-block",
        "timeline-block",
        "diagram-compare",
        "quiz-check",
        "fill-in-blank",
    }
)

PASSIVE_LEARNER_ACTIONS: frozenset[str] = frozenset(
    {"compare-without-response", "read-explanation"}
)

ACTION_TO_LEARN_INTERACTION: dict[str, LearnRetainedInteraction] = {
    "select-one": "choice",
    "select-many": "multi-select",
    "complete-missing-values": "fill-blank",
    "classify-items": "classify",
    "match-pairs": "match-pairs",
    "order-items": "sequence",
    "enter-number": "numeric",
    "enter-text": "short-response",
    # Gate wording alias
    "reconstruct-order": "sequence",
}

ACTION_TO_PRINT_TASK: dict[str, PrintTaskObject] = {
    "select-one": "choices",
    "select-many": "choices",
    "complete-missing-values": "questions",
    "classify-items": "questions",
    "match-pairs": "questions",
    "order-items": "questions",
    "enter-number": "questions",
    "enter-text": "questions",
    "reconstruct-order": "questions",
}

VISUAL_INTENTS: frozenset[str] = frozenset(
    {
        "illustrate",
        "show-structure",
        "show-process",
        "visualize",
        "diagram",
        "show",
    }
)
COMPARE_INTENTS: frozenset[str] = frozenset({"compare", "contrast", "compare-contrast"})
DEFINE_INTENTS: frozenset[str] = frozenset(
    {"define", "explain", "clarify", "introduce", "summarize"}
)
LIST_INTENTS: frozenset[str] = frozenset(
    {"list", "enumerate", "sequence", "steps", "outline"}
)
WORKED_EXAMPLE_INTENTS: frozenset[str] = frozenset(
    {"demonstrate", "model", "worked-example", "walkthrough"}
)


class CompositionDecision(BaseModel):
    """One ordered realization choice for a teaching block."""

    model_config = ConfigDict(extra="forbid")

    teaching_block_id: str = Field(min_length=1)
    kind: str = Field(
        min_length=1,
        description="Document primitive kind, Print task object, or Learn interaction id.",
    )
    lane: Literal["document", "print_task", "learn_interaction"]
    reason: str = Field(min_length=1)


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["print", "learn"]
    teaching_plan_id: str | None = None
    teaching_plan_revision: int | None = None
    decisions: list[CompositionDecision] = Field(default_factory=list)


__all__ = [
    "ACTION_TO_LEARN_INTERACTION",
    "ACTION_TO_PRINT_TASK",
    "COMPARE_INTENTS",
    "CompositionDecision",
    "CompositionPlan",
    "DEFINE_INTENTS",
    "DOCUMENT_PRIMITIVE_KINDS",
    "DocumentPrimitiveKind",
    "LEGACY_LEARN_COMPONENT_IDS",
    "LEARN_RETAINED_INTERACTIONS",
    "LIST_INTENTS",
    "LearnRetainedInteraction",
    "PASSIVE_LEARNER_ACTIONS",
    "PRINT_ONLY_LAYOUT_OBJECTS",
    "PRINT_TASK_OBJECTS",
    "PrintTaskObject",
    "VISUAL_INTENTS",
    "WORKED_EXAMPLE_INTENTS",
]

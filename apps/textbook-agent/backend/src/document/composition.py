"""Compact composition-plan decision schemas for Print/Learn document realizers.

Path-specific task/interaction maps live in print/ and learn/.
This module owns only shared ordinary-content composition contracts and
intent cues used by generic document heuristics / the LLM composer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document.models import DOCUMENT_PRIMITIVE_KINDS

DocumentPrimitiveKind = Literal[
    "paragraph", "heading", "list", "figure", "table", "callout"
]

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


class CompositionDecision(BaseModel):
    """One ordered realization choice for a teaching block.

    ``kind`` for lane=document must be one of the six ordinary primitives.
    Path-specific lanes (print_task / learn_interaction) are validated by
    the owning realizer — not by shared document maps.
    """

    model_config = ConfigDict(extra="forbid")

    teaching_block_id: str = Field(min_length=1)
    kind: str = Field(
        min_length=1,
        description="Document primitive kind, Print task object, or Learn interaction id.",
    )
    lane: Literal["document", "print_task", "learn_interaction"]
    reason: str = Field(min_length=1)
    section_id: str | None = Field(
        default=None,
        description="Teaching Plan section / slot id for local regeneration.",
    )
    role: str | None = Field(
        default=None,
        description="Optional pedagogical role for this node within the block (e.g. orient, explain).",
    )


class CompositionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["print", "learn"]
    teaching_plan_id: str | None = None
    teaching_plan_revision: int | None = None
    decisions: list[CompositionDecision] = Field(default_factory=list)


__all__ = [
    "COMPARE_INTENTS",
    "CompositionDecision",
    "CompositionPlan",
    "DEFINE_INTENTS",
    "DOCUMENT_PRIMITIVE_KINDS",
    "DocumentPrimitiveKind",
    "LIST_INTENTS",
    "VISUAL_INTENTS",
]

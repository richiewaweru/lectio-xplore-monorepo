"""Retained vs deleted Learn interaction kinds (Phase G).

Ordinary teaching content is not listed here — document primitives own that lane.
This registry is the admission boundary for true learner behaviors only.
"""

from __future__ import annotations

# Strict interaction kinds with runtime/evaluation contracts.
RETAINED_INTERACTIONS: frozenset[str] = frozenset(
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

# Asset-heavy / unsupported behaviors — never selectable in production policy.
DELETED_INTERACTIONS: frozenset[str] = frozenset(
    {
        "image-hotspot",
        "drag-label",
        "image-choice",
        "image-block",
        "video-embed",
    }
)

# Ordinary Learn component ids retired in favor of shared document primitives.
# Listed here so native policy / realizers can deny them.
RETIRED_ORDINARY_CONTENT_IDS: frozenset[str] = frozenset(
    {
        "ExplanationBlock",
        "section-header",
        "hook-hero",
        "explanation-block",
        "definition-card",
        "key-fact",
        "callout-block",
        "process-steps",
        "worked-example-card",
        "summary-block",
        "timeline-block",
        "diagram-compare",
        "quiz-check",
        "fill-in-blank",
        "diagram-block",
    }
)

assert RETAINED_INTERACTIONS.isdisjoint(DELETED_INTERACTIONS)


__all__ = [
    "DELETED_INTERACTIONS",
    "RETAINED_INTERACTIONS",
    "RETIRED_ORDINARY_CONTENT_IDS",
]

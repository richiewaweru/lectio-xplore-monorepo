"""Shared heuristics for choosing ordinary document primitives from teaching blocks."""

from __future__ import annotations

from curriculum.teaching_plan.models import TeachingPlanBlock
from document.composition import (
    COMPARE_INTENTS,
    DEFINE_INTENTS,
    LIST_INTENTS,
    VISUAL_INTENTS,
    DocumentPrimitiveKind,
)


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("_", "-").replace("/", " ").split())


def _warning_like(brief: str, evidence: str) -> bool:
    blob = f"{brief} {evidence}".lower()
    cues = (
        "warning",
        "caution",
        "pitfall",
        "misconception",
        "watch out",
        "common error",
        "trap",
        "important:",
    )
    return any(cue in blob for cue in cues)


def _list_worthy(brief: str, intent: str) -> bool:
    if intent in LIST_INTENTS:
        return True
    blob = brief.lower()
    cues = (
        "list",
        "steps",
        "bullet",
        "first,",
        "second,",
        "then ",
        "enumerate",
        "several",
        "ordered",
    )
    return any(cue in blob for cue in cues)


def choose_document_primitive(
    block: TeachingPlanBlock,
) -> tuple[DocumentPrimitiveKind, str]:
    """Deterministic ordinary-content form for a teaching block."""
    intent = _norm(block.intent)
    brief = block.brief or ""

    if intent in VISUAL_INTENTS or any(
        token in intent for token in ("illustrat", "diagram", "visual", "show-structure")
    ):
        return "figure", f"visual intent {block.intent!r} → figure"

    if intent in COMPARE_INTENTS or "compar" in intent or "contrast" in intent:
        return "table", f"compare intent {block.intent!r} → table"

    if _list_worthy(brief, intent):
        return "list", f"list-worthy brief/intent {block.intent!r} → list"

    if intent in DEFINE_INTENTS or any(
        token in intent for token in ("defin", "explain", "clarif", "introduc", "summar")
    ):
        if _warning_like(brief, block.evidence or ""):
            return "callout", f"define/explain with warning cues → callout"
        return "paragraph", f"define/explain intent {block.intent!r} → paragraph"

    if _warning_like(brief, block.evidence or ""):
        return "callout", "warning-like brief → callout"

    if intent in {"title", "heading", "section-title"}:
        return "heading", f"heading intent {block.intent!r} → heading"

    return "paragraph", f"default prose for intent {block.intent!r} → paragraph"


__all__ = ["choose_document_primitive"]

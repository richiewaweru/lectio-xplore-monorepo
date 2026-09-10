"""Deterministic document / interaction node writers for LearnDocument v2."""

from __future__ import annotations

import re
import uuid
from typing import Any, Mapping

from document.models import DOCUMENT_PRIMITIVE_KINDS
from learn.contracts.lesson_document import RETAINED_INTERACTION_TYPES

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip()) if p.strip()]
    if parts:
        return parts
    bullets = [p.strip(" -•\t") for p in text.splitlines() if p.strip()]
    return bullets or ([text.strip()] if text.strip() else ["Content pending."])


def _brief_text(brief: str | Mapping[str, Any] | None) -> str:
    if brief is None:
        return ""
    if isinstance(brief, Mapping):
        for key in ("brief", "text", "body", "prompt"):
            value = brief.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return str(brief)
    return str(brief).strip()


_MINIMAL_INTERACTION_CONFIGS: dict[str, dict[str, Any]] = {
    "choice": {
        "options": [
            {"id": "a", "text": "Option A"},
            {"id": "b", "text": "Option B"},
        ],
        "correct_option_id": "a",
    },
    "multi-select": {
        "options": [
            {"id": "a", "text": "Option A"},
            {"id": "b", "text": "Option B"},
        ],
        "correct_option_ids": ["a"],
    },
    "fill-blank": {
        "answers": ["answer"],
        "blank_ids": ["blank-1"],
        "case_sensitive": False,
    },
    "classify": {
        "categories": [
            {"id": "cat-a", "label": "Category A"},
            {"id": "cat-b", "label": "Category B"},
        ],
        "pairs": [],
    },
    "match-pairs": {"pairs": [{"left": "left", "right": "right"}]},
    "sequence": {
        "items": [
            {"id": "step-1", "label": "First"},
            {"id": "step-2", "label": "Second"},
        ],
        "order": ["step-1", "step-2"],
    },
    "numeric": {"value": 0, "tolerance": 0},
    "short-response": {
        "evaluation": "teacher-review",
        "review_guidance": "Review the learner response.",
    },
}


def write_document_node(
    *,
    form: str,
    brief: str | Mapping[str, Any] | None,
    teaching_block_id: str | None = None,
    node_id: str | None = None,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one document-primitive node payload from a composition decision + brief."""
    kind = str(form or (decision or {}).get("form") or (decision or {}).get("kind") or "").strip()
    if kind not in DOCUMENT_PRIMITIVE_KINDS:
        raise ValueError(f"unsupported document form {kind!r}")
    text = _brief_text(brief) or "Content pending."
    nid = node_id or _new_id("node")
    block_id = teaching_block_id
    if block_id is None and decision is not None:
        raw = decision.get("teaching_block_id")
        block_id = str(raw) if raw else None

    if kind == "paragraph":
        return {
            "id": nid,
            "kind": "paragraph",
            "text": text,
            "teaching_block_id": block_id,
        }
    if kind == "heading":
        heading = text.split(".")[0].strip() or text
        return {
            "id": nid,
            "kind": "heading",
            "text": heading[:120],
            "level": 2,
            "teaching_block_id": block_id,
        }
    if kind == "list":
        return {
            "id": nid,
            "kind": "list",
            "ordered": False,
            "items": _split_sentences(text),
            "teaching_block_id": block_id,
        }
    if kind == "figure":
        return {
            "id": nid,
            "kind": "figure",
            "caption": text,
            "alt": text[:160],
            "teaching_block_id": block_id,
        }
    if kind == "table":
        rows_src = _split_sentences(text)
        headers = ["Item", "Detail"]
        rows = [[f"Row {i + 1}", row] for i, row in enumerate(rows_src[:4])] or [["—", text]]
        return {
            "id": nid,
            "kind": "table",
            "headers": headers,
            "rows": rows,
            "caption": text[:120],
            "teaching_block_id": block_id,
        }
    # callout
    return {
        "id": nid,
        "kind": "callout",
        "tone": "note",
        "title": "",
        "body": text,
        "teaching_block_id": block_id,
    }


def write_interaction_node(
    *,
    interaction_type: str,
    brief: str | Mapping[str, Any] | None = None,
    teaching_block_id: str | None = None,
    node_id: str | None = None,
    prompt: str | None = None,
    decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Stub interaction writer — minimal valid config shells for retained types."""
    kind = str(
        interaction_type
        or (decision or {}).get("interaction_type")
        or (decision or {}).get("interaction_id")
        or ""
    ).strip()
    if kind not in RETAINED_INTERACTION_TYPES:
        raise ValueError(f"unsupported interaction type {kind!r}")
    text = prompt if prompt is not None else _brief_text(brief)
    if not text:
        text = f"Respond using {kind}."
    block_id = teaching_block_id
    if block_id is None and decision is not None:
        raw = decision.get("teaching_block_id")
        block_id = str(raw) if raw else None
    return {
        "id": node_id or _new_id("ix"),
        "kind": "interaction",
        "interaction_type": kind,
        "teaching_block_id": block_id,
        "prompt": text,
        "config": dict(_MINIMAL_INTERACTION_CONFIGS[kind]),
        "feedback": None,
    }


__all__ = ["write_document_node", "write_interaction_node"]

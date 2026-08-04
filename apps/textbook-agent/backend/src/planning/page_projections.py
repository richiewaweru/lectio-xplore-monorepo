"""v2 projections over ordered page blocks (no legacy component field reads)."""

from __future__ import annotations

from typing import Any


def project_blocks_by_intent(document: dict[str, Any], intents: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section in document.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("intent") in intents:
                out.append(
                    {
                        "section_id": section.get("id"),
                        "block_id": block.get("id"),
                        "intent": block.get("intent"),
                        "object": block.get("object"),
                        "position": block.get("position"),
                    }
                )
    return out


def project_teacher_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Teacher projection: all blocks in document order."""
    out: list[dict[str, Any]] = []
    for section in document.get("sections", []):
        for block in section.get("blocks", []):
            out.append(block)
    return out


def project_student_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Student projection: hide answer-key objects only."""
    return [
        block
        for block in project_teacher_blocks(document)
        if block.get("object") != "answer-key"
    ]


def qc_committed_document(document: dict[str, Any]) -> list[str]:
    from contracts.lectio_page import validate_document

    return validate_document(document)

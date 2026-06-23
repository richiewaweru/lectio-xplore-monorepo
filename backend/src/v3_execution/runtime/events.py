from __future__ import annotations

import json
from typing import Any

GENERATION_STARTED = "generation_started"
WORK_ORDERS_COMPILED = "work_orders_compiled"
SECTION_WRITING_STARTED = "section_writing_started"
SECTION_WRITER_FAILED = "section_writer_failed"
COMPONENT_READY = "component_ready"
QUESTIONS_STARTED = "questions_started"
QUESTION_READY = "question_ready"
VISUAL_GENERATION_STARTED = "visual_generation_started"
VISUAL_READY = "visual_ready"
VISUAL_FAILED = "visual_failed"
ANSWER_KEY_STARTED = "answer_key_started"
ANSWER_KEY_READY = "answer_key_ready"
ASSEMBLY_STARTED = "assembly_started"
DRAFT_PACK_READY = "draft_pack_ready"
FINAL_PACK_READY = "final_pack_ready"
DRAFT_STATUS_UPDATED = "draft_status_updated"
COMPONENT_PATCHED = "component_patched"
GENERATION_COMPLETE = "generation_complete"
GENERATION_WARNING = "generation_warning"

# Proposal 3 - coherence review / repair streaming
COHERENCE_REVIEW_STARTED = "coherence_review_started"
DETERMINISTIC_REVIEW_STARTED = "deterministic_review_started"
DETERMINISTIC_REVIEW_COMPLETE = "deterministic_review_complete"
COHERENCE_REPORT_READY = "coherence_report_ready"
RESOURCE_FINALISED = "resource_finalised"


def format_sse_payload(event_type: str, payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.setdefault("type", event_type)
    return f"event: {event_type}\ndata: {json.dumps(body, default=str)}\n\n"


__all__ = [
    "ANSWER_KEY_READY",
    "ANSWER_KEY_STARTED",
    "ASSEMBLY_STARTED",
    "COHERENCE_REPORT_READY",
    "COHERENCE_REVIEW_STARTED",
    "COMPONENT_PATCHED",
    "COMPONENT_READY",
    "DETERMINISTIC_REVIEW_COMPLETE",
    "DETERMINISTIC_REVIEW_STARTED",
    "DRAFT_PACK_READY",
    "DRAFT_STATUS_UPDATED",
    "FINAL_PACK_READY",
    "GENERATION_COMPLETE",
    "GENERATION_STARTED",
    "GENERATION_WARNING",
    "QUESTION_READY",
    "QUESTIONS_STARTED",
    "RESOURCE_FINALISED",
    "SECTION_WRITING_STARTED",
    "SECTION_WRITER_FAILED",
    "VISUAL_GENERATION_STARTED",
    "VISUAL_FAILED",
    "VISUAL_READY",
    "WORK_ORDERS_COMPILED",
    "format_sse_payload",
]

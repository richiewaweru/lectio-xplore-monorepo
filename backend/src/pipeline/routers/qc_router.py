"""
pipeline.routers.qc_router

Routes post-section execution toward the narrowest valid retry:
    - media issues -> retry_media_frame
    - single text-field issues -> retry_field
    - other retryable issues -> process_section
"""

from __future__ import annotations

import json

import core.events as core_events  # noqa: F401
from langgraph.graph import END
from langgraph.types import Send

from pipeline.events import SectionRetryQueuedEvent
from pipeline.state import TextbookPipelineState
from pipeline.runtime_diagnostics import publish_runtime_event

_TEXT_FIELDS = {
    "hook",
    "explanation",
    "practice",
    "callout",
    "summary",
    "student_textbox",
    "short_answer",
    "fill_in_blank",
    "worked_example",
    "definition",
    "key_fact",
    "pitfall",
    "glossary",
    "what_next",
    "divider",
}


def _schema_failures_for_section(
    state: TextbookPipelineState,
    section_id: str,
) -> list[dict]:
    for error in reversed(state.errors):
        if error.node != "schema_validator" or error.section_id != section_id:
            continue
        try:
            payload = json.loads(error.message)
        except json.JSONDecodeError:
            return []
        failures = payload.get("failures", [])
        if isinstance(failures, list):
            return [failure for failure in failures if isinstance(failure, dict)]
        return []
    return []


def _schema_single_retry_field(failures: list[dict]) -> str | None:
    fields: set[str] = set()
    for failure in failures:
        field = str(failure.get("field", "")).strip()
        if not field or field == "<root>":
            continue
        root_field = field.split(".", 1)[0]
        fields.add(root_field)
    if len(fields) != 1:
        return None
    only_field = next(iter(fields))
    return only_field if only_field in _TEXT_FIELDS else None


def _blocking_issues_for_section(
    state: TextbookPipelineState,
    section_id: str,
) -> list[dict]:
    pending = state.pending_rerender_for(section_id)
    if pending is not None:
        return [
            {
                "severity": "blocking",
                "block": pending.block_type,
                "message": pending.reason,
            }
        ]

    report = state.qc_reports.get(section_id)
    if report is None:
        return []
    return [
        issue
        for issue in report.issues
        if issue.get("severity") == "blocking"
    ]


def _is_single_field_retry(blocking_issues: list[dict]) -> bool:
    blocks = {issue.get("block", "") for issue in blocking_issues}
    return len(blocks) == 1 and blocks <= _TEXT_FIELDS


def _publish_retry_queued(
    state: TextbookPipelineState,
    *,
    section_id: str,
    block_type: str,
    reason: str,
) -> None:
    generation_id = state.request.generation_id or ""
    publish_runtime_event(
        generation_id,
        SectionRetryQueuedEvent(
            generation_id=generation_id,
            section_id=section_id,
            reason=reason,
            block_type=block_type,
            next_attempt=state.rerender_count.get(section_id, 0) + 2,
            max_attempts=state.max_rerenders + 1,
        ),
    )


def route_after_qc(state: TextbookPipelineState | dict) -> list[Send] | str:
    state = TextbookPipelineState.parse(state)

    if any(not error.recoverable for error in state.errors):
        return END
    return END

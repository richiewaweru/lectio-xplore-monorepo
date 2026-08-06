"""Project native whole-lesson progress into chunked status payloads."""

from __future__ import annotations

from typing import Any, Mapping

from planning.whole_lesson.native_routing import generation_is_native_whole_lesson
from planning.whole_lesson.states import DEFAULT_VARIANT_ID, NATIVE_STATUSES, execution_key


def _page_state(state: Mapping[str, Any]) -> dict[str, Any]:
    raw = state.get("page_document_v2")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _native_next_action(stage: str) -> str | None:
    if stage == "awaiting_teaching_approval":
        return "approve_teaching"
    if stage in {
        "queued",
        "planning_forms",
        "writing_sections",
        "writing_blocks",
        "assembling",
    }:
        return "wait"
    if stage == "failed_recoverable":
        return "retry_native"
    if stage == "failed_terminal":
        return "inspect_error"
    if stage == "ready":
        return "done"
    if stage == "awaiting_visuals":
        return "wait_visuals"
    if stage == "rejected_by_teacher":
        return "none"
    return None


def _structured_error(
    page: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any] | None:
    execution = page.get("execution") if isinstance(page.get("execution"), Mapping) else {}
    last_error = execution.get("last_error") if isinstance(execution, Mapping) else None
    if not isinstance(last_error, Mapping):
        block_execution = page.get("block_execution")
        if isinstance(block_execution, Mapping):
            for outcome in block_execution.values():
                if not isinstance(outcome, Mapping):
                    continue
                status = str(outcome.get("status") or "")
                if status in {"failed_recoverable", "failed_terminal", "failed"}:
                    err = outcome.get("error")
                    if isinstance(err, Mapping):
                        last_error = err
                        break
    if not isinstance(last_error, Mapping):
        if stage in {"failed_recoverable", "failed_terminal"}:
            return {
                "scope": "generation",
                "code": "NATIVE_FAILURE",
                "message": "Native whole-lesson execution failed",
                "retryable": stage == "failed_recoverable",
            }
        return None

    message = str(last_error.get("message") or "").strip() or "Native whole-lesson failure"
    detail: dict[str, Any] = {
        "scope": str(last_error.get("scope") or ("block" if last_error.get("block_id") else "generation")),
        "code": str(last_error.get("code") or "NATIVE_FAILURE"),
        "message": message,
        "retryable": bool(last_error.get("retryable")),
    }
    for key in ("section_id", "block_id", "validation_errors", "stage", "type"):
        if key in last_error and last_error[key] is not None:
            detail[key] = last_error[key]
    return detail


def project_native_status(
    generation_id: str,
    state: Mapping[str, Any],
    document_json: Any = None,
    *,
    generation_status: str | None = None,
) -> dict[str, Any] | None:
    """Return native status field overrides, or None when not native."""
    if not generation_is_native_whole_lesson(state):
        stage = str(generation_status or state.get("stage") or "")
        if stage not in NATIVE_STATUSES:
            return None

    page = _page_state(state)
    stage = str(
        generation_status
        or state.get("stage")
        or (page.get("execution") or {}).get("stage")
        or ""
    )
    form_plan = page.get("form_plan") if isinstance(page.get("form_plan"), Mapping) else {}
    sections = form_plan.get("sections") if isinstance(form_plan, Mapping) else []
    if not isinstance(sections, list):
        sections = []

    block_execution = page.get("block_execution")
    if not isinstance(block_execution, Mapping):
        block_execution = {}

    sections_total = len(sections)
    blocks_total = 0
    blocks_ready = 0
    blocks_failed = 0
    sections_ready = 0
    sections_failed = 0
    failed_section_ids: list[str] = []
    failed_block_ids: list[str] = []

    for section in sections:
        if not isinstance(section, Mapping):
            continue
        slot_id = str(section.get("slot_id") or "")
        blocks = section.get("blocks") if isinstance(section.get("blocks"), list) else []
        section_ready = True
        section_failed = False
        section_has_blocks = False
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            section_has_blocks = True
            blocks_total += 1
            block_id = str(block.get("id") or "")
            key = execution_key(slot_id, block_id, DEFAULT_VARIANT_ID)
            outcome = block_execution.get(key)
            if not isinstance(outcome, Mapping):
                section_ready = False
                continue
            status = str(outcome.get("status") or "")
            if status in {"ready", "visual_pending"}:
                blocks_ready += 1
            elif status in {"failed", "failed_recoverable", "failed_terminal"}:
                blocks_failed += 1
                section_failed = True
                section_ready = False
                if block_id and block_id not in failed_block_ids:
                    failed_block_ids.append(block_id)
            else:
                section_ready = False
        if section_has_blocks and section_ready:
            sections_ready += 1
        if section_failed:
            sections_failed += 1
            if slot_id and slot_id not in failed_section_ids:
                failed_section_ids.append(slot_id)

    document_exists = isinstance(document_json, Mapping) and bool(document_json)
    document_version: int | None = None
    if document_exists:
        try:
            document_version = int(document_json.get("document_version") or 2)
        except (TypeError, ValueError):
            document_version = 2
    elif page:
        document_version = 2

    error_detail = _structured_error(page, stage=stage)
    if stage in {"failed_recoverable", "failed_terminal"} and error_detail is None:
        error_detail = {
            "scope": "generation",
            "code": "NATIVE_FAILURE",
            "message": "Native whole-lesson execution failed",
            "retryable": stage == "failed_recoverable",
        }

    error_message: str | None = None
    if isinstance(error_detail, Mapping):
        error_message = str(error_detail.get("message") or "") or None
    elif isinstance(state.get("error"), str):
        error_message = state.get("error")

    return {
        "generation_id": generation_id,
        "stage": stage or str(state.get("stage") or "unknown"),
        "document_version": document_version,
        "document_exists": document_exists,
        "sections_total": sections_total,
        "sections_ready": sections_ready,
        "sections_failed": sections_failed,
        "blocks_total": blocks_total,
        "blocks_ready": blocks_ready,
        "blocks_failed": blocks_failed,
        "failed_section_ids": failed_section_ids,
        "failed_block_ids": failed_block_ids,
        "failed_sections": failed_section_ids,
        "next_action": _native_next_action(stage),
        "error": error_message,
        "error_detail": error_detail,
        "error_type": (
            str(error_detail.get("code"))
            if isinstance(error_detail, Mapping) and error_detail.get("code")
            else (state.get("error_type") if isinstance(state.get("error_type"), str) else None)
        ),
        "execution_started": stage
        in {
            "queued",
            "planning_forms",
            "writing_sections",
            "writing_blocks",
            "assembling",
            "awaiting_visuals",
            "ready",
            "failed_recoverable",
            "failed_terminal",
        },
    }

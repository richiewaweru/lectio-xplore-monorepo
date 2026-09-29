"""Single projection of generation-Run state onto ``native_realizations`` (Option D, 4A).

``native_realizations`` is a product record (what the teacher asked for); its
``status`` is a *projection* of the shared-document Run and the realization's
own learn/print Run.  ``project_realization_status`` is the only function that
writes that status from run state.  Stale marking (``mark_stale_*``) and the
retry/regenerate revision bump remain product decisions and are not job state.

| shared doc Run        | realization Run    | status                |
|-----------------------|--------------------|-----------------------|
| queued / running      | none               | queued                |
| failed_recoverable +  | none               | needs_shared_review   |
|   document review     |                    |                       |
| failed_* / cancelled  | none               | failed_recoverable    |
| ready                 | queued / running   | queued / running      |
| ready                 | ready              | ready                 |
| ready                 | failed_recoverable | failed_recoverable    |
| ready                 | failed_terminal /  | failed_terminal       |
|                       | cancelled          |                       |
"""

from __future__ import annotations

from typing import Any

from core.database.models import NativeRealizationModel
from document.shared_lesson.realization_source import RealizationSourceResult
from infra.database.models import GenerationRunModel
from infra.generation_runtime import active_work_items

LEGACY_SUMMARY = "Created before the job update — regenerate this output."

# Statuses a realization without a Run can legitimately hold under the new
# worker (queued awaiting the document, document review, product markers).
_NO_RUN_STATUSES = frozenset(
    {"queued", "ready", "published", "completed", "stale", "read_only", "needs_shared_review"}
)
_NON_PROJECTED_STATUSES = frozenset({"stale", "read_only"})
# A no-Run failure written by the projection itself (document failed/stale).
_DOC_PROJECTED_FAILURE_STATES = frozenset({"failed", "stale"})
_FAILED_STATUSES = frozenset({"failed_recoverable", "failed_terminal", "failed"})


def is_legacy_realization(row: NativeRealizationModel) -> bool:
    """True for a mid-flight or failed row created by the retired per-path workers."""
    if getattr(row, "generation_run_id", None):
        return False
    status = str(row.status or "")
    if status in _NO_RUN_STATUSES:
        return False
    if (
        status in {"failed_recoverable", "failed"}
        and str(row.shared_document_state or "") in _DOC_PROJECTED_FAILURE_STATES
    ):
        return False
    return True


def effective_status(row: NativeRealizationModel) -> str:
    """The status the API exposes (legacy rows are projected terminal)."""
    if is_legacy_realization(row):
        return "failed_terminal"
    status = str(row.status or "")
    return "failed_recoverable" if status == "failed" else status


def recovery_action_for(row: NativeRealizationModel) -> str | None:
    """Closed recovery vocabulary: ``retry / review / regenerate / none``."""
    if is_legacy_realization(row):
        return "regenerate"
    status = str(row.status or "")
    if status == "needs_shared_review":
        return "review"
    if status in {"failed_recoverable", "failed"}:
        return "retry"
    if status == "failed_terminal":
        return "regenerate"
    return None


def _run_failure_summary(run: GenerationRunModel) -> str:
    code = run.error_code
    summary = run.error_summary
    if not (code or summary):
        for item in active_work_items(tuple(run.work_items or ())):
            if item.error_code or item.error_summary:
                code, summary = item.error_code, item.error_summary
                break
    code = code or "REALIZATION_RUN_FAILED"
    summary = summary or "The output job failed."
    return f"{code}: {summary}"[:500]


def _apply(
    row: NativeRealizationModel,
    *,
    status: str,
    error_summary: str | None,
    shared_document_state: str | None = None,
) -> None:
    if row.status != status:
        row.status = status
    if row.error_summary != error_summary:
        row.error_summary = error_summary
    if shared_document_state is not None and row.shared_document_state != shared_document_state:
        row.shared_document_state = shared_document_state


def project_realization_status(
    row: NativeRealizationModel,
    *,
    run: GenerationRunModel | None = None,
    doc_source: RealizationSourceResult | None = None,
) -> str:
    """Write ``row.status`` from run state (see module table); returns the status.

    ``run`` is the realization's own learn/print Run (with ``work_items``
    loaded); ``doc_source`` is the classified shared-document source and is
    consulted only while no realization Run exists.  Rows the product marked
    ``stale`` / ``read_only`` are never re-projected.  Does not flush/commit.
    """
    current = str(row.status or "")
    if current in _NON_PROJECTED_STATUSES:
        return current

    if run is not None:
        status = str(run.status)
        if status == "ready":
            _apply(row, status="ready", error_summary=None, shared_document_state="ready")
        elif status in {"queued", "running"}:
            _apply(row, status=status, error_summary=None)
        elif status == "awaiting_review":
            _apply(row, status="running", error_summary=None)
        elif status == "failed_recoverable":
            _apply(
                row,
                status="failed_recoverable",
                error_summary=_run_failure_summary(run),
            )
        else:  # failed_terminal / cancelled
            _apply(
                row,
                status="failed_terminal",
                error_summary=_run_failure_summary(run),
            )
        return str(row.status)

    if doc_source is None:
        return current
    state = doc_source.state
    if state == "pending":
        pending = doc_source.pending
        if pending is not None and pending.run_id:
            row.shared_document_run_id = pending.run_id
        _apply(row, status="queued", error_summary=None, shared_document_state="pending")
    elif state == "needs_review":
        needs_review = doc_source.needs_review
        assert needs_review is not None
        row.shared_document_run_id = needs_review.run_id
        _apply(
            row,
            status="needs_shared_review",
            error_summary=None,
            shared_document_state="needs_review",
        )
    elif state == "stale":
        stale = doc_source.stale
        assert stale is not None
        row.shared_document_run_id = stale.run_id
        _apply(
            row,
            status="failed_recoverable",
            error_summary=f"SHARED_DOCUMENT_STALE: {stale.reason}"[:500],
            shared_document_state="stale",
        )
    elif state == "failed":
        failed = doc_source.failed
        assert failed is not None
        if failed.run_id:
            row.shared_document_run_id = failed.run_id
        code = failed.error_code or "SHARED_DOCUMENT_FAILED"
        summary = failed.error_summary or "SharedLessonDocument run failed."
        _apply(
            row,
            status="failed_recoverable",
            error_summary=f"{code}: {summary}"[:500],
            shared_document_state="failed",
        )
    # state == "ready": the worker admits the Run; nothing to project yet.
    return str(row.status)


def identity_extras(row: NativeRealizationModel) -> dict[str, Any]:
    """Additive DTO fields shared by every realization read."""
    return {
        "run_id": getattr(row, "generation_run_id", None),
        "recovery_action": recovery_action_for(row),
    }


__all__ = [
    "LEGACY_SUMMARY",
    "effective_status",
    "identity_extras",
    "is_legacy_realization",
    "project_realization_status",
    "recovery_action_for",
]

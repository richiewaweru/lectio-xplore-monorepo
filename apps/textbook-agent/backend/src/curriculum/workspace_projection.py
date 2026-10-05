"""Canonical teacher-facing state projection for a Unit lesson workspace."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal

from curriculum.models import (
    ArtifactWorkspaceDTO,
    LessonWorkspaceStateDTO,
    PreparationProgressDTO,
    PreparationWorkspaceDTO,
    WorkspaceErrorDTO,
)
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import TeachingRevisionStore

ArtifactState = Literal[
    "not_created",
    "queued",
    "running",
    "ready",
    "failed_recoverable",
    "failed_terminal",
    # P10B: the pinned SharedLessonDocument Run needs a human reviewer
    # decision before Learn authoring can proceed. Distinct from a running
    # poll and from an execution failure.
    "needs_review",
]

_ACTIVE_REALIZATION_STAGES = {
    "selecting",
    "writing",
    "validating",
    "assembling",
    "awaiting_assets",
    "exporting",
    "editing",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _has_persisted_teaching_state(state: Mapping[str, Any]) -> bool:
    review = _mapping(state.get("teaching_review"))
    return bool(
        state.get("teaching_revisions")
        or _mapping(state.get("teaching_plan"))
        or review.get("approved_revision") is not None
        or str(review.get("status") or "").lower() == "approved"
    )


def workspace_state_from_layers(
    outer_state: Mapping[str, Any], page_state: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Merge progress/debug state with the page-document-owned teaching ledger.

    Native teaching review lives inside ``page_document_v2``. The outer
    generation wrapper remains authoritative for worker stage and structural
    planning fields. Legacy teaching fields are used only when the page state
    contains no persisted teaching data; an outer approval string alone still
    cannot verify an approval without a revision snapshot.
    """
    outer = dict(outer_state)
    page = dict(page_state or {})
    nested = _mapping(outer.get("page_document_v2"))
    if not _has_persisted_teaching_state(page) and _has_persisted_teaching_state(nested):
        page = dict(nested)
    if _has_persisted_teaching_state(page):
        return {**outer, **page}
    if _has_persisted_teaching_state(outer):
        return outer
    return {**outer, **page}


def _workspace_error(
    *,
    code: str | None = None,
    error_type: str | None = None,
    failure_class: str | None = None,
    message: str | None = None,
    retryable: bool | None = None,
    stage: str | None = None,
    work_item_id: str | None = None,
    attempt: object = None,
    recovery_action: str | None = None,
    max_attempts: object = None,
    auto_retrying: bool | None = None,
) -> WorkspaceErrorDTO | None:
    try:
        attempt_value = int(attempt) if attempt is not None else None
    except (TypeError, ValueError):
        attempt_value = None
    try:
        max_attempts_value = int(max_attempts) if max_attempts is not None else None
    except (TypeError, ValueError):
        max_attempts_value = None
    values = {
        "code": code,
        "error_type": error_type,
        "failure_class": failure_class,
        "message": message,
        "retryable": retryable,
        "stage": stage,
        "work_item_id": work_item_id,
        "attempt": attempt_value,
        "max_attempts": max_attempts_value,
        "recovery_action": recovery_action,
        "auto_retrying": auto_retrying,
    }
    if not any(value is not None for value in values.values()):
        return None
    return WorkspaceErrorDTO(**values)


def _approved_snapshot(state: Mapping[str, Any]) -> tuple[str, int, str] | None:
    """Return approval identity only when snapshot and persisted digest agree."""
    try:
        # TeachingRevisionStore can synthesize a legacy ledger from mutable
        # state. That compatibility read is useful to consumers, but it is not
        # proof that an immutable approval snapshot was actually persisted.
        if not state.get("teaching_revisions"):
            return None
        store = TeachingRevisionStore(deepcopy(dict(state)))
        review = _mapping(store.state.get("teaching_review"))
        approved_revision = review.get("approved_revision")
        if approved_revision is None:
            return None
        revision = int(approved_revision)
        record = store.get_revision(revision)
        if record is None or record.status != "approved" or not record.content_hash:
            return None
        plan = TeachingPlan.model_validate(record.plan)
        if teaching_plan_content_hash(plan) != record.content_hash:
            return None
        if plan.revision is not None and plan.revision != record.revision:
            return None
        if plan.teaching_plan_id and plan.teaching_plan_id != record.teaching_plan_id:
            return None
        return record.teaching_plan_id, record.revision, record.content_hash
    except (TypeError, ValueError, KeyError):
        return None


def _approved_snapshot_error(state: Mapping[str, Any]) -> tuple[str, str]:
    """Explain unverified legacy/hardening failures without asserting approval."""
    try:
        store = TeachingRevisionStore(deepcopy(dict(state)))
        review = _mapping(store.state.get("teaching_review"))
        revision_value = review.get("approved_revision")
        if revision_value is not None:
            record = store.get_revision(int(revision_value))
            if record is not None:
                if not record.content_hash:
                    return (
                        "APPROVED_CONTENT_HASH_UNAVAILABLE",
                        "This historical approval has no persisted content hash. Existing output remains readable; reprepare and review before creating a new output.",
                    )
                try:
                    matches = teaching_plan_content_hash(record.plan) == record.content_hash
                except (TypeError, ValueError):
                    matches = False
                if not matches:
                    return (
                        "APPROVED_CONTENT_HASH_MISMATCH",
                        "The approved Teaching Plan no longer matches its persisted content hash. Existing output remains readable; reprepare and review before creating a new output.",
                    )
    except (TypeError, ValueError, KeyError):
        pass
    return (
        "APPROVED_REVISION_UNVERIFIED",
        "Preparation completed without a verifiable approved teaching revision.",
    )


LEGACY_UNSUPPORTED_MESSAGE = "Prepared before the planning update — re-prepare this lesson."


@dataclass(frozen=True)
class PreparationRunView:
    """Plain-data view of a lesson's preparation Run (built by the application layer).

    The preparation Run is the only job status the UI projection reads.  It is
    deliberately plain data so this module never imports the runtime.
    """

    run_id: str
    status: str
    error_code: str | None = None
    error_summary: str | None = None
    retryable: bool = False
    items_total: int = 0
    items_ready: int = 0
    items_failed: int = 0
    teaching_plan: str = "not_started"
    failed_work_item_ids: tuple[str, ...] = field(default_factory=tuple)


def _progress(run: PreparationRunView | None) -> PreparationProgressDTO | None:
    if run is None:
        return None
    return PreparationProgressDTO(
        items_total=run.items_total,
        items_ready=run.items_ready,
        items_failed=run.items_failed,
        teaching_plan=run.teaching_plan,  # type: ignore[arg-type]
        failed_work_item_ids=list(run.failed_work_item_ids),
    )


def _preparation_projection(
    *,
    generation_id: str | None,
    state: Mapping[str, Any] | None,
    run: PreparationRunView | None,
    stale: bool,
) -> PreparationWorkspaceDTO:
    """Project preparation state from the preparation Run and the teaching ledger.

    Never reads ``generation.status`` or ``chunked.stage``: the Run is the job
    status, ``teaching_review`` (hash-bound revision store) is the approval
    state, and ``structure_review_open`` marks the stage-1 structural review.
    """
    if not generation_id:
        return PreparationWorkspaceDTO(state="not_started", stale=stale)

    chunked = state or {}
    review = _mapping(chunked.get("teaching_review"))
    raw_plan = _mapping(chunked.get("teaching_plan"))
    run_id = run.run_id if run is not None else None
    progress = _progress(run)

    approved = _approved_snapshot(chunked)
    review_status = str(review.get("status") or "").lower()
    if approved is not None and review_status == "approved":
        return PreparationWorkspaceDTO(
            state="approved",
            review_kind=None,
            generation_id=generation_id,
            teaching_plan_id=approved[0],
            approved_revision=approved[1],
            approved_content_hash=approved[2],
            approved_snapshot_verified=True,
            stale=stale,
            run_id=run_id,
            recovery_action="none",
            progress=progress,
        )

    if review_status == "approved" and approved is None:
        code, message = _approved_snapshot_error(chunked)
        return PreparationWorkspaceDTO(
            state="failed_terminal",
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=True,
            run_id=run_id,
            progress=progress,
            error=_workspace_error(
                code=code,
                error_type="workspace_state_ambiguous",
                failure_class="state_integrity",
                message=message,
                retryable=False,
                recovery_action="reprepare",
            ),
        )

    def _pending_plan_review() -> PreparationWorkspaceDTO | None:
        if review_status != "pending" or not raw_plan:
            return None
        try:
            plan = TeachingPlan.model_validate(raw_plan)
            if int(review.get("revision") or plan.revision) != plan.revision:
                return None
        except (TypeError, ValueError):
            return None
        return PreparationWorkspaceDTO(
            state="awaiting_review",
            review_kind="teaching_plan",
            generation_id=generation_id,
            teaching_plan_id=plan.teaching_plan_id,
            approved_revision=approved[1] if approved else None,
            approved_content_hash=approved[2] if approved else None,
            approved_snapshot_verified=approved is not None,
            stale=stale,
            run_id=run_id,
            recovery_action="review",
            progress=progress,
        )

    def _failed(
        failure_state: Literal["failed_recoverable", "failed_terminal"],
        *,
        code: str,
        message: str,
        retryable: bool,
        action: Literal["retry", "regenerate"],
    ) -> PreparationWorkspaceDTO:
        return PreparationWorkspaceDTO(
            state=failure_state,
            generation_id=generation_id,
            stale=stale,
            run_id=run_id,
            recovery_action=action,
            retryable=retryable,
            progress=progress,
            error=_workspace_error(
                code=code,
                error_type="preparation_run",
                message=message,
                retryable=retryable,
                stage="preparation",
                work_item_id=(
                    run.failed_work_item_ids[0]
                    if run is not None and run.failed_work_item_ids
                    else None
                ),
                recovery_action=action,
            ),
        )

    if run is not None:
        status = run.status
        if status in {"queued", "running", "awaiting_review"}:
            return PreparationWorkspaceDTO(
                state="planning",
                generation_id=generation_id,
                stale=stale,
                run_id=run_id,
                recovery_action="none",
                progress=progress,
            )
        if status == "failed_recoverable":
            return _failed(
                "failed_recoverable",
                code=run.error_code or "PREPARATION_RUN_FAILED",
                message=run.error_summary or "Plan generation failed.",
                retryable=run.retryable,
                action="retry" if run.retryable else "regenerate",
            )
        if status in {"failed_terminal", "cancelled"}:
            return _failed(
                "failed_terminal",
                code=run.error_code or "PREPARATION_RUN_FAILED",
                message=run.error_summary or "Plan generation failed.",
                retryable=False,
                action="regenerate",
            )
        if status == "ready":
            pending = _pending_plan_review()
            if pending is not None:
                return pending
            if review_status == "rejected":
                return _failed(
                    "failed_terminal",
                    code="TEACHING_PLAN_REJECTED",
                    message="The Teaching Plan was rejected. Regenerate it.",
                    retryable=False,
                    action="regenerate",
                )
        return PreparationWorkspaceDTO(
            state="failed_terminal",
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=True,
            run_id=run_id,
            recovery_action="regenerate",
            progress=progress,
            error=_workspace_error(
                code="PREPARATION_STATE_UNKNOWN",
                error_type="workspace_state_ambiguous",
                failure_class="state_integrity",
                message=(
                    "Preparation state cannot be determined from the plan run "
                    "and review data. Regenerate the plan."
                ),
                retryable=False,
                recovery_action="regenerate",
            ),
        )

    # No preparation Run.
    pending = _pending_plan_review()
    if pending is not None:
        # A plan generated before Runs is fully reviewable: approval is
        # hash-bound to the revision store, not to a job.
        return pending
    if chunked.get("structure_review_open") is True and isinstance(
        chunked.get("structural_plan"), dict
    ):
        return PreparationWorkspaceDTO(
            state="awaiting_review",
            review_kind="structural",
            generation_id=generation_id,
            stale=stale,
            recovery_action="review",
        )
    return PreparationWorkspaceDTO(
        state="legacy_unsupported",
        generation_id=generation_id,
        stale=stale,
        recovery_action="regenerate",
        retryable=False,
        error=_workspace_error(
            code="PREPARATION_LEGACY_UNSUPPORTED",
            error_type="legacy_unsupported",
            failure_class="legacy",
            message=LEGACY_UNSUPPORTED_MESSAGE,
            retryable=False,
            stage="preparation",
            recovery_action="regenerate",
        ),
    )


def _artifact_projection(
    realization: Mapping[str, Any] | None,
    *,
    legacy_ambiguous: bool,
) -> ArtifactWorkspaceDTO:
    if realization is None:
        return ArtifactWorkspaceDTO(
            state="not_created",
            legacy_ambiguous=legacy_ambiguous,
        )

    status = str(realization.get("status") or "").lower()
    output_id = realization.get("output_id")
    realization_id = realization.get("realization_id")
    href = realization.get("open_href")
    stale = status == "stale"
    shared_document_fields = {
        "shared_document_state": realization.get("shared_document_state"),
        "shared_document_run_id": realization.get("shared_document_run_id"),
        "shared_document_id": realization.get("shared_document_id"),
        "shared_document_revision": realization.get("shared_document_revision"),
        "shared_document_hash": realization.get("shared_document_hash"),
        "run_id": realization.get("run_id"),
        "recovery_action": realization.get("recovery_action"),
        "progress": realization.get("progress"),
    }
    if status == "needs_shared_review":
        return ArtifactWorkspaceDTO(
            state="needs_review",
            realization_id=str(realization_id) if realization_id else None,
            output_id=str(output_id) if output_id else None,
            open_href=str(href) if href else None,
            stale=False,
            legacy_ambiguous=legacy_ambiguous,
            error=None,
            **shared_document_fields,
        )
    if status in {"failed", "failed_recoverable"}:
        state: ArtifactState = "failed_recoverable"
    elif status == "failed_terminal":
        state = "failed_terminal"
    elif status in {"stale", "read_only"}:
        # A stale pinned identity needs reprepare; it is not an execution
        # failure and must not advertise the explicit failed-run retry action.
        state = "failed_terminal"
    elif status == "queued":
        state = "queued"
    elif status in _ACTIVE_REALIZATION_STAGES | {"running"}:
        state = "running"
    elif status in {"ready", "published", "completed"} and output_id:
        state = "ready"
    elif status in {"ready", "published", "completed"} or status == "read_only":
        state = "failed_terminal"
    else:
        state = "failed_terminal"

    error = None
    if state in {"failed_recoverable", "failed_terminal"}:
        stored_message = realization.get("error_summary")
        detail = _mapping(realization.get("error_detail"))
        code = (
            str(detail.get("code"))
            if detail.get("code")
            else
            "REALIZATION_STALE"
            if stale
            else "REALIZATION_READ_ONLY"
            if status == "read_only"
            else "REALIZATION_OUTPUT_MISSING"
            if status in {"ready", "published", "completed"} and not output_id
            else "REALIZATION_FAILED"
            if status in {"failed", "failed_recoverable", "failed_terminal"}
            else "REALIZATION_STATUS_UNKNOWN"
        )
        error = _workspace_error(
            code=code,
            error_type=(
                str(detail.get("error_type"))
                if detail.get("error_type")
                else "legacy_ambiguous"
                if legacy_ambiguous
                else None
            ),
            failure_class=(str(detail.get("failure_class")) if detail.get("failure_class") else None),
            message=(
                str(detail.get("message"))
                if detail.get("message")
                else
                str(stored_message)
                if stored_message
                else "This realization has no usable output and needs attention."
            ),
            retryable=(
                bool(detail.get("retryable"))
                if isinstance(detail.get("retryable"), bool)
                else state == "failed_recoverable"
            ),
            stage=str(detail.get("stage") or status) or None,
            work_item_id=(str(detail.get("work_item_id")) if detail.get("work_item_id") else None),
            attempt=detail.get("attempt"),
            max_attempts=detail.get("max_attempts"),
            auto_retrying=(
                detail.get("auto_retrying")
                if isinstance(detail.get("auto_retrying"), bool)
                else None
            ),
            recovery_action=(
                str(detail.get("recovery_action"))
                if detail.get("recovery_action")
                else "reprepare"
                if status == "stale"
                else str(realization.get("recovery_action"))
                if realization.get("recovery_action")
                else None
            ),
        )
    return ArtifactWorkspaceDTO(
        state=state,
        realization_id=str(realization_id) if realization_id else None,
        output_id=str(output_id) if output_id else None,
        open_href=str(href) if href else None,
        stale=stale,
        legacy_ambiguous=legacy_ambiguous,
        error=error,
        **shared_document_fields,
    )


def project_lesson_workspace(
    *,
    generation_id: str | None,
    state: Mapping[str, Any] | None = None,
    stale: bool = False,
    preparation_run: PreparationRunView | None = None,
    learn_realization: Mapping[str, Any] | None = None,
    print_realization: Mapping[str, Any] | None = None,
    legacy_ambiguous: bool = False,
) -> LessonWorkspaceStateDTO:
    """Project the preparation Run + persisted ledgers to stable teacher-facing state.

    Approval is decided before job status: a verified approved snapshot stays
    approved even if a downstream realization has failed. A status claiming
    completion without a verifiable approval record fails closed. Legacy rows
    with no path identity are reported at workspace level and never assigned to
    either artifact path.
    """
    preparation = _preparation_projection(
        generation_id=generation_id,
        state=state,
        run=preparation_run,
        stale=stale,
    )
    ambiguities: list[str] = []
    if legacy_ambiguous:
        ambiguities.append("ambiguous_legacy_realization_path")
    if preparation.legacy_ambiguous:
        ambiguities.append("ambiguous_approved_revision_snapshot")
    return LessonWorkspaceStateDTO(
        preparation=preparation,
        learn=_artifact_projection(
            learn_realization, legacy_ambiguous=legacy_ambiguous and learn_realization is None
        ),
        print=_artifact_projection(
            print_realization, legacy_ambiguous=legacy_ambiguous and print_realization is None
        ),
        legacy_ambiguities=ambiguities,
    )


__all__ = [
    "PreparationRunView",
    "project_lesson_workspace",
    "workspace_state_from_layers",
]

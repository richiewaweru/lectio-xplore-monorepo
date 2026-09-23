"""Canonical teacher-facing state projection for a Unit lesson workspace."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Literal

from curriculum.models import (
    ArtifactWorkspaceDTO,
    LessonWorkspaceStateDTO,
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
]

_ACTIVE_PREPARATION_STAGES = {
    "queued",
    "item_generation",
    "planning_teaching",
    "planning_forms",
    "writing_sections",
    "writing_blocks",
    "assembling",
    "stage1_running",
    "stage2_running",
    "variants_running",
}
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
) -> WorkspaceErrorDTO | None:
    try:
        attempt_value = int(attempt) if attempt is not None else None
    except (TypeError, ValueError):
        attempt_value = None
    values = {
        "code": code,
        "error_type": error_type,
        "failure_class": failure_class,
        "message": message,
        "retryable": retryable,
        "stage": stage,
        "work_item_id": work_item_id,
        "attempt": attempt_value,
        "recovery_action": recovery_action,
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


def _preparation_projection(
    *,
    generation_id: str | None,
    generation_status: str | None,
    workflow_stage: str | None,
    generation_error: str | None,
    generation_error_code: str | None,
    generation_error_type: str | None,
    state: Mapping[str, Any] | None,
    stale: bool,
) -> PreparationWorkspaceDTO:
    if not generation_id:
        return PreparationWorkspaceDTO(state="not_started", stale=stale)

    chunked = state or {}
    review = _mapping(chunked.get("teaching_review"))
    raw_plan = _mapping(chunked.get("teaching_plan"))
    stage = str(workflow_stage or "").lower()
    status = str(generation_status or "").lower()
    stage_detail = _mapping(chunked.get("error_detail"))

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
        )

    legacy_ambiguous = review_status == "approved" and approved is None
    if review_status == "pending" and raw_plan:
        try:
            plan = TeachingPlan.model_validate(raw_plan)
            review_revision = int(review.get("revision") or plan.revision)
            if review_revision == plan.revision:
                return PreparationWorkspaceDTO(
                    state="awaiting_review",
                    review_kind="teaching_plan",
                    generation_id=generation_id,
                    teaching_plan_id=plan.teaching_plan_id,
                    approved_revision=approved[1] if approved else None,
                    approved_content_hash=approved[2] if approved else None,
                    approved_snapshot_verified=approved is not None,
                    stale=stale,
                )
            legacy_ambiguous = True
        except (TypeError, ValueError):
            legacy_ambiguous = True

    if legacy_ambiguous and review_status in {"approved", "pending"}:
        code, message = (
            _approved_snapshot_error(chunked)
            if review_status == "approved"
            else (
                "PENDING_REVISION_UNVERIFIED",
                "The pending Teaching Plan does not match its review revision.",
            )
        )
        return PreparationWorkspaceDTO(
            state="failed_terminal",
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=True,
            error=_workspace_error(
                code=code,
                error_type="workspace_state_ambiguous",
                failure_class="state_integrity",
                message=message,
                retryable=False,
                stage=stage or None,
                recovery_action="reprepare" if review_status == "approved" else None,
            ),
        )

    if status in {"failed_terminal", "cancelled"} or stage in {
        "failed_terminal",
        "stage1_failed",
    }:
        failure_state: Literal["failed_recoverable", "failed_terminal"] = "failed_terminal"
    elif status in {"failed", "failed_recoverable"} or stage == "failed_recoverable":
        failure_state = "failed_recoverable"
    else:
        failure_state = "failed_terminal"

    if status in {"failed", "failed_recoverable", "failed_terminal", "cancelled"} or stage in {
        "failed_recoverable",
        "failed_terminal",
        "stage1_failed",
    }:
        error = _workspace_error(
            code=generation_error_code,
            error_type=generation_error_type,
            failure_class=(
                str(stage_detail["failure_class"])
                if stage_detail.get("failure_class") is not None
                else None
            ),
            message=generation_error
            or (str(stage_detail["message"]) if stage_detail.get("message") else None),
            retryable=(
                stage_detail.get("retryable")
                if isinstance(stage_detail.get("retryable"), bool)
                else failure_state == "failed_recoverable"
            ),
            stage=(str(stage_detail.get("stage") or stage) or None),
            work_item_id=(
                str(stage_detail["work_item_id"])
                if stage_detail.get("work_item_id") is not None
                else None
            ),
            attempt=stage_detail.get("attempt"),
        )
        return PreparationWorkspaceDTO(
            state=failure_state,
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=legacy_ambiguous,
            error=error,
        )

    structural_review_stages = {
        "awaiting_review",
        "plan_ready",
        "blueprint_ready",
        "assembly_blocked",
        "stage2_error",
    }
    if (stage in _ACTIVE_PREPARATION_STAGES and stage not in structural_review_stages) or (
        status in {"pending", "queued", "running", "generating"}
        and stage not in structural_review_stages
    ):
        return PreparationWorkspaceDTO(
            state="planning",
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=legacy_ambiguous,
        )

    if stage in structural_review_stages or (
        status == "awaiting_review" and stage not in _ACTIVE_PREPARATION_STAGES
    ):
        if isinstance(chunked.get("structural_plan"), dict):
            return PreparationWorkspaceDTO(
                state="awaiting_review",
                review_kind="structural",
                generation_id=generation_id,
                stale=stale,
                legacy_ambiguous=legacy_ambiguous,
            )
        legacy_ambiguous = True

    if (
        status in {"completed", "ready", "approved"}
        or stage
        in {
            "ready",
            "completed",
            "approved",
            "awaiting_teaching_approval",
        }
        or legacy_ambiguous
    ):
        message = (
            "Preparation claims approval but has no persisted matching approved revision snapshot."
            if legacy_ambiguous
            else "Preparation completed without a verifiable approved teaching revision."
        )
        return PreparationWorkspaceDTO(
            state="failed_terminal",
            generation_id=generation_id,
            stale=stale,
            legacy_ambiguous=True,
            error=_workspace_error(
                code="APPROVED_REVISION_UNVERIFIED",
                error_type="workspace_state_ambiguous",
                failure_class="state_integrity",
                message=message,
                retryable=False,
                stage=stage or None,
            ),
        )

    return PreparationWorkspaceDTO(
        state="failed_terminal",
        generation_id=generation_id,
        stale=stale,
        legacy_ambiguous=True,
        error=_workspace_error(
            code="PREPARATION_STATE_UNKNOWN",
            error_type="workspace_state_ambiguous",
            failure_class="state_integrity",
            message="Preparation state cannot be determined from persisted status and review data.",
            retryable=False,
            stage=stage or None,
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
            recovery_action=(
                str(detail.get("recovery_action"))
                if detail.get("recovery_action")
                else "reprepare"
                if status == "stale"
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
    )


def project_lesson_workspace(
    *,
    generation_id: str | None,
    generation_status: str | None = None,
    workflow_stage: str | None = None,
    generation_error: str | None = None,
    generation_error_code: str | None = None,
    generation_error_type: str | None = None,
    state: Mapping[str, Any] | None = None,
    stale: bool = False,
    learn_realization: Mapping[str, Any] | None = None,
    print_realization: Mapping[str, Any] | None = None,
    legacy_ambiguous: bool = False,
) -> LessonWorkspaceStateDTO:
    """Project persisted stage/ledger rows to stable teacher-facing state.

    Approval is decided before worker status: a verified approved snapshot stays
    approved even if a downstream realization has failed. A status claiming
    completion without a verifiable approval record fails closed. Legacy rows
    with no path identity are reported at workspace level and never assigned to
    either artifact path.
    """
    preparation = _preparation_projection(
        generation_id=generation_id,
        generation_status=generation_status,
        workflow_stage=workflow_stage,
        generation_error=generation_error,
        generation_error_code=generation_error_code,
        generation_error_type=generation_error_type,
        state=state,
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


__all__ = ["project_lesson_workspace", "workspace_state_from_layers"]

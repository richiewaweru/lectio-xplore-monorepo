from __future__ import annotations

import pytest
from sqlalchemy import select

from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    UserModel,
)
from core.entities.user import User
from curriculum.routes import get_path_lesson_status
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from curriculum.workspace_projection import (
    project_lesson_workspace,
    workspace_state_from_layers,
)
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture


def _approved_state() -> dict:
    state: dict = {}
    store = TeachingRevisionStore(state)
    store.record_draft(
        {
            "arc": "Explain water movement",
            "sections": [],
        },
        preparation_hash="prep-fingerprint-1",
        revision=1,
    )
    store.approve(expected_revision=1, reviewed_by="teacher-1")
    return state


def _realization(path: str, *, status: str, output_id: str | None) -> dict:
    return {
        "realization_id": f"{path}-run-1",
        "path": path,
        "status": status,
        "output_id": output_id,
        "open_href": f"/{path}/{output_id}" if output_id else None,
        "error_summary": "controlled failure" if "failed" in status else None,
    }


def test_ready_output_projects_ready_even_when_preparation_worker_is_active() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="running",
        workflow_stage="writing_sections",
        learn_realization=_realization("learn", status="ready", output_id="learn-out-1"),
    )

    assert workspace.learn.state == "ready"
    assert workspace.learn.output_id == "learn-out-1"
    assert workspace.preparation.state == "planning"


def test_failed_realization_never_projects_ready_when_output_pointer_exists() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="completed",
        workflow_stage="awaiting_teaching_approval",
        state=_approved_state(),
        learn_realization=_realization(
            "learn", status="failed_recoverable", output_id="old-output"
        ),
    )

    assert workspace.learn.state == "failed_recoverable"
    assert workspace.learn.output_id == "old-output"
    assert workspace.learn.error is not None
    assert workspace.learn.error.retryable is True


def test_stale_realization_does_not_advertise_failed_run_retry() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        learn_realization=_realization("learn", status="stale", output_id="old-output"),
    )

    assert workspace.learn.state == "failed_terminal"
    assert workspace.learn.stale is True
    assert workspace.learn.error is not None
    assert workspace.learn.error.code == "REALIZATION_STALE"
    assert workspace.learn.error.retryable is False
    assert workspace.learn.error.recovery_action == "reprepare"


def test_missing_path_realization_projects_not_created() -> None:
    workspace = project_lesson_workspace(generation_id=None)

    assert workspace.learn.state == "not_created"
    assert workspace.print.state == "not_created"
    assert workspace.preparation.state == "not_started"


def test_print_realization_cannot_fill_learn_projection_or_reverse() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        print_realization=_realization("print", status="ready", output_id="print-out-1"),
    )

    assert workspace.print.realization_id == "print-run-1"
    assert workspace.learn.state == "not_created"
    assert workspace.learn.realization_id is None


def test_learn_realization_cannot_fill_print_projection() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        learn_realization=_realization("learn", status="ready", output_id="learn-out-1"),
    )

    assert workspace.learn.realization_id == "learn-run-1"
    assert workspace.print.state == "not_created"
    assert workspace.print.realization_id is None


@pytest.mark.parametrize(
    ("learn_state", "print_state"),
    [
        ("not_created", "ready"),
        ("ready", "not_created"),
        ("running", "ready"),
        ("ready", "running"),
        ("failed_recoverable", "ready"),
        ("ready", "failed_recoverable"),
        ("failed_terminal", "queued"),
        ("ready", "ready"),
    ],
)
def test_p07_learn_print_state_truth_table_is_independent(
    learn_state: str, print_state: str
) -> None:
    def row(path: str, state: str) -> dict | None:
        if state == "not_created":
            return None
        return {
            **_realization(path, status=state, output_id=f"{path}-output"),
            "error_detail": (
                {
                    "code": f"{path.upper()}_ERROR",
                    "failure_class": "controlled",
                    "retryable": state == "failed_recoverable",
                    "stage": "test_stage",
                    "attempt": 2,
                }
                if state.startswith("failed")
                else None
            ),
        }

    workspace = project_lesson_workspace(
        generation_id="prep-p07-truth-table",
        learn_realization=row("learn", learn_state),
        print_realization=row("print", print_state),
    )

    assert workspace.learn.state == learn_state
    assert workspace.print.state == print_state
    assert workspace.learn.realization_id == ("learn-run-1" if learn_state != "not_created" else None)
    assert workspace.print.realization_id == ("print-run-1" if print_state != "not_created" else None)
    if learn_state.startswith("failed"):
        assert workspace.learn.error is not None
        assert workspace.learn.error.code == "LEARN_ERROR"
    if print_state.startswith("failed"):
        assert workspace.print.error is not None
        assert workspace.print.error.code == "PRINT_ERROR"


def test_ambiguous_legacy_row_is_reported_without_assigning_either_path() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-legacy",
        generation_status="completed",
        workflow_stage="completed",
        legacy_ambiguous=True,
    )

    assert workspace.learn.state == "not_created"
    assert workspace.print.state == "not_created"
    assert "ambiguous_legacy_realization_path" in workspace.legacy_ambiguities
    assert workspace.learn.legacy_ambiguous is True
    assert workspace.print.legacy_ambiguous is True
    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.legacy_ambiguous is True


def test_structural_awaiting_review_is_not_reported_as_failed_or_approved() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-structural",
        generation_status="awaiting_review",
        workflow_stage="awaiting_review",
        state={"structural_plan": {"sections": []}},
    )

    assert workspace.preparation.state == "awaiting_review"
    assert workspace.preparation.review_kind == "structural"
    assert workspace.preparation.approved_snapshot_verified is False


def test_teaching_worker_stage_stays_planning_despite_legacy_status_alias() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-teaching-worker",
        generation_status="awaiting_review",
        workflow_stage="planning_teaching",
        state={"structural_plan": {"sections": []}},
    )

    assert workspace.preparation.state == "planning"
    assert workspace.preparation.review_kind is None


def test_failed_generation_status_wins_over_stale_active_worker_stage() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-failed",
        generation_status="failed_recoverable",
        workflow_stage="writing_sections",
        generation_error="work-item budget exhausted",
    )

    assert workspace.preparation.state == "failed_recoverable"
    assert workspace.preparation.error is not None
    assert workspace.preparation.error.retryable is True


def test_stale_preparation_keeps_approval_identity_and_marks_it_stale() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="failed",
        workflow_stage="failed_recoverable",
        state=_approved_state(),
        stale=True,
    )

    assert workspace.preparation.state == "approved"
    assert workspace.preparation.approved_snapshot_verified is True
    assert workspace.preparation.stale is True


def test_revisionless_verified_snapshot_projects_approved_like_consumer_gate() -> None:
    from curriculum.teaching_plan.consumers import accept_approved_teaching_revision

    state = _approved_state()
    state["teaching_revisions"][0]["plan"].pop("revision")

    admitted = accept_approved_teaching_revision(state, consumer="print")
    workspace = project_lesson_workspace(
        generation_id="prep-legacy-revisionless",
        generation_status="completed",
        workflow_stage="approved",
        state=state,
    )

    assert admitted.revision is None
    assert workspace.preparation.state == "approved"
    assert workspace.preparation.approved_revision == 1
    assert workspace.preparation.approved_snapshot_verified is True


def test_new_pending_draft_is_not_hidden_by_older_approved_snapshot() -> None:
    state = _approved_state()
    TeachingRevisionStore(state).edit_plan(
        {"arc": "Updated explanation", "sections": []},
        preparation_hash="prep-fingerprint-2",
    )

    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="completed",
        workflow_stage="awaiting_teaching_approval",
        state=state,
    )

    assert workspace.preparation.state == "awaiting_review"
    assert workspace.preparation.review_kind == "teaching_plan"
    assert workspace.preparation.approved_revision == 1
    assert workspace.preparation.approved_snapshot_verified is True


def test_synthesized_legacy_approval_is_not_projected_as_verified() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-legacy-approved",
        generation_status="completed",
        workflow_stage="approved",
        state={
            "teaching_plan": {"arc": "Legacy plan", "sections": []},
            "teaching_review": {"status": "approved", "approved_revision": 1},
        },
    )

    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.approved_snapshot_verified is False
    assert workspace.preparation.legacy_ambiguous is True
    assert "ambiguous_approved_revision_snapshot" in workspace.legacy_ambiguities


@pytest.mark.parametrize("mutation", ["missing_hash", "changed_bytes"])
def test_approval_projection_matches_consumer_content_hash_gate(mutation: str) -> None:
    state = _approved_state()
    if mutation == "missing_hash":
        state["teaching_revisions"][0]["content_hash"] = None
    else:
        state["teaching_revisions"][0]["plan"]["arc"] = "Changed after approval"

    workspace = project_lesson_workspace(
        generation_id="prep-unverifiable-hash",
        generation_status="completed",
        workflow_stage="approved",
        state=state,
    )

    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.approved_snapshot_verified is False
    assert workspace.preparation.approved_content_hash is None
    assert workspace.preparation.error is not None
    assert workspace.preparation.error.code in {
        "APPROVED_CONTENT_HASH_UNAVAILABLE",
        "APPROVED_CONTENT_HASH_MISMATCH",
    }
    assert workspace.preparation.error.recovery_action == "reprepare"


def test_mismatched_pending_plan_does_not_poll_as_active_planning() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-pending-mismatch",
        generation_status="running",
        workflow_stage="planning_teaching",
        state={
            "teaching_plan": {"arc": "invalid legacy plan"},
            "teaching_review": {"status": "pending", "revision": 2},
        },
    )

    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.legacy_ambiguous is True
    assert workspace.preparation.error is not None
    assert workspace.preparation.error.code == "PENDING_REVISION_UNVERIFIED"


def test_preparation_failure_projects_underlying_typed_error_details() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="failed_recoverable",
        workflow_stage="failed_recoverable",
        generation_error="writer retries exhausted",
        generation_error_code="OUTPUT_INVALID",
        generation_error_type="generation",
        state={
            "error_detail": {
                "failure_class": "validation",
                "retryable": True,
                "stage": "writing",
                "work_item_id": "section-2:block-1",
                "attempt": 2,
            }
        },
    )

    error = workspace.preparation.error
    assert error is not None
    assert error.code == "OUTPUT_INVALID"
    assert error.error_type == "generation"
    assert error.failure_class == "validation"
    assert error.stage == "writing"
    assert error.work_item_id == "section-2:block-1"
    assert error.attempt == 2
    assert error.retryable is True


def test_approved_snapshot_stays_approved_when_downstream_print_failed() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-1",
        generation_status="failed",
        workflow_stage="failed_recoverable",
        generation_error="Print worker failed",
        state=_approved_state(),
        print_realization=_realization("print", status="failed_recoverable", output_id="prep-1"),
    )

    assert workspace.preparation.state == "approved"
    assert workspace.preparation.approved_snapshot_verified is True
    assert workspace.preparation.approved_revision == 1
    assert workspace.print.state == "failed_recoverable"


def test_nested_page_document_approval_projects_through_route_state_merge() -> None:
    state = _approved_state()
    outer = {
        "stage": "failed_recoverable",
        "teaching_review": {"status": "approved"},
        "page_document_v2": state,
    }
    # The normalized page loader can return only an empty shell on a legacy
    # generation; the persisted nested state remains the authoritative source.
    page_state = {"teaching_review": {"status": "pending"}}
    merged = workspace_state_from_layers(outer, page_state)
    workspace = project_lesson_workspace(
        generation_id="prep-nested",
        generation_status="failed",
        workflow_stage=outer["stage"],
        state=merged,
    )

    assert workspace.preparation.state == "approved"
    assert workspace.preparation.approved_revision == 1
    assert workspace.preparation.approved_snapshot_verified is True


def test_outer_legacy_approval_string_cannot_verify_snapshot() -> None:
    merged = workspace_state_from_layers(
        {"stage": "completed", "teaching_review": {"status": "approved"}},
        {"teaching_review": {"status": "pending"}},
    )
    workspace = project_lesson_workspace(
        generation_id="prep-outer-legacy",
        generation_status="completed",
        workflow_stage="completed",
        state=merged,
    )

    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.approved_snapshot_verified is False


def test_completed_preparation_without_approved_snapshot_fails_closed() -> None:
    workspace = project_lesson_workspace(
        generation_id="prep-unverified",
        generation_status="completed",
        workflow_stage="ready",
        state={"teaching_plan": {"arc": "unverified"}},
    )

    assert workspace.preparation.state == "failed_terminal"
    assert workspace.preparation.approved_snapshot_verified is False
    assert workspace.preparation.error is not None
    assert workspace.preparation.error.code == "APPROVED_REVISION_UNVERIFIED"


@pytest.mark.asyncio
async def test_path_lesson_status_reads_approval_from_nested_page_document_state(
    db_session,
) -> None:
    user = UserModel(
        id="p1-workspace-route-user",
        email="p1-workspace-route@example.invalid",
        name="P1 Workspace Route",
    )
    db_session.add(user)
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(
        db_session,
        unit=unit,
        plan=load_canonical_plan("grade4-photosynthesis-path.json"),
    )
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None

    state = _approved_state()
    generation = GenerationModel(
        id="p1-nested-page-preparation",
        user_id=user.id,
        subject="science",
        requested_template_id="lesson",
        requested_preset_id="balanced",
        status="failed_recoverable",
        error="A downstream Print attempt failed",
        chunked_state_json={
            "stage": "failed_recoverable",
            "page_document_v2": state,
        },
    )
    lesson.pack_id = generation.id
    db_session.add(generation)
    db_session.add(
        LessonProvenanceModel(
            pack_id=generation.id,
            path_version_id=version.id,
            path_lesson_id=lesson.id,
            objective_hash=lesson.objective_hash,
            path_lesson_revision=lesson.revision,
        )
    )
    await db_session.flush()

    response = await get_path_lesson_status(
        unit_id=unit.id,
        lesson_id=lesson.id,
        current_user=User(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at="2026-09-22T00:00:00Z",
            updated_at="2026-09-22T00:00:00Z",
        ),
        session=db_session,
    )

    assert response["workspace"]["preparation"]["state"] == "approved"
    assert response["workspace"]["preparation"]["approved_revision"] == 1
    assert response["worker_debug"]["debug_only"] is True
    assert response["worker_debug"]["workflow_stage"] == "failed_recoverable"

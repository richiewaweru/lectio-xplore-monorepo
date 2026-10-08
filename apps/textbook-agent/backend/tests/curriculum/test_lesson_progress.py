from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from curriculum.figure_progress import PlannedFigure
from curriculum.lesson_progress import ProgressItem, project_artifact_progress

START = datetime(2026, 10, 1, 12, 0, 0)


def _i(key: str, status: str, stage: str = "x") -> ProgressItem:
    return ProgressItem(key, stage, status)


def _project(items, *, run="running", realize=None, realize_items=(), path="learn"):
    return project_artifact_progress(
        path=path,
        shared_run_status=run,
        shared_items=items,
        shared_started_at=START,
        realize_run_status=realize,
        realize_items=realize_items,
    )


def _by_key(progress):
    return {s.key: s for s in progress.steps}


def test_none_without_any_run():
    assert (
        project_artifact_progress(
            path="learn", shared_run_status=None, shared_items=[], shared_started_at=None
        )
        is None
    )


def test_early_first_step_active():
    progress = _project([_i("sourcebook", "running")])
    steps = _by_key(progress)
    assert steps["sourcebook"].status == "active"
    assert steps["shared_tasks"].status == "pending"
    assert progress.current_label == "Gathering source notes"
    assert progress.started_at == START.replace(tzinfo=UTC).isoformat()
    assert "media" not in steps


def test_queued_next_stage_without_rows_shows_active():
    progress = _project([_i("sourcebook", "ready"), _i("shared_tasks", "ready")])
    assert _by_key(progress)["compose"].status == "active"


def test_mid_writing_counts():
    items = [_i("sourcebook", "ready"), _i("shared_tasks", "ready")]
    items += [_i(f"compose:s{n}", "ready") for n in range(4)]
    items += [_i("write:s0", "ready"), _i("write:s1", "ready"), _i("write:s2", "running")]
    items += [_i("write:s3", "queued"), _i("boundary:s0->s1", "ready")]
    progress = _project(items)
    steps = _by_key(progress)
    assert steps["compose"].status == "done"
    assert (steps["write"].status, steps["write"].done, steps["write"].total) == ("active", 2, 4)
    assert (steps["boundary"].done, steps["boundary"].total) == (1, 3)
    assert steps["boundary"].status == "active"
    assert progress.current_label == "Writing sections (2/4)"


def test_repair_items_replace_base_status():
    items = [
        _i("write:s0", "failed_recoverable"),
        _i("write:s0:repair:abc", "running"),
        _i("compose:s0", "ready"),
    ]
    steps = _by_key(_project(items))
    assert steps["write"].total == 1
    assert steps["write"].status == "active"


def test_media_step_only_when_media_items_exist():
    items = [
        _i("media:a", "ready", "media_generation"),
        _i("media:b", "running", "media_generation"),
    ]
    steps = _by_key(_project(items))
    assert (steps["media"].done, steps["media"].total) == (1, 2)


def test_document_qa_active():
    items = [_i("sourcebook", "ready"), _i("shared_tasks", "ready"), _i("compose:s0", "ready")]
    items += [_i("write:s0", "ready"), _i("document-qa", "running")]
    progress = _project(items)
    steps = _by_key(progress)
    assert steps["boundary"].status == "done"
    assert progress.current_label == "Final quality check"


def test_failed_step_is_current():
    items = [_i("sourcebook", "ready"), _i("shared_tasks", "failed_terminal")]
    progress = _project(items, run="failed_terminal")
    assert _by_key(progress)["shared_tasks"].status == "failed"
    assert progress.current_label == "Writing practice questions"


def test_shared_ready_builds_print_booklet():
    progress = _project(
        [],
        run="ready",
        realize="running",
        realize_items=[_i("print:realize", "running")],
        path="print",
    )
    steps = _by_key(progress)
    assert all(s.status == "done" for k, s in steps.items() if k != "realize")
    assert steps["realize"].status == "active"
    assert steps["realize"].label == "Building the Print booklet"


def test_everything_done():
    progress = _project([], run="ready", realize="ready")
    assert all(s.status == "done" for s in progress.steps)
    assert progress.current_label is None


def test_started_at_is_tz_aware_utc_and_elapsed_is_small():
    # DB datetimes are naive UTC; a run started "now" must not look hours old.
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="running",
        shared_items=[_i("sourcebook", "running")],
        shared_started_at=started,
    )
    assert progress.started_at is not None
    assert progress.started_at.endswith("+00:00")
    elapsed = datetime.now(UTC) - datetime.fromisoformat(progress.started_at)
    assert timedelta(0) <= elapsed < timedelta(seconds=60)


def _media(
    key: str,
    status: str,
    figure_id: str,
    *,
    error_code: str | None = None,
    attempt: int = 1,
    recovery_action: str | None = None,
    warnings: list[str] | None = None,
) -> ProgressItem:
    identity = {"figure_node_id": figure_id, "section_id": "s1", "required": True}
    if warnings:
        identity["warnings"] = warnings
    return ProgressItem(
        key,
        "media_generation",
        status,
        id=f"id-{key}",
        attempt=attempt,
        error_code=error_code,
        error_class="provider_transport" if error_code else None,
        error_summary="Figure generation failed: the image provider rejected the request (HTTP 403)."
        if error_code
        else None,
        recovery_action=recovery_action,
        composition_identity=json.dumps(identity),
    )


PLANNED = tuple(
    PlannedFigure(f"fig-{n}", "s1", "Section one", f"b{n}", True) for n in range(1, 6)
)


def test_figure_records_cover_planned_ready_failed_and_pending():
    items = [
        _media("media:1", "ready", "fig-1"),
        _media("media:2", "ready", "fig-2", warnings=["label_missing:Root"]),
        _media(
            "media:3",
            "failed_recoverable",
            "fig-3",
            error_code="provider_http_403",
            recovery_action="retry",
        ),
        _media("media:4", "running", "fig-4"),
    ]
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="running",
        shared_items=items,
        shared_started_at=START,
        planned_figures=PLANNED,
    )
    by_id = {f.figure_id: f for f in progress.figures}
    assert [f.status for f in progress.figures] == ["ready", "ready", "failed", "pending", "planned"]
    assert by_id["fig-2"].warnings == ["label_missing:Root"]
    failed = by_id["fig-3"]
    assert failed.error_code == "provider_http_403"
    assert failed.retryable is True
    assert failed.recovery_action == "retry"
    # 403 is never auto-retried: say so honestly.
    assert failed.auto_retrying is False
    assert by_id["fig-5"].section_title == "Section one"
    assert (progress.figures_planned, progress.figures_ready, progress.figures_failed) == (5, 2, 1)
    media_step = _by_key(progress)["media"]
    assert media_step.label == "Figures: 2 ready / 1 failed / 5 planned"
    assert media_step.status == "failed"
    assert progress.current_label == "Figures: 2 ready / 1 failed / 5 planned"


def test_transient_failure_is_marked_auto_retrying():
    items = [
        _media(
            "media:1",
            "failed_recoverable",
            "fig-1",
            error_code="provider_http_503",
            recovery_action="retry",
        )
    ]
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="failed_recoverable",
        shared_items=items,
        shared_started_at=START,
        planned_figures=PLANNED[:1],
    )
    figure = progress.figures[0]
    assert figure.status == "failed"
    assert figure.retryable is True
    assert figure.auto_retrying is True


def test_planned_figures_show_before_any_media_item_exists():
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="running",
        shared_items=[_i("sourcebook", "ready")],
        shared_started_at=START,
        planned_figures=PLANNED,
    )
    step = _by_key(progress)["media"]
    assert step.label == "Figures: 0 ready / 5 planned"
    assert step.status == "pending"
    assert {f.status for f in progress.figures} == {"planned"}


def test_all_figures_ready_is_done():
    items = [_media(f"media:{n}", "ready", f"fig-{n}") for n in range(1, 6)]
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="running",
        shared_items=items,
        shared_started_at=START,
        planned_figures=PLANNED,
    )
    step = _by_key(progress)["media"]
    assert step.label == "Figures: 5 ready"
    assert step.status == "done"


def test_plan_visual_figures_lists_one_per_visual_block_with_composer_ids():
    from curriculum.figure_progress import plan_visual_figures
    from curriculum.teaching_plan.models import TeachingPlanBlock
    from document.shared_lesson.composer import figure_item_for_block

    def block(block_id: str, visual: dict | None) -> dict:
        data = {
            "id": block_id,
            "position": 0,
            "intent": "explain",
            "brief": "brief",
            "evidence": "evidence",
        }
        if visual is not None:
            data["visual"] = visual
        return data

    visual = {"mode": "diagram", "purpose": "show flow", "must_show": ["a", "b"], "required": False}
    page_state = {
        "teaching_revisions": [
            {
                "revision": 2,
                "plan": {
                    "sections": [
                        {
                            "slot_id": "s1",
                            "display_title": "Intro",
                            "blocks": [block("b1", visual), block("b2", None)],
                        }
                    ]
                },
            }
        ]
    }

    planned = plan_visual_figures(page_state, revision=2)

    assert len(planned) == 1
    figure = planned[0]
    assert figure.section_id == "s1"
    assert figure.section_title == "Intro"
    assert figure.block_id == "b1"
    assert figure.required is False
    expected = figure_item_for_block("s1", TeachingPlanBlock.model_validate(block("b1", visual)))
    assert figure.figure_id == expected.id
    assert plan_visual_figures(page_state, revision=9) == []
    assert plan_visual_figures(None, revision=2) == []


def test_unavailable_figure_is_a_settled_advisory_state():
    unavailable = _media("media:2", "ready", "fig-2")
    unavailable = ProgressItem(
        **{
            **unavailable.__dict__,
            "output_json": {
                "status": "unavailable",
                "error_code": "provider_http_403",
                "reason": "The figure service was unavailable for this figure.",
            },
        }
    )
    items = [_media("media:1", "ready", "fig-1"), unavailable]
    progress = project_artifact_progress(
        path="learn",
        shared_run_status="running",
        shared_items=items,
        shared_started_at=START,
        planned_figures=PLANNED[:2],
    )
    by_id = {f.figure_id: f for f in progress.figures}
    assert by_id["fig-2"].status == "unavailable"
    assert by_id["fig-2"].error_code == "provider_http_403"
    assert by_id["fig-2"].error_summary == "The figure service was unavailable for this figure."
    assert by_id["fig-2"].retryable is False
    assert progress.figures_failed == 0
    step = _by_key(progress)["media"]
    assert step.label == "Figures: 1 ready / 1 unavailable"
    assert step.status == "done"


def test_shared_ready_without_print_run_says_starting_not_getting_started():
    # Shared document READY, realization Run not admitted yet: the build step
    # is waiting for dispatch, and the label must say so (not a blank state).
    progress = _project([], run="ready", realize=None, path="print")
    steps = _by_key(progress)
    assert all(s.status == "done" for k, s in steps.items() if k != "realize")
    assert steps["realize"].status == "pending"
    assert steps["realize"].label == "Building the Print booklet"
    assert progress.current_label == "Starting Print…"

    learn = _project([], run="ready", realize=None, path="learn")
    assert learn.current_label == "Starting Learn…"

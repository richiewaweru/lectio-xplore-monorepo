from __future__ import annotations

from datetime import datetime

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
    assert progress.started_at == START.isoformat()
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

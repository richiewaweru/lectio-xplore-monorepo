from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from infra.generation_runtime.http import _run_status


def _item(
    item_id: str,
    *,
    status: str,
    attempt: int = 1,
    max_attempts: int = 3,
    error_class: str | None = "provider_output",
    recovery_action: str | None = "retry",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        item_key=item_id,
        stage="section_writing",
        status=status,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        replaces_work_item_id=None,
        attempt=attempt,
        max_attempts=max_attempts,
        error_code="provider_output" if status.startswith("failed") else None,
        error_class=error_class if status.startswith("failed") else None,
        error_summary="Safe failure summary." if status.startswith("failed") else None,
        recovery_action=recovery_action if status.startswith("failed") else None,
    )


def _run(*items: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id="run-1",
        build_id="build-1",
        run_type="shared_document",
        status="failed_recoverable",
        stage="section_writing",
        work_items=list(items),
        output_artifact_id=None,
        output_artifact_type=None,
        output_revision=None,
        output_hash=None,
        source_artifact_type="teaching_plan",
        source_artifact_id="plan-1",
        source_revision=1,
        source_hash="source-hash",
        error_code="provider_output",
        error_class="provider_output",
        error_summary="Safe run failure.",
        recovery_action="retry",
        updated_at=datetime.now(UTC),
    )


def test_multiple_eligible_failed_leaves_expose_only_atomic_run_retry() -> None:
    run = _run(
        _item("ready", status="ready"),
        _item("failed-a", status="failed_recoverable"),
        _item("failed-b", status="failed_recoverable"),
    )

    status = _run_status(run)
    items = {item["id"]: item for item in status["work_items"]}

    assert status["allowed_actions"] == ["cancel", "retry"]
    assert status["links"]["retry"] == "/api/v1/generation/runs/run-1/retry"
    assert status["links"]["retry_work_item_ids"] == ["failed-a", "failed-b"]
    assert items["failed-a"]["allowed_actions"] == []
    assert items["failed-a"]["links"] == {}
    assert items["failed-b"]["allowed_actions"] == []
    assert items["ready"]["allowed_actions"] == []


def test_multiple_failed_leaves_without_full_eligibility_expose_no_retry() -> None:
    run = _run(
        _item("failed-a", status="failed_recoverable"),
        _item("failed-b", status="failed_terminal", error_class="validation"),
    )

    status = _run_status(run)

    assert status["allowed_actions"] == ["cancel"]
    assert "retry" not in status["links"]
    assert all(item["allowed_actions"] == [] for item in status["work_items"])
    assert all("retry" not in item["links"] for item in status["work_items"])


def test_single_eligible_failure_keeps_targeted_retry_link() -> None:
    run = _run(
        _item("ready", status="ready"),
        _item("failed-a", status="failed_recoverable"),
    )

    status = _run_status(run)
    items = {item["id"]: item for item in status["work_items"]}

    assert status["allowed_actions"] == ["cancel"]
    assert "retry" not in status["links"]
    assert items["failed-a"]["allowed_actions"] == ["retry"]
    assert items["failed-a"]["links"]["retry"] == (
        "/api/v1/generation/work-items/failed-a/retry"
    )

"""Teacher-facing stage progress for a Learn/Print build (pure projection).

Derived from ``generation_work_items`` rows of the shared-document Run and the
realization Run. No I/O: callers load the rows in one batched query per Run.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from curriculum.figure_progress import (
    PlannedFigure,
    active_leaves,
    figures_label,
    project_figures,
)
from curriculum.models import ArtifactProgressDTO, ArtifactProgressStepDTO
from document.shared_lesson.run_failure import summarize_failed_leaves

StepStatus = Literal["pending", "active", "done", "failed"]


@dataclass(frozen=True)
class ProgressItem:
    item_key: str
    stage: str
    status: str
    # Optional detail used for failure truth and per-figure records.
    id: str = ""
    replaces_work_item_id: str | None = None
    attempt: int = 1
    max_attempts: int = 3
    error_code: str | None = None
    error_class: str | None = None
    error_summary: str | None = None
    recovery_action: str | None = None
    composition_identity: str | None = None


def as_utc_iso(value: datetime | None) -> str | None:
    """Timezone-aware UTC ISO-8601. DB datetimes are naive UTC by design."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()


def _base_key(key: str) -> str:
    # Repair/replacement items share the base key of the item they replace.
    return key.split(":repair:", 1)[0]


def _collapse(items: Iterable[ProgressItem], prefix: str) -> dict[str, str]:
    """base key -> status; later rows (replacements) win over earlier ones."""
    out: dict[str, str] = {}
    for item in items:
        if item.item_key.startswith(prefix):
            out[_base_key(item.item_key)] = item.status
    return out


def _group_status(statuses: Sequence[str], total: int | None) -> StepStatus:
    if any(s.startswith("failed") for s in statuses):
        return "failed"
    done = sum(1 for s in statuses if s == "ready")
    if total is not None and total > 0 and done >= total:
        return "done"
    if any(s == "running" for s in statuses) or done > 0:
        return "active"
    return "pending"


def _single(items: Sequence[ProgressItem], key: str) -> StepStatus:
    status = None
    for item in items:
        if item.item_key == key:
            status = item.status
    if status is None:
        return "pending"
    return _group_status([status], 1)


def _counted(
    statuses: dict[str, str], total: int | None
) -> tuple[StepStatus, int, int | None]:
    done = sum(1 for s in statuses.values() if s == "ready")
    known = max(total or 0, len(statuses)) or None
    return _group_status(list(statuses.values()), known), done, known


def project_artifact_progress(
    *,
    path: Literal["learn", "print"],
    shared_run_status: str | None,
    shared_items: Sequence[ProgressItem],
    shared_started_at: datetime | None,
    realize_run_status: str | None = None,
    realize_items: Sequence[ProgressItem] = (),
    realize_started_at: datetime | None = None,
    planned_figures: Sequence[PlannedFigure] = (),
) -> ArtifactProgressDTO | None:
    """Return ordered steps, or None when there is no Run to describe."""
    if shared_run_status is None and realize_run_status is None:
        return None
    steps: list[ArtifactProgressStepDTO] = []
    figures: list = []

    def add(
        key: str,
        label: str,
        status: StepStatus,
        done: int | None = None,
        total: int | None = None,
    ) -> None:
        steps.append(
            ArtifactProgressStepDTO(key=key, label=label, status=status, done=done, total=total)
        )

    if shared_run_status is not None:
        all_done = shared_run_status == "ready"
        compose = _collapse(shared_items, "compose:")
        write = _collapse(shared_items, "write:")
        boundary = _collapse(shared_items, "boundary:")
        media = {
            _base_key(i.item_key): i.status
            for i in shared_items
            if i.item_key.startswith("media:") or i.stage == "media_generation"
        }
        sections = max(len(compose), len(write)) or None

        def pick(computed: StepStatus) -> StepStatus:
            return "done" if all_done else computed

        add("sourcebook", "Gathering source notes", pick(_single(shared_items, "sourcebook")))
        add(
            "shared_tasks",
            "Writing practice questions",
            pick(_single(shared_items, "shared_tasks")),
        )
        st, d, t = _counted(compose, sections)
        add("compose", "Planning sections", pick(st), d, t)
        st, d, t = _counted(write, sections)
        add("write", "Writing sections", pick(st), d, t)
        pairs = (sections - 1) if sections else None
        st, d, t = _counted(boundary, pairs)
        if sections == 1 and not boundary:
            st, d, t = ("done" if write and all(s == "ready" for s in write.values()) else "pending"), 0, 0
        add("boundary", "Checking how sections connect", pick(st), d, t)
        if media or planned_figures:
            failure = summarize_failed_leaves(active_leaves(list(shared_items)))
            figures = project_figures(
                planned_figures,
                shared_items,
                run_auto_retrying=bool(failure and failure.auto_retrying),
            )
            ready = sum(1 for f in figures if f.status == "ready")
            failed = sum(1 for f in figures if f.status == "failed")
            total = len(figures)
            if failed:
                fig_status: StepStatus = "failed"
            elif total and ready >= total:
                fig_status = "done"
            elif ready or any(f.status == "pending" for f in figures):
                fig_status = "active"
            else:
                fig_status = "pending"
            add(
                "media",
                figures_label(ready=ready, failed=failed, total=total),
                pick(fig_status),
                ready,
                total,
            )
        add("document_qa", "Final quality check", pick(_single(shared_items, "document-qa")))

    build_label = "Building the Learn lesson" if path == "learn" else "Building the Print booklet"
    if realize_run_status == "ready":
        build_status: StepStatus = "done"
    elif realize_run_status in {"failed_recoverable", "failed_terminal"}:
        build_status = "failed"
    else:
        build_status = _single(realize_items, f"{path}:realize")
        if build_status == "pending" and realize_run_status == "running":
            build_status = "active"
    add("realize", build_label, build_status)

    # Items are admitted progressively, so once earlier steps finish the next
    # stage may have no rows yet: show the first pending step as active.
    live = shared_run_status in {"queued", "running"} or realize_run_status in {
        "queued",
        "running",
    }
    if live and not any(s.status in {"active", "failed"} for s in steps):
        for index, step in enumerate(steps):
            if step.status == "pending":
                steps[index] = step.model_copy(update={"status": "active"})
                break

    current = next((s for s in steps if s.status == "failed"), None) or next(
        (s for s in steps if s.status == "active"), None
    )
    label = None
    if current is not None:
        label = current.label
        if current.total and current.key != "media":
            label = f"{label} ({current.done or 0}/{current.total})"
    started = shared_started_at or realize_started_at
    return ArtifactProgressDTO(
        steps=steps,
        current_label=label,
        started_at=as_utc_iso(started),
        figures=figures,
        figures_planned=len(figures),
        figures_ready=sum(1 for f in figures if f.status == "ready"),
        figures_failed=sum(1 for f in figures if f.status == "failed"),
    )


__all__ = ["ProgressItem", "project_artifact_progress"]

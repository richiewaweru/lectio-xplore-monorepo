"""Deterministic whole-lesson checks shared by Print and Learn."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from curriculum.lesson_sourcebook.models import LessonSourcebook
from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.validation import validate_shared_tasks
from curriculum.teaching_plan.models import TeachingPlan

from .models import CoherenceReport, RepairTarget, ReviewIssue


def _json_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_json_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_json_text(item) for item in value)
    return str(value or "")


def check_slope_consistency(output: Mapping[str, Any]) -> list[ReviewIssue]:
    """Protect the canonical `(1,4)`, `(3,12)` slope regression when present."""
    text = _json_text(output).lower()
    if not any(token in text for token in ("slope", "gradient", "(1, 4)", "(3, 12)")):
        return []
    issues: list[ReviewIssue] = []
    if not any(token in text for token in ("1, 4", "1,4", "[1, 4]", "[1,4]")):
        issues.append(ReviewIssue(code="SLOPE_POINT_MISSING", message="canonical point (1,4) is missing", details={"point": [1, 4]}))
    if not any(token in text for token in ("3, 12", "3,12", "[3, 12]", "[3,12]")):
        issues.append(ReviewIssue(code="SLOPE_POINT_MISSING", message="canonical point (3,12) is missing", details={"point": [3, 12]}))
    mentions = re.findall(r"(?:slope|gradient)\s*(?:is|=|of|:)?\s*(-?\d+(?:\.\d+)?)", text)
    if any(float(value) != 4 for value in mentions):
        issues.append(ReviewIssue(code="SLOPE_DRIFT", message="canonical points (1,4) and (3,12) require slope 4", details={"expected": 4, "mentions": mentions}))
    return issues


def compare_path_task_semantics(
    print_tasks: Iterable[SharedTaskSpec],
    learn_tasks: Iterable[SharedTaskSpec],
) -> list[ReviewIssue]:
    """Ensure each path uses the same task prompt/evaluation contract."""
    left = {task.id: task for task in print_tasks}
    right = {task.id: task for task in learn_tasks}
    issues: list[ReviewIssue] = []
    for task_id in sorted(set(left) | set(right)):
        if task_id not in left or task_id not in right:
            issues.append(ReviewIssue(code="TASK_PATH_MISSING", message=f"shared task {task_id!r} is missing from one realization", shared_task_id=task_id))
            continue
        if left[task_id].prompt != right[task_id].prompt or left[task_id].evaluation != right[task_id].evaluation:
            issues.append(ReviewIssue(code="TASK_PARITY_DRIFT", message=f"shared task {task_id!r} differs across Print/Learn", shared_task_id=task_id))
    return issues


def _node_ids(output: Any) -> list[str]:
    if not isinstance(output, Mapping):
        return []
    document = output.get("document", output)
    nodes = document.get("nodes") if isinstance(document, Mapping) else None
    if not isinstance(nodes, list):
        return []
    return [str(node.get("id")) for node in nodes if isinstance(node, Mapping) and node.get("id")]


def build_coherence_report(
    *,
    path: str,
    plan: TeachingPlan,
    tasks: Sequence[SharedTaskSpec],
    output: Mapping[str, Any],
    sourcebook: LessonSourcebook | None = None,
    semantic_issues: Sequence[ReviewIssue] = (),
) -> CoherenceReport:
    issues: list[ReviewIssue] = []
    task_errors = validate_shared_tasks(plan, tasks, sourcebook=sourcebook)
    issues.extend(ReviewIssue(code="SHARED_TASK_CONTRACT", message=error) for error in task_errors)
    ids = _node_ids(output)
    if len(ids) != len(set(ids)):
        issues.append(ReviewIssue(code="DUPLICATE_NODE_ID", message="realized lesson contains duplicate node ids", path=path))
    issues.extend(check_slope_consistency(output))
    report = CoherenceReport(
        path=path,  # type: ignore[arg-type]
        teaching_plan_id=str(plan.teaching_plan_id or ""),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=str(plan.preparation_hash or ""),
        deterministic_issues=issues,
        semantic_issues=list(semantic_issues),
        reviewed=True,
    )
    return report.model_copy(update={"repair_targets": repair_targets_for_report(report)})


def repair_targets_for_report(report: CoherenceReport, *, max_targets: int = 3) -> list[RepairTarget]:
    """Map only named issues to bounded repair targets; never repair the whole lesson."""
    targets: list[RepairTarget] = []
    seen: set[tuple[str, str]] = set()
    for issue in report.issues:
        if not issue.blocking:
            continue
        if issue.shared_task_id:
            kind, target_id = "task", issue.shared_task_id
        elif issue.figure_id:
            kind, target_id = "figure", issue.figure_id
        elif issue.node_id:
            kind, target_id = "node", issue.node_id
        elif issue.teaching_block_id:
            kind, target_id = "node", issue.teaching_block_id
        else:
            continue
        key = (kind, target_id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            RepairTarget(
                kind=kind,
                target_kind={"node": "document_node", "task": "shared_task", "figure": "figure_asset"}[kind],
                target_id=target_id,
                issue_codes=[issue.code],
                instruction=issue.message,
            )
        )
        if len(targets) >= max_targets:
            break
    return targets


def review_with_targeted_repairs(
    *,
    path: str,
    plan: TeachingPlan,
    tasks: Sequence[SharedTaskSpec],
    output: Mapping[str, Any],
    sourcebook: LessonSourcebook | None = None,
    repair: Any | None = None,
    max_attempts: int = 1,
    max_targets: int = 3,
) -> tuple[CoherenceReport, list[dict[str, Any]]]:
    """Run review, repair only named targets, and revalidate after each pass."""
    if max_attempts < 0 or max_targets < 0:
        raise ValueError("repair caps must be non-negative")
    current = dict(output)
    events: list[dict[str, Any]] = []
    report = build_coherence_report(
        path=path, plan=plan, tasks=tasks, output=current, sourcebook=sourcebook,
    )
    for attempt in range(1, max_attempts + 1):
        targets = report.repair_targets[:max_targets]
        if not targets or repair is None:
            break
        for target in targets:
            try:
                replacement = repair(target, current)
                if replacement is not None:
                    current = dict(replacement)
                events.append({"attempt": attempt, "target": target.model_dump(mode="json"), "status": "completed"})
            except (RuntimeError, TypeError, ValueError) as exc:
                events.append({"attempt": attempt, "target": target.model_dump(mode="json"), "status": "failed", "message": str(exc)})
        report = build_coherence_report(
            path=path, plan=plan, tasks=tasks, output=current, sourcebook=sourcebook,
        ).model_copy(update={"repair_attempts": attempt})
        if not report.blocking:
            break
    if report.blocking and max_attempts and events:
        # The caller can fail closed based on this explicit state.
        report = report.model_copy(update={"repair_attempts": max_attempts})
    return report, events


__all__ = [
    "build_coherence_report",
    "check_slope_consistency",
    "compare_path_task_semantics",
    "repair_targets_for_report",
    "review_with_targeted_repairs",
]

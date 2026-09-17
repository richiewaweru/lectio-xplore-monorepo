from __future__ import annotations

from collections.abc import Iterable, Mapping

from curriculum.lesson_sourcebook.models import LessonSourcebook, TeachingContentBinding
from curriculum.teaching_plan.compatibility import response_bearing_action
from curriculum.teaching_plan.models import TeachingPlan

from .models import SharedTaskSpec
from .service import teaching_plan_hash


def validate_task_response_contract(task: SharedTaskSpec) -> list[str]:
    """Validate the answer-shape data needed by either realization path.

    The provider may return a syntactically valid response envelope that is
    still unusable (for example ``select-one`` with no options).  Keep this
    check semantic and path-neutral so stale/fallback artifacts cannot be
    reused by Print or Learn.
    """
    response = task.response
    response_type = str(response.get("type") or "")
    errors: list[str] = []
    action = str(task.action)
    if action in {"select-one", "select-many"} or response_type in {
        "single_choice",
        "multiple_choice",
        "select-one",
        "select-many",
    }:
        options = response.get("options")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"task {task.id!r} choice response requires at least two options")
        elif any(not isinstance(option, dict) for option in options):
            errors.append(f"task {task.id!r} choice options must be objects")
    elif action == "classify-items" or response_type in {"classification", "classify-items"}:
        if not isinstance(response.get("items"), list) or not response["items"]:
            errors.append(f"task {task.id!r} classification response requires items")
        if not isinstance(response.get("categories"), list) or not response["categories"]:
            errors.append(f"task {task.id!r} classification response requires categories")
        if not isinstance(response.get("correct_placements"), dict):
            errors.append(f"task {task.id!r} classification response requires correct_placements")
    elif action == "match-pairs" or response_type in {"matching", "match-pairs"}:
        if not isinstance(response.get("pairs"), list) or not response["pairs"]:
            errors.append(f"task {task.id!r} matching response requires pairs")
    elif action in {"order-items", "reconstruct-order"} or response_type in {
        "ordered_items",
        "order-items",
    }:
        if not isinstance(response.get("items"), list) or not response["items"]:
            errors.append(f"task {task.id!r} ordered response requires items")
        if not isinstance(response.get("correct_order"), list) and not isinstance(
            response.get("order"), list
        ):
            errors.append(f"task {task.id!r} ordered response requires an answer order")
    elif action == "complete-missing-values" or response_type == "missing_values":
        if not isinstance(response.get("values"), list) and not isinstance(
            response.get("answers"), list
        ):
            errors.append(f"task {task.id!r} missing-values response requires values")
    return errors


def validate_shared_tasks(
    plan: TeachingPlan,
    tasks: Iterable[SharedTaskSpec],
    *,
    sourcebook: LessonSourcebook | None = None,
    bindings: Iterable[TeachingContentBinding] = (),
) -> list[str]:
    task_list = list(tasks)
    errors: list[str] = []
    by_block: dict[str, SharedTaskSpec] = {}
    for task in task_list:
        if task.teaching_plan_id != plan.teaching_plan_id:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_id")
        if task.teaching_plan_revision != plan.revision:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_revision")
        if task.teaching_plan_hash != teaching_plan_hash(plan):
            errors.append(f"task {task.id!r} has the wrong teaching_plan_hash")
        if task.teaching_block_id in by_block:
            errors.append(f"multiple shared tasks own block {task.teaching_block_id!r}")
        by_block[task.teaching_block_id] = task
        if task.mode == "formative" and task.approved_source_ids:
            errors.append(f"formative task {task.id!r} cannot own approved sources")
        if task.mode == "assessment" and not task.approved_source_ids:
            errors.append(f"assessment task {task.id!r} requires approved sources")
        if not task.response.get("type"):
            errors.append(f"task {task.id!r} response must declare a semantic type")
        errors.extend(validate_task_response_contract(task))
        if sourcebook is not None:
            missing = sorted(set(task.sourcebook_refs) - set(sourcebook.by_id()))
            if missing:
                errors.append(f"task {task.id!r} references unknown sourcebook entries {missing}")
    response_blocks: dict[str, object] = {}
    for section in plan.sections:
        for block in section.blocks:
            action = block.learner_action.action if block.learner_action else None
            if action and response_bearing_action(action):
                response_blocks[block.id] = block
                if block.id not in by_block:
                    errors.append(f"response-bearing block {block.id!r} has no SharedTaskSpec")
            elif block.id in by_block:
                errors.append(f"passive block {block.id!r} cannot own a SharedTaskSpec")
    unknown_blocks = sorted(set(by_block) - set(response_blocks))
    for block_id in unknown_blocks:
        errors.append(f"shared task {by_block[block_id].id!r} targets unknown/non-response block {block_id!r}")
    return errors


def assert_task_preserved(realized: Mapping[str, object], task: SharedTaskSpec) -> None:
    """Fail closed when a path realization changes shared task semantics."""
    prompt = realized.get("prompt")
    if prompt is not None and str(prompt).strip() != task.prompt.strip():
        raise ValueError(f"realized task {task.id!r} changed prompt meaning")
    evaluation = realized.get("evaluation")
    if evaluation is not None and evaluation != task.evaluation:
        raise ValueError(f"realized task {task.id!r} changed evaluation ownership")


__all__ = [
    "assert_task_preserved",
    "validate_shared_tasks",
    "validate_task_response_contract",
]

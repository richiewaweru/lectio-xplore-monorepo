from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from curriculum.lesson_sourcebook.models import LessonSourcebook, TeachingContentBinding
from curriculum.teaching_plan.compatibility import response_bearing_action
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan

from .models import (
    ACTION_RESPONSE_TYPES,
    PASSIVE_ACTION_MEANINGS,
    TASK_EVALUATION_FIELDS,
    TASK_RESPONSE_FIELDS,
    SharedTaskSpec,
    TaskEvaluationType,
)

_FEEDBACK_META_KEYS = frozenset({"correct", "incorrect", "by_option"})


def _feedback_text_blank(value: object) -> bool:
    return not isinstance(value, str) or not value.strip()


def _validate_choice_feedback(
    task: SharedTaskSpec, declared_ids: set[str], correct_ids: list[str]
) -> list[str]:
    """Validate the deterministic per-option feedback contract for choice tasks.

    Feedback may be omitted. When present, every option-id key (top-level
    legacy form or nested under ``by_option``) must be a real, wrong option
    id, every wrong option must have feedback, and no feedback text may be
    blank.
    """
    feedback = task.feedback
    if feedback is None:
        return []
    errors: list[str] = []
    by_option = feedback.get("by_option")
    if "by_option" in feedback and not isinstance(by_option, dict):
        errors.append(f"task {task.id!r} feedback_unknown_option: by_option must be an object")
        by_option = {}
    elif not isinstance(by_option, dict):
        by_option = {}
    top_level_option_keys = {
        key: value for key, value in feedback.items() if key not in _FEEDBACK_META_KEYS
    }
    per_option: dict[str, object] = dict(top_level_option_keys)
    per_option.update(by_option)
    correct_set = {str(value) for value in correct_ids}
    if per_option:
        unknown_options = sorted(set(per_option) - declared_ids)
        if unknown_options:
            errors.append(f"task {task.id!r} feedback_unknown_option {unknown_options}")
        on_correct = sorted(set(per_option) & correct_set)
        if on_correct:
            errors.append(f"task {task.id!r} feedback_on_correct_option {on_correct}")
        wrong_ids = sorted(declared_ids - correct_set)
        covered = set(per_option) & declared_ids
        missing = sorted(set(wrong_ids) - covered)
        if missing:
            errors.append(f"task {task.id!r} feedback_missing_wrong_option {missing}")
    for key, value in feedback.items():
        if key == "by_option":
            if isinstance(value, dict):
                for option_key, text in value.items():
                    if _feedback_text_blank(text):
                        errors.append(f"task {task.id!r} feedback_blank at by_option.{option_key}")
            continue
        if _feedback_text_blank(value):
            errors.append(f"task {task.id!r} feedback_blank at {key}")
    return errors


def _validate_classification_feedback(task: SharedTaskSpec, items: list[str]) -> list[str]:
    """Validate the deterministic feedback contract for classification tasks.

    Feedback may be omitted. When present, ``common_errors`` keys must refer
    to real classified items and no feedback text may be blank.
    """
    feedback = task.feedback
    if feedback is None:
        return []
    errors: list[str] = []
    common_errors = feedback.get("common_errors")
    if common_errors is not None:
        if not isinstance(common_errors, dict):
            errors.append(f"task {task.id!r} feedback_unknown_item: common_errors must be an object")
        else:
            item_set = {str(item) for item in items}
            unknown = sorted(set(common_errors) - item_set)
            if unknown:
                errors.append(f"task {task.id!r} feedback_unknown_item {unknown}")
            for key, text in common_errors.items():
                if _feedback_text_blank(text):
                    errors.append(f"task {task.id!r} feedback_blank at common_errors.{key}")
    for key, value in feedback.items():
        if key == "common_errors":
            continue
        if _feedback_text_blank(value):
            errors.append(f"task {task.id!r} feedback_blank at {key}")
    return errors


def validate_final_task_response_contract(task: SharedTaskSpec) -> list[str]:
    """Validate canonical response/evaluation meaning for finalized tasks.

    The provider may return a syntactically valid response envelope that is
    still unusable (for example ``select-one`` with no options). This
    path-neutral check belongs at the SharedDocument finalization gate.
    """
    response = task.response
    response_type = str(response.get("type") or "")
    errors: list[str] = []
    action = task.action
    expected_type = ACTION_RESPONSE_TYPES.get(action)
    if expected_type is None:
        errors.append(f"task {task.id!r} uses an unsupported learner action")
    elif response_type != expected_type:
        errors.append(
            f"task {task.id!r} action {action!r} requires response type {expected_type!r}"
        )
    elif set(response) - TASK_RESPONSE_FIELDS[expected_type]:
        unexpected = sorted(set(response) - TASK_RESPONSE_FIELDS[expected_type])
        errors.append(f"task {task.id!r} response contains unsupported fields {unexpected}")

    if response_type in {"single_choice", "multiple_choice"}:
        options = response.get("options")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"task {task.id!r} choice response requires at least two options")
        elif any(
            not isinstance(option, dict)
            or not isinstance(option.get("id", option.get("key")), str)
            or not option.get("id", option.get("key")).strip()
            or not isinstance(option.get("text"), str)
            or not option["text"].strip()
            for option in options
        ):
            errors.append(f"task {task.id!r} choice options require unique ids and learner-facing text")
        else:
            option_ids = [str(option.get("id", option.get("key"))) for option in options]
            if len(option_ids) != len(set(option_ids)):
                errors.append(f"task {task.id!r} choice option ids must be unique")
        evaluation = task.evaluation
        correct = evaluation.get("correct_option_id") or evaluation.get("correct_key")
        correct_many = evaluation.get("correct_option_ids")
        if correct_many is None:
            correct_many = evaluation.get("correct_keys")
        if correct_many is None:
            correct_many = evaluation.get("correct")
        if response_type == "single_choice":
            if not isinstance(correct, str) and isinstance(correct_many, list) and len(correct_many) == 1:
                correct = str(correct_many[0])
            if not isinstance(correct, str) or not correct.strip():
                errors.append(f"task {task.id!r} single-choice evaluation requires one correct option id")
        elif not isinstance(correct_many, list):
            errors.append(f"task {task.id!r} multiple-choice evaluation requires correct option ids")
        elif not correct_many:
            errors.append(f"task {task.id!r} multiple-choice evaluation requires at least one correct option id")
        correct_ids = (
            [correct] if isinstance(correct, str) else correct_many
        )
        if isinstance(options, list) and correct_ids:
            declared = {
                str(option.get("id", option.get("key")))
                for option in options if isinstance(option, dict)
            }
            unknown = sorted({str(value) for value in correct_ids} - declared)
            if unknown:
                errors.append(f"task {task.id!r} evaluation references unknown option ids {unknown}")
            elif task.feedback is not None:
                errors.extend(
                    _validate_choice_feedback(task, declared, [str(value) for value in correct_ids])
                )
    elif response_type == "classification":
        items = response.get("items")
        categories = response.get("categories")
        items_valid = isinstance(items, list) and bool(items) and all(
            isinstance(item, str) and item.strip() for item in items
        )
        if not items_valid:
            errors.append(f"task {task.id!r} classification response requires items")
        elif task.feedback is not None:
            errors.extend(_validate_classification_feedback(task, list(items)))
        if not isinstance(categories, list) or not categories or any(
            not isinstance(item, str) or not item.strip() for item in categories
        ):
            errors.append(f"task {task.id!r} classification response requires categories")
        placements = response.get("correct_placements")
        if not isinstance(placements, dict) or not placements:
            errors.append(f"task {task.id!r} classification response requires correct_placements")
        elif isinstance(items, list) and isinstance(categories, list):
            if any(not isinstance(key, str) or not key.strip() for key in placements):
                errors.append(f"task {task.id!r} placement item ids must be non-empty strings")
            if any(not isinstance(value, str) or not value.strip() for value in placements.values()):
                errors.append(f"task {task.id!r} placement categories must be non-empty strings")
            if set(map(str, placements)) != set(map(str, items)):
                errors.append(f"task {task.id!r} placements must cover every classified item exactly")
            if set(map(str, placements.values())) - set(map(str, categories)):
                errors.append(f"task {task.id!r} placements reference undeclared categories")
        if (
            task.evaluation.get("type") == "mapping"
            and task.evaluation.get("correct_placements") != placements
        ):
            errors.append(f"task {task.id!r} mapping evaluation must preserve correct_placements")
    elif response_type == "matching":
        pairs = response.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            errors.append(f"task {task.id!r} matching response requires pairs")
        elif any(
            not isinstance(pair, dict)
            or not isinstance(pair.get("left"), str)
            or not pair["left"].strip()
            or not isinstance(pair.get("right"), str)
            or not pair["right"].strip()
            for pair in pairs
        ):
            errors.append(f"task {task.id!r} matching response requires complete left/right pairs")
        elif len({str(pair["left"]) for pair in pairs}) != len(pairs):
            errors.append(f"task {task.id!r} matching left values must be unique")
        if task.evaluation.get("type") == "mapping":
            evaluated_pairs = task.evaluation.get("pairs", task.evaluation.get("correct_pairs"))
            if evaluated_pairs != pairs:
                errors.append(f"task {task.id!r} mapping evaluation must preserve matching pairs")
    elif response_type == "ordered_items":
        items = response.get("items")
        if not isinstance(items, list) or not items or any(
            not isinstance(item, str) or not item.strip() for item in items
        ):
            errors.append(f"task {task.id!r} ordered response requires items")
        order = response.get("correct_order", response.get("order"))
        if not isinstance(order, list) or not order or any(
            not isinstance(item, str) or not item.strip() for item in order
        ):
            errors.append(f"task {task.id!r} ordered response requires an answer order")
        elif isinstance(items, list) and sorted(order) != sorted(items):
            errors.append(f"task {task.id!r} answer order must contain exactly the declared items")
        if task.evaluation.get("type") == "ordered_match":
            evaluated_order = task.evaluation.get("correct_order", task.evaluation.get("order"))
            if evaluated_order != order:
                errors.append(f"task {task.id!r} ordered-match evaluation must preserve the answer order")
    elif response_type == "missing_values":
        values = response.get("values", response.get("answers"))
        if not isinstance(values, list) or not values or any(
            not isinstance(value, (str, int, float))
            or isinstance(value, bool)
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, float) and not math.isfinite(value))
            for value in values
        ):
            errors.append(f"task {task.id!r} missing-values response requires values")

    if response_type not in {"single_choice", "multiple_choice", "classification"} and isinstance(
        task.feedback, dict
    ):
        for key, value in task.feedback.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if _feedback_text_blank(sub_value):
                        errors.append(f"task {task.id!r} feedback_blank at {key}.{sub_key}")
            elif _feedback_text_blank(value):
                errors.append(f"task {task.id!r} feedback_blank at {key}")

    evaluation_type = str(task.evaluation.get("type") or "")
    if evaluation_type not in TaskEvaluationType.__args__:
        errors.append(f"task {task.id!r} evaluation must use a supported semantic type")
    elif set(task.evaluation) - TASK_EVALUATION_FIELDS[evaluation_type]:
        unexpected = sorted(set(task.evaluation) - TASK_EVALUATION_FIELDS[evaluation_type])
        errors.append(f"task {task.id!r} evaluation contains unsupported fields {unexpected}")
    allowed_evaluation_types = {
        "single_choice": {"exact_match", "choice_keys"},
        "multiple_choice": {"exact_match", "choice_keys"},
        "missing_values": {"rubric", "exact_match", "accepted_answers"},
        "classification": {"rubric", "mapping"},
        "matching": {"rubric", "mapping", "exact_match"},
        "ordered_items": {"rubric", "ordered_match", "exact_match"},
        "number": {"rubric", "numeric", "exact_match"},
        "text": {"rubric", "accepted_answers", "teacher_review", "exact_match"},
    }
    if response_type in allowed_evaluation_types and evaluation_type not in allowed_evaluation_types[response_type]:
        errors.append(
            f"task {task.id!r} evaluation type {evaluation_type!r} is incompatible with {response_type!r}"
        )
    if evaluation_type == "rubric":
        criteria = task.evaluation.get("criteria") or task.evaluation.get("rubric")
        if not isinstance(criteria, (str, list)) or not criteria or (isinstance(criteria, str) and not criteria.strip()):
            errors.append(f"task {task.id!r} rubric evaluation requires meaningful criteria")
        elif isinstance(criteria, list) and any(not str(item).strip() for item in criteria):
            errors.append(f"task {task.id!r} rubric criteria must be meaningful")
    elif evaluation_type == "exact_match" and response_type not in {"single_choice", "multiple_choice"}:
        answer = task.evaluation.get("answer", task.evaluation.get("correct_value"))
        if answer is None or (isinstance(answer, str) and not answer.strip()):
            errors.append(f"task {task.id!r} exact-match evaluation requires an answer")
    elif evaluation_type == "choice_keys" and response_type not in {"single_choice", "multiple_choice"}:
        correct = task.evaluation.get("correct")
        if not isinstance(correct, list) or not correct:
            errors.append(f"task {task.id!r} choice-keys evaluation requires correct keys")
    elif evaluation_type == "numeric":
        value = task.evaluation.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"task {task.id!r} numeric evaluation requires a numeric value")
        tolerance = task.evaluation.get("tolerance")
        if tolerance is not None and (
            isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or tolerance < 0
        ):
            errors.append(f"task {task.id!r} numeric tolerance must be finite and non-negative")
    elif evaluation_type == "accepted_answers":
        answers = task.evaluation.get("accepted_answers")
        if not isinstance(answers, list) or not answers or any(not str(item).strip() for item in answers):
            errors.append(f"task {task.id!r} accepted-answers evaluation requires answers")
        elif response_type == "missing_values":
            response_answers = task.response.get("values", task.response.get("answers"))
            if response_answers != answers:
                errors.append(f"task {task.id!r} evaluation must preserve missing-value answers")
    elif evaluation_type == "teacher_review":
        guidance = task.evaluation.get("review_guidance")
        if not isinstance(guidance, str) or not guidance.strip():
            errors.append(f"task {task.id!r} teacher-review evaluation requires review_guidance")
    elif evaluation_type == "mapping":
        mapping = task.evaluation.get("correct_placements")
        pairs = task.evaluation.get("pairs", task.evaluation.get("correct_pairs"))
        if not isinstance(mapping, dict) and not isinstance(pairs, list):
            errors.append(f"task {task.id!r} mapping evaluation requires placements or pairs")
    elif evaluation_type == "ordered_match":
        order = task.evaluation.get("correct_order", task.evaluation.get("order"))
        if not isinstance(order, list) or not order:
            errors.append(f"task {task.id!r} ordered-match evaluation requires an answer order")
    return errors


def assert_task_response_contract(task: SharedTaskSpec) -> None:
    """Raise when a task's response/evaluation meaning is not fully realizable.

    This is the pure per-task gate for finalized SharedLessonDocument contracts.
    Base SharedTaskSpec remains readable by staged legacy Print/Learn callers.
    """
    errors = validate_final_task_response_contract(task)
    if errors:
        raise ValueError("invalid shared task response/evaluation: " + "; ".join(errors))


def validate_task_response_contract(task: SharedTaskSpec) -> list[str]:
    """Preserve legacy response checks used by current Print and Learn callers."""
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
    """Legacy validation retained until Print/Learn caller cutover completes."""
    del bindings
    task_list = list(tasks)
    errors: list[str] = []
    by_block: dict[str, SharedTaskSpec] = {}
    for task in task_list:
        if task.teaching_plan_id != plan.teaching_plan_id:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_id")
        if task.teaching_plan_revision != plan.revision:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_revision")
        if task.teaching_plan_hash != teaching_plan_content_hash(plan):
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
        errors.append(
            f"shared task {by_block[block_id].id!r} targets unknown/non-response block {block_id!r}"
        )
    return errors


def validate_final_shared_tasks(
    plan: TeachingPlan,
    tasks: Iterable[SharedTaskSpec],
    *,
    sourcebook: LessonSourcebook | None = None,
    bindings: Iterable[TeachingContentBinding] = (),
) -> list[str]:
    task_list = list(tasks)
    errors: list[str] = []
    by_block: dict[str, SharedTaskSpec] = {}
    plan_id = str(plan.teaching_plan_id or "teaching-plan")
    plan_revision = int(plan.revision or 1)
    plan_hash = teaching_plan_content_hash(plan)
    blocks = {
        block.id: block
        for section in plan.sections
        for block in section.blocks
    }
    block_ids = [block.id for section in plan.sections for block in section.blocks]
    if len(block_ids) != len(set(block_ids)):
        errors.append("Teaching Plan block ids must be unique for shared task ownership")
    for task in task_list:
        if task.teaching_plan_id != plan_id:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_id")
        if task.teaching_plan_revision != plan_revision:
            errors.append(f"task {task.id!r} has the wrong teaching_plan_revision")
        if task.teaching_plan_hash != plan_hash:
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
        errors.extend(validate_final_task_response_contract(task))
        if sourcebook is not None:
            sourcebook_ids = [entry.id for entry in sourcebook.entries]
            if len(sourcebook_ids) != len(set(sourcebook_ids)):
                errors.append("sourcebook entry ids must be unique")
            missing = sorted(set(task.sourcebook_refs) - set(sourcebook.by_id()))
            if missing:
                errors.append(f"task {task.id!r} references unknown sourcebook entries {missing}")
            if sourcebook.teaching_plan_id != plan_id:
                errors.append("sourcebook has the wrong teaching_plan_id")
            if sourcebook.teaching_plan_revision != plan_revision:
                errors.append("sourcebook has the wrong teaching_plan_revision")
            if sourcebook.teaching_plan_hash != plan_hash:
                errors.append("sourcebook has the wrong teaching_plan_hash")
        block = blocks.get(task.teaching_block_id)
        if block is not None:
            if task.id != f"task-{block.id}":
                errors.append(f"task for block {block.id!r} has a non-canonical id")
            learner_action = block.learner_action
            if learner_action is not None:
                if task.action != learner_action.action:
                    errors.append(f"task {task.id!r} has the wrong learner action for block {block.id!r}")
                if task.purpose != learner_action.purpose:
                    errors.append(f"task {task.id!r} has the wrong purpose for block {block.id!r}")
                if task.expected_evidence != learner_action.expected_evidence:
                    errors.append(f"task {task.id!r} has the wrong expected_evidence for block {block.id!r}")
                if task.difficulty != learner_action.difficulty:
                    errors.append(f"task {task.id!r} has the wrong difficulty for block {block.id!r}")
            expected_mode = "assessment" if block.task_mode == "assessment" or block.source_question_ids else "formative"
            if task.mode != expected_mode:
                errors.append(f"task {task.id!r} has the wrong mode for block {block.id!r}")
            if task.sourcebook_refs != block.sourcebook_refs:
                errors.append(f"task {task.id!r} has the wrong sourcebook_refs for block {block.id!r}")
            if task.approved_source_ids != block.source_question_ids:
                errors.append(f"task {task.id!r} has the wrong approved_source_ids for block {block.id!r}")
    response_blocks: dict[str, object] = {}
    for section in plan.sections:
        for block in section.blocks:
            action = block.learner_action.action if block.learner_action else None
            if action and response_bearing_action(action):
                response_blocks[block.id] = block
                if block.id not in by_block:
                    errors.append(f"response-bearing block {block.id!r} has no SharedTaskSpec")
            elif action in PASSIVE_ACTION_MEANINGS:
                if block.id in by_block:
                    errors.append(f"passive block {block.id!r} cannot own a SharedTaskSpec")
            elif action is not None:
                errors.append(f"block {block.id!r} has an action with no shared-task meaning")
            elif block.id in by_block:
                errors.append(f"block {block.id!r} without a learner action cannot own a SharedTaskSpec")
    unknown_blocks = sorted(set(by_block) - set(response_blocks))
    for block_id in unknown_blocks:
        errors.append(f"shared task {by_block[block_id].id!r} targets unknown/non-response block {block_id!r}")
    binding_list = list(bindings)
    if binding_list:
        by_binding: dict[str, TeachingContentBinding] = {}
        for binding in binding_list:
            if binding.teaching_block_id in by_binding:
                errors.append(f"duplicate binding for teaching block {binding.teaching_block_id!r}")
            by_binding[binding.teaching_block_id] = binding
            if binding.teaching_plan_id != plan_id:
                errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_id")
            if binding.teaching_plan_revision != plan_revision:
                errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_revision")
            if binding.teaching_plan_hash != plan_hash:
                errors.append(f"binding {binding.teaching_block_id!r} has the wrong teaching_plan_hash")
            bound_block = blocks.get(binding.teaching_block_id)
            if bound_block is None:
                errors.append(f"binding targets unknown teaching block {binding.teaching_block_id!r}")
                continue
            if binding.sourcebook_refs != bound_block.sourcebook_refs:
                errors.append(f"binding {binding.teaching_block_id!r} has the wrong sourcebook_refs")
            expected_task_id = by_block[binding.teaching_block_id].id if binding.teaching_block_id in by_block else None
            if binding.shared_task_id != expected_task_id:
                errors.append(f"binding {binding.teaching_block_id!r} has the wrong shared_task_id")
        missing_bindings = sorted(set(blocks) - set(by_binding))
        if missing_bindings:
            errors.append(f"missing TeachingContentBinding for blocks {missing_bindings}")
    return errors


def finalize_shared_tasks(
    plan: TeachingPlan,
    tasks: Iterable[SharedTaskSpec],
    *,
    sourcebook: LessonSourcebook | None = None,
    bindings: Iterable[TeachingContentBinding] = (),
) -> list[SharedTaskSpec]:
    """Return tasks only after complete plan, source and response validation.

    New finalized SharedDocument paths should call this before READY. Legacy
    registries remain permissive until their Learn/Print callers are cut over.
    """
    task_list = list(tasks)
    errors = validate_final_shared_tasks(
        plan,
        task_list,
        sourcebook=sourcebook,
        bindings=bindings,
    )
    if sourcebook is None and any(
        block.sourcebook_refs
        for section in plan.sections
        for block in section.blocks
    ):
        errors.append("shared task finalization requires the referenced LessonSourcebook")
    if errors:
        raise ValueError("shared task finalization failed: " + "; ".join(errors))
    return task_list


def assert_task_preserved(realized: Mapping[str, object], task: SharedTaskSpec) -> None:
    """Fail closed when a path realization changes shared task semantics."""
    prompt = realized.get("prompt")
    if prompt is not None and str(prompt).strip() != task.prompt.strip():
        raise ValueError(f"realized task {task.id!r} changed prompt meaning")
    evaluation = realized.get("evaluation")
    if evaluation is not None and evaluation != task.evaluation:
        raise ValueError(f"realized task {task.id!r} changed evaluation ownership")
    response = realized.get("response")
    if response is not None and response != task.response:
        raise ValueError(f"realized task {task.id!r} changed response semantics")
    action = realized.get("action")
    if action is not None and action != task.action:
        raise ValueError(f"realized task {task.id!r} changed learner action")


__all__ = [
    "assert_task_preserved",
    "assert_task_response_contract",
    "finalize_shared_tasks",
    "validate_final_shared_tasks",
    "validate_final_task_response_contract",
    "validate_shared_tasks",
    "validate_task_response_contract",
]

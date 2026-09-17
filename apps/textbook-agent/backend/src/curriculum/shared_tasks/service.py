"""Shared task registry construction and semantic path-realization helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock

from .models import SharedTaskSpec


def teaching_plan_hash(plan: TeachingPlan) -> str:
    if plan.preparation_hash:
        return plan.preparation_hash
    raw = json.dumps(plan.model_dump(mode="json", exclude_none=True), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _response_contract(action: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    mapping = {
        "select-one": "single_choice",
        "select-many": "multiple_choice",
        "complete-missing-values": "missing_values",
        "classify-items": "classification",
        "match-pairs": "matching",
        "order-items": "ordered_items",
        "reconstruct-order": "ordered_items",
        "enter-number": "number",
        "enter-text": "text",
    }
    response_type = mapping.get(action)
    if response_type is None:
        raise ValueError(f"no response contract for learner action {action!r}")
    response: dict[str, Any] = {"type": response_type}
    evaluation: dict[str, Any] = {"type": "rubric", "criteria": []}
    return response_type, response, evaluation


def shared_task_for_block(
    plan: TeachingPlan,
    block: TeachingPlanBlock,
    *,
    approved_items: Mapping[str, Any] | None = None,
) -> SharedTaskSpec:
    if block.learner_action is None:
        raise ValueError(f"block {block.id!r} has no learner action")
    action = str(block.learner_action.action)
    _response_type, response, evaluation = _response_contract(action)
    approved_items = approved_items or {}
    is_assessment = block.task_mode == "assessment" or bool(block.source_question_ids)
    if is_assessment:
        if not block.source_question_ids:
            raise ValueError(f"assessment block {block.id!r} has no approved source")
        source = approved_items.get(block.source_question_ids[0])
        if source is not None:
            source_map = dict(source) if isinstance(source, Mapping) else vars(source)
            prompt = str(
                source_map.get("prompt") or source_map.get("stem") or block.brief
            )
            options = source_map.get("options")
            if options:
                response["options"] = options
            evaluation = dict(source_map.get("evaluation") or {})
            if not evaluation and source_map.get("correct_key"):
                evaluation = {"type": "choice_keys", "correct": [source_map["correct_key"]]}
        else:
            prompt = block.brief
    else:
        prompt = block.brief
        evaluation["criteria"] = [block.learner_action.expected_evidence]
    return SharedTaskSpec(
        id=f"task-{block.id}",
        teaching_plan_id=str(plan.teaching_plan_id or "teaching-plan"),
        teaching_plan_revision=int(plan.revision or 1),
        teaching_plan_hash=teaching_plan_hash(plan),
        teaching_block_id=block.id,
        mode="assessment" if is_assessment else "formative",
        action=block.learner_action.action,
        purpose=block.learner_action.purpose,
        prompt=prompt,
        difficulty=block.learner_action.difficulty,
        sourcebook_refs=list(block.sourcebook_refs),
        expected_evidence=block.learner_action.expected_evidence,
        response=response,
        evaluation=evaluation,
        approved_source_ids=list(block.source_question_ids),
    )


def build_shared_task_registry(
    plan: TeachingPlan,
    *,
    approved_items: Mapping[str, Any] | None = None,
) -> list[SharedTaskSpec]:
    tasks: list[SharedTaskSpec] = []
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action is None:
                continue
            action = str(block.learner_action.action)
            if action in {"compare-without-response", "read-explanation"}:
                continue
            tasks.append(shared_task_for_block(plan, block, approved_items=approved_items))
    return tasks


__all__ = ["build_shared_task_registry", "shared_task_for_block", "teaching_plan_hash"]

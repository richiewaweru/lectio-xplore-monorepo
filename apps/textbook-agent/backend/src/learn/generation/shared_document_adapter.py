"""Pure Learn realization of a verified SharedLessonDocument.

Ordinary learner-facing content is copied from the immutable shared artifact.
Task anchors are lowered through closed, deterministic mappings to the
existing Learn interaction contract; this module never authors content.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from curriculum.shared_tasks.models import ACTION_RESPONSE_TYPES, SharedTaskSpec
from curriculum.shared_tasks.validation import assert_task_response_contract
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import (
    CalloutNode as SharedCalloutNode,
    CompareNode as SharedCompareNode,
    EquationNode as SharedEquationNode,
)
from document.shared_lesson.models import (
    FigureNode as SharedFigureNode,
)
from document.shared_lesson.models import (
    HeadingNode as SharedHeadingNode,
)
from document.shared_lesson.models import (
    ListNode as SharedListNode,
)
from document.shared_lesson.models import (
    ParagraphNode as SharedParagraphNode,
)
from document.shared_lesson.models import (
    SharedLessonDocument,
    TaskAnchor,
    QuoteNode as SharedQuoteNode,
)
from document.shared_lesson.models import (
    TableNode as SharedTableNode,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.contracts.lesson_document import LearnDocument, assert_valid_learn_document
from learn.generation.assemble import assemble_learn_document


class SharedDocumentLearnMappingError(ValueError):
    """A shared task cannot be expressed by an existing Learn interaction."""


@dataclass(frozen=True)
class SharedDocumentIdentity:
    id: str
    revision: int
    content_hash: str


@dataclass(frozen=True)
class SharedDocumentLearnRealization:
    source_identity: SharedDocumentIdentity
    document: LearnDocument


_DEFAULT_FEEDBACK = {"correct": "Correct.", "incorrect": "Not yet — try again."}
_DEFAULT_ATTEMPT_POLICY = {
    "max_attempts": None,
    "show_feedback_after_submit": True,
    "allow_retry_after_correct": True,
}
_DEFAULT_COMPLETION = {"type": "submitted"}

_INTERACTION_KINDS = {
    "single_choice": "choice",
    "multiple_choice": "multi-select",
    "number": "numeric",
    "text": "short-response",
    "missing_values": "fill-blank",
    "classification": "classify",
    "matching": "match-pairs",
    "ordered_items": "sequence",
}


def _mapping(value: Any, *, field: str, task_id: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SharedDocumentLearnMappingError(f"task {task_id!r} has invalid {field}")
    return value


def _choice_correct_id(evaluation: Mapping[str, Any], *, task_id: str) -> str:
    value = evaluation.get("correct_option_id") or evaluation.get("correct_key")
    if not value:
        many = evaluation.get("correct_option_ids", evaluation.get("correct_keys"))
        if many is None:
            many = evaluation.get("correct")
        if isinstance(many, list) and len(many) == 1:
            value = many[0]
    if not isinstance(value, str) or not value.strip():
        raise SharedDocumentLearnMappingError(
            f"task {task_id!r} has no single-choice Learn answer key"
        )
    return value


def _choice_correct_ids(evaluation: Mapping[str, Any], *, task_id: str) -> list[str]:
    values = evaluation.get("correct_option_ids", evaluation.get("correct_keys"))
    if values is None:
        values = evaluation.get("correct")
    if values is None:
        one = evaluation.get("correct_option_id", evaluation.get("correct_key"))
        values = [one] if isinstance(one, str) else None
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(item, str) or not item.strip() for item in values)
    ):
        raise SharedDocumentLearnMappingError(
            f"task {task_id!r} has no multiple-choice Learn answer keys"
        )
    return list(values)


def _learn_config(task: SharedTaskSpec, interaction_kind: str) -> dict[str, Any]:
    response = _mapping(task.response, field="response", task_id=task.id)
    evaluation = _mapping(task.evaluation, field="evaluation", task_id=task.id)
    evaluation_type = str(evaluation.get("type") or "")

    if interaction_kind == "choice":
        config = {
            "options": response.get("options", []),
        }
        if "answer_lines" in response:
            config["answer_lines"] = response["answer_lines"]
        config["correct_option_id"] = _choice_correct_id(evaluation, task_id=task.id)
        return config
    if interaction_kind == "multi-select":
        config = {
            "options": response.get("options", []),
            "correct_option_ids": _choice_correct_ids(evaluation, task_id=task.id),
        }
        if "answer_lines" in response:
            config["answer_lines"] = response["answer_lines"]
        return config
    if interaction_kind == "fill-blank":
        response_answers = response.get("values", response.get("answers"))
        if evaluation_type == "accepted_answers":
            answers = evaluation.get("accepted_answers")
        elif evaluation_type == "exact_match":
            answers = evaluation.get("answer", evaluation.get("correct_value"))
        else:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} evaluation is not supported by Learn fill-blank interaction"
            )
        if answers is None or answers != response_answers:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} fill-blank answers cannot be represented exactly in Learn"
            )
        return {
            "answers": answers,
            "answer_lines": response.get("answer_lines"),
            "case_sensitive": evaluation.get("case_sensitive", False),
        }
    if interaction_kind == "numeric":
        if evaluation_type == "numeric":
            value = evaluation.get("value")
            tolerance = evaluation.get("tolerance")
            unit = evaluation.get("unit")
        elif evaluation_type == "exact_match":
            value = evaluation.get("answer", evaluation.get("correct_value"))
            tolerance = 0
            unit = response.get("unit")
        else:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} evaluation is not supported by Learn numeric interaction"
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SharedDocumentLearnMappingError(f"task {task.id!r} has no numeric Learn answer")
        return {
            "value": value,
            "tolerance": tolerance,
            "unit": unit,
            **{
                key: response[key]
                for key in ("min", "max", "step", "precision", "answer_lines")
                if key in response
            },
        }
    if interaction_kind == "short-response":
        if evaluation_type == "rubric":
            criteria = evaluation.get("criteria") or evaluation.get("rubric")
            if isinstance(criteria, str):
                if not criteria.strip():
                    raise SharedDocumentLearnMappingError(
                        f"task {task.id!r} rubric evaluation requires non-empty text criteria"
                    )
                preserved_criteria: str | list[str] = criteria
                guidance = criteria
            elif isinstance(criteria, list) and criteria and all(
                isinstance(item, str) and item.strip() for item in criteria
            ):
                preserved_criteria = list(criteria)
                guidance = "Review the learner response against these rubric criteria:\n" + "\n".join(
                    f"- {criterion}" for criterion in preserved_criteria
                )
            else:
                raise SharedDocumentLearnMappingError(
                    f"task {task.id!r} rubric evaluation requires non-empty text criteria"
                )
            return {
                "evaluation": "teacher-review",
                "review_guidance": guidance,
                "rubric_criteria": preserved_criteria,
            }
        if evaluation_type == "teacher_review":
            return {
                "evaluation": "teacher-review",
                "review_guidance": evaluation.get("review_guidance"),
            }
        if evaluation_type == "accepted_answers":
            answers = evaluation.get("accepted_answers")
        elif evaluation_type == "exact_match":
            answer = evaluation.get("answer", evaluation.get("correct_value"))
            answers = [answer] if isinstance(answer, str) else None
        else:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} evaluation is not supported by Learn text interaction"
            )
        if not isinstance(answers, list) or not answers:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} has no Learn accepted-answer set"
            )
        return {
            "evaluation": "accepted-answers",
            "accepted_answers": answers,
            "case_sensitive": evaluation.get("case_sensitive", False),
            **{
                key: response[key]
                for key in ("min_length", "max_length", "placeholder", "answer_lines")
                if key in response
            },
        }
    if interaction_kind == "classify":
        placements = response.get("correct_placements")
        items = response.get("items")
        categories = response.get("categories")
        if (
            evaluation_type != "mapping"
            or not isinstance(placements, Mapping)
            or not isinstance(items, list)
            or not isinstance(categories, list)
        ):
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} classification data cannot be mapped to Learn"
            )
        return {
            "items": items,
            "categories": [{"id": item, "label": item} for item in categories],
            "pairs": [{"left": item, "right": placements[item]} for item in items],
        }
    if interaction_kind == "match-pairs":
        pairs = response.get("pairs")
        evaluation_pairs = evaluation.get("pairs", evaluation.get("correct_pairs"))
        if evaluation_type == "exact_match":
            evaluation_pairs = evaluation.get("answer", evaluation.get("correct_value"))
        if (
            not isinstance(pairs, list)
            or evaluation_type not in {"mapping", "exact_match"}
            or evaluation_pairs != pairs
        ):
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} matching evaluation cannot be mapped to Learn"
            )
        return {"pairs": pairs}
    if interaction_kind == "sequence":
        if evaluation_type not in {"ordered_match", "exact_match"}:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} ordering evaluation cannot be mapped to Learn"
            )
        order = evaluation.get("correct_order", evaluation.get("order"))
        if order is None and evaluation_type == "exact_match":
            order = evaluation.get("answer", evaluation.get("correct_value"))
        if not isinstance(order, list) or not order:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} has no Learn expected ordering"
            )
        response_order = response.get("correct_order", response.get("order"))
        if response_order != order:
            raise SharedDocumentLearnMappingError(
                f"task {task.id!r} expected ordering cannot be represented exactly in Learn"
            )
        return {"items": response.get("items", order), "order": order}
    raise SharedDocumentLearnMappingError(
        f"task {task.id!r} action has no existing Learn interaction mapping"
    )


def _task_contract(
    task: SharedTaskSpec, anchor: TaskAnchor, source: SharedDocumentIdentity
) -> dict[str, Any]:
    try:
        assert_task_response_contract(task)
    except ValueError as exc:
        raise SharedDocumentLearnMappingError(
            f"task {task.id!r} fails the shared response/evaluation contract"
        ) from exc
    response_type = str(task.response.get("type") or "")
    expected_type = ACTION_RESPONSE_TYPES.get(task.action)
    if response_type != expected_type:
        raise SharedDocumentLearnMappingError(
            f"task {task.id!r} action and response do not have a Learn mapping"
        )
    interaction_kind = _INTERACTION_KINDS.get(response_type)
    if interaction_kind is None:
        raise SharedDocumentLearnMappingError(
            f"task {task.id!r} action has no existing Learn interaction mapping"
        )
    config = _learn_config(task, interaction_kind)
    contract = {
        "id": anchor.id,
        "kind": interaction_kind,
        "prompt": task.prompt,
        "config": config,
        "feedback": dict(task.feedback) if task.role is not None and task.feedback else dict(_DEFAULT_FEEDBACK),
        "assessment_mode": "graded" if task.mode == "assessment" else "practice",
        "attempt_policy": dict(_DEFAULT_ATTEMPT_POLICY),
        "completion": dict(_DEFAULT_COMPLETION),
        "ai_config_rule": "config-only",
        "teaching_block_id": task.teaching_block_id,
        "shared_task": {
            "id": task.id,
            "action": task.action,
            "mode": task.mode,
            "purpose": task.purpose,
            "prompt": task.prompt,
            "difficulty": task.difficulty,
            "expected_evidence": task.expected_evidence,
            "response": task.response,
            "evaluation": task.evaluation,
            "sourcebook_refs": list(task.sourcebook_refs),
            "approved_source_ids": list(task.approved_source_ids),
            "teaching_plan_id": task.teaching_plan_id,
            "teaching_plan_revision": task.teaching_plan_revision,
            "teaching_plan_hash": task.teaching_plan_hash,
        },
        "source_document": {
            "id": source.id,
            "revision": source.revision,
            "content_hash": source.content_hash,
        },
    }
    # These fields are authored task presentation semantics.  They are copied
    # through for Learn consumers while legacy tasks keep their old omission
    # behavior through the conditional entries below.
    if task.role is not None:
        contract["role"] = task.role
        contract["shared_task"]["role"] = task.role
    if task.display_prompt is not None:
        contract["display_prompt"] = task.display_prompt
        contract["shared_task"]["display_prompt"] = task.display_prompt
    if task.option_notes is not None:
        contract["option_notes"] = dict(task.option_notes)
        contract["shared_task"]["option_notes"] = dict(task.option_notes)
    return contract


def _ordinary_node(node: Any) -> dict[str, Any]:
    base = {"id": node.id, "kind": node.kind, "teaching_block_id": node.teaching_block_id}
    if isinstance(node, SharedParagraphNode):
        return {**base, "text": node.display.text}
    if isinstance(node, SharedHeadingNode):
        return {**base, "text": node.display.text, "level": node.display.level}
    if isinstance(node, SharedListNode):
        return {**base, "ordered": node.display.ordered, "items": list(node.display.items)}
    if isinstance(node, SharedFigureNode):
        return {
            **base,
            "asset_id": node.display.asset_id,
            "caption": node.display.caption,
            # Learn has no media path, so alt text is usually empty; fall back
            # to the caption rather than shipping an unlabelled figure.
            "alt": node.accessibility.alt_text.strip() or node.display.caption,
        }
    if isinstance(node, SharedTableNode):
        return {
            **base,
            "headers": list(node.display.headers),
            "rows": [list(row) for row in node.display.rows],
            "caption": node.display.caption,
        }
    if isinstance(node, SharedCalloutNode):
        result = {
            **base,
            "tone": node.display.tone,
            "title": node.display.title,
        }
        for field in ("body", "variant", "belief", "evidence", "conclusion", "aside"):
            value = getattr(node.display, field)
            if value is not None:
                result[field] = value
        return result
    if isinstance(node, SharedEquationNode):
        result = {
            **base,
            "inputs": list(node.display.inputs),
            "outputs": list(node.display.outputs),
        }
        if node.display.label is not None:
            result["label"] = node.display.label
        if node.display.condition is not None:
            result["condition"] = node.display.condition
        return result
    if isinstance(node, SharedQuoteNode):
        result = {**base, "text": node.display.text}
        if node.display.attribution is not None:
            result["attribution"] = node.display.attribution
        return result
    if isinstance(node, SharedCompareNode):
        return {
            **base,
            "items": [item.model_dump(mode="json") for item in node.display.items],
        }
    raise SharedDocumentLearnMappingError(
        f"shared node {getattr(node, 'id', '<unknown>')!r} has no Learn primitive mapping"
    )


def realize_shared_document_for_learn(
    stored: StoredSharedLessonDocument,
    *,
    expected_identity: SharedDocumentIdentity,
    subject: str,
    source_generation_id: str | None = None,
    learn_document_id: str | None = None,
) -> SharedDocumentLearnRealization:
    """Copy one exact READY shared artifact into the existing LearnDocument v2.

    The caller supplies the immutable identity pinned by Learn admission. This
    adapter rechecks READY status, identity, storage hash, and the recomputed
    SharedLessonDocument hash before constructing any Learn nodes.
    """
    if stored.status != "ready":
        raise SharedDocumentLearnMappingError("only a READY SharedLessonDocument can enter Learn")
    document = stored.document
    try:
        normalized = SharedLessonDocument.model_validate(
            document.model_dump(mode="json"),
            context={"skip_content_hash_validation": True},
        )
    except Exception as exc:  # turn malformed persisted data into a closed failure
        raise SharedDocumentLearnMappingError("shared document failed contract validation") from exc
    actual_hash = shared_lesson_content_hash(normalized)
    actual_identity = SharedDocumentIdentity(
        id=normalized.id,
        revision=normalized.revision,
        content_hash=actual_hash,
    )
    if actual_hash != normalized.content_hash:
        raise SharedDocumentLearnMappingError("shared document content hash is stale")
    if actual_identity != expected_identity:
        raise SharedDocumentLearnMappingError(
            "shared document ID, revision, or content hash differs from Learn admission"
        )
    if content_hash(normalized.model_dump(mode="json")) != stored.storage_hash:
        raise SharedDocumentLearnMappingError("shared document storage hash is stale")

    tasks_by_id = {task.id: task for task in normalized.tasks}
    nodes: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    for section in normalized.sections:
        section_node_ids: list[str] = []
        for shared_node in section.nodes:
            if isinstance(shared_node, TaskAnchor):
                task = tasks_by_id.get(shared_node.task_spec_id)
                if task is None or task.teaching_block_id != shared_node.teaching_block_id:
                    raise SharedDocumentLearnMappingError(
                        f"task anchor {shared_node.id!r} is not bound to its SharedTaskSpec"
                    )
                contract = _task_contract(task, shared_node, actual_identity)
                learn_node = {
                    "id": shared_node.id,
                    "kind": "interaction",
                    "interaction_type": contract["kind"],
                    "teaching_block_id": shared_node.teaching_block_id,
                    "prompt": task.prompt,
                    "config": contract["config"],
                    "feedback": contract["feedback"],
                    "assessment_mode": contract["assessment_mode"],
                    "attempt_policy": contract["attempt_policy"],
                    "completion": contract["completion"],
                    "contract": contract,
                }
                for field in ("role", "display_prompt", "option_notes"):
                    if field in contract:
                        learn_node[field] = contract[field]
            else:
                learn_node = _ordinary_node(shared_node)
            nodes.append(learn_node)
            section_node_ids.append(str(learn_node["id"]))
        sections.append(
            {
                "id": section.id,
                "title": section.title,
                "position": section.position,
                "node_ids": section_node_ids,
            }
        )

    document_id = learn_document_id or f"shared-{normalized.id}-r{normalized.revision}"
    learn_payload = assemble_learn_document(
        nodes,
        {
            "id": document_id,
            "title": normalized.title,
            "subject": subject,
            "source": "shared_document",
            "source_generation_id": source_generation_id,
            "created_at": normalized.created_at.isoformat(),
            "updated_at": normalized.created_at.isoformat(),
            "teaching_plan_id": normalized.teaching_plan_id,
            "teaching_plan_revision": normalized.teaching_plan_revision,
            "sections": sections,
        },
    )
    learn_document = assert_valid_learn_document(learn_payload)
    return SharedDocumentLearnRealization(
        source_identity=actual_identity,
        document=learn_document,
    )


__all__ = [
    "SharedDocumentIdentity",
    "SharedDocumentLearnMappingError",
    "SharedDocumentLearnRealization",
    "realize_shared_document_for_learn",
]

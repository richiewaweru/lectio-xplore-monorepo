"""Pure Print realization of an immutable SharedLessonDocument."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.validation import assert_task_response_contract
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.media import FigureMediaResult, SharedFigureMediaError, verify_bound_figure_media
from document.shared_lesson.models import (
    CalloutNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    SharedLessonDocument,
    TableNode,
    TaskAnchor,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from print.contracts.lectio_page import validate_document
from print.generation.task_treatments import print_treatment_for_learner_action
from print.rendering.page_objects.document_assembly import build_answer_key_block
from print.rendering.page_objects.validation import validate_answer_key_integrity


class SharedDocumentPrintMappingError(ValueError):
    """A shared lesson cannot be represented truthfully by the current Print contract."""


@dataclass(frozen=True)
class SharedDocumentIdentity:
    id: str
    revision: int
    content_hash: str


@dataclass(frozen=True)
class SharedDocumentPrintRealization:
    source_identity: SharedDocumentIdentity
    document: dict[str, Any]


def _human_label(index: int, *, prefix: str) -> str:
    """Return stable learner-facing labels without exposing source task IDs."""
    return f"{prefix}{index}"


def _object_block(node_id: str, position: int, object_id: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "object": object_id,
        "intent": "check-understanding" if object_id in {"questions", "choices"} else "explain",
        "position": position,
        "content": content,
    }


_USABLE_MEDIA_STATUSES = frozenset({"ready", "ready_with_quality_warning"})


def _ordinary_block(node: Any, position: int, media_by_figure: Mapping[str, FigureMediaResult]) -> dict[str, Any]:
    if isinstance(node, ParagraphNode):
        return _object_block(node.id, position, "prose", {"paragraphs": [node.display.text]})
    if isinstance(node, HeadingNode):
        return {
            "id": node.id,
            "object": "heading",
            "position": position,
            "content": {"text": node.display.text, "level": node.display.level},
        }
    if isinstance(node, ListNode):
        return _object_block(
            node.id,
            position,
            "list",
            {
                "style": "ordered" if node.display.ordered else "unordered",
                "items": [{"text": item} for item in node.display.items],
            },
        )
    if isinstance(node, FigureNode):
        media = media_by_figure.get(node.id)
        if media is None:
            raise SharedDocumentPrintMappingError(
                f"required figure {node.id!r} has no document-bound Print media"
            )
        return _object_block(
            node.id,
            position,
            "figure",
            {
                "asset": {"kind": "image", "status": "ready", "src": media.asset_url},
                "alt_text": node.accessibility.alt_text,
                **({"caption": node.display.caption} if node.display.caption else {}),
            },
        )
    if isinstance(node, TableNode):
        if not node.display.headers or any(len(row) != len(node.display.headers) for row in node.display.rows):
            raise SharedDocumentPrintMappingError(f"table {node.id!r} has inconsistent columns")
        return _object_block(
            node.id,
            position,
            "table",
            {
                "columns": [
                    {"id": f"column-{index + 1}", "label": label}
                    for index, label in enumerate(node.display.headers)
                ],
                "rows": [
                    {"cells": {f"column-{index + 1}": value for index, value in enumerate(row)}}
                    for row in node.display.rows
                ],
                **({"caption": node.display.caption} if node.display.caption else {}),
            },
        )
    if isinstance(node, CalloutNode):
        body = f"{node.display.title}\n{node.display.body}" if node.display.title else node.display.body
        return _object_block(node.id, position, "aside", {"body": body, "label": node.display.tone})
    raise SharedDocumentPrintMappingError(
        f"shared node {getattr(node, 'id', '<unknown>')!r} has no Print primitive mapping"
    )


def _mapping(value: Any, *, field: str, task: SharedTaskSpec) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SharedDocumentPrintMappingError(f"task {task.id!r} has invalid {field}")
    return value


def _single_choice_answer(task: SharedTaskSpec, labels: Mapping[str, str]) -> str:
    evaluation = _mapping(task.evaluation, field="evaluation", task=task)
    value = evaluation.get("correct_option_id", evaluation.get("correct_key"))
    if value is None:
        keys = evaluation.get("correct_option_ids", evaluation.get("correct_keys", evaluation.get("correct")))
        if isinstance(keys, list) and len(keys) == 1:
            value = keys[0]
    if not isinstance(value, str) or value not in labels:
        raise SharedDocumentPrintMappingError(f"task {task.id!r} has no valid Print choice answer")
    return labels[value]


def _choice_task(task: SharedTaskSpec) -> tuple[dict[str, Any], str]:
    response = _mapping(task.response, field="response", task=task)
    options = response.get("options")
    if not isinstance(options, list) or len(options) < 2:
        raise SharedDocumentPrintMappingError(f"task {task.id!r} needs at least two choice options")
    labels: dict[str, str] = {}
    paper_options: list[dict[str, str]] = []
    for index, option in enumerate(options):
        if not isinstance(option, Mapping):
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has a malformed choice option")
        option_id = str(option.get("id") or "")
        text = str(option.get("text") or "")
        if not option_id or not text.strip() or option_id in labels:
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has invalid or duplicate choice options")
        # Paper choices use A, B, …, AA; these are the answer labels shown to learners.
        n = index + 1
        letters = ""
        while n:
            n, remainder = divmod(n - 1, 26)
            letters = chr(65 + remainder) + letters
        label = letters
        labels[option_id] = label
        paper_options.append({"letter": label, "text": text})

    evaluation = _mapping(task.evaluation, field="evaluation", task=task)
    if task.action == "select-one":
        answer = _single_choice_answer(task, labels)
    else:
        raw = evaluation.get("correct_option_ids", evaluation.get("correct_keys", evaluation.get("correct")))
        if raw is None:
            one = evaluation.get("correct_option_id", evaluation.get("correct_key"))
            raw = [one] if isinstance(one, str) else None
        if not isinstance(raw, list) or not raw or any(not isinstance(key, str) or key not in labels for key in raw):
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has invalid Print choice answer labels")
        answer = ", ".join(labels[key] for key in raw)
    return {"stem": task.prompt, "options": paper_options}, answer


def _question_task(task: SharedTaskSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    response = _mapping(task.response, field="response", task=task)
    evaluation = _mapping(task.evaluation, field="evaluation", task=task)
    response_type = str(response.get("type") or "")
    prompt = task.prompt
    answer_lines = response.get("answer_lines")
    answer: str | None = None
    alternatives: list[str] = []
    rubric: str | None = None

    if response_type == "missing_values":
        values = response.get("values", response.get("answers"))
        if not isinstance(values, list) or not values:
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has no fill-in prompts")
        prompt += "\nComplete each value: " + ", ".join(str(value) for value in values)
        if evaluation.get("type") == "accepted_answers":
            accepted = evaluation.get("accepted_answers")
            if isinstance(accepted, list):
                answer = "; ".join(map(str, accepted))
        else:
            result = evaluation.get("answer", evaluation.get("correct_value"))
            if result is not None:
                answer = "; ".join(map(str, result)) if isinstance(result, list) else str(result)
    elif response_type == "classification":
        items, categories = response.get("items"), response.get("categories")
        placements = evaluation.get("correct_placements", response.get("correct_placements"))
        if not isinstance(items, list) or not isinstance(categories, list) or not isinstance(placements, Mapping):
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has invalid classification mapping")
        prompt += "\nClassify each item into one of these categories: " + ", ".join(map(str, categories))
        prompt += "\nItems: " + "; ".join(map(str, items))
        answer = "; ".join(f"{item}: {placements[item]}" for item in items if item in placements)
    elif response_type == "matching":
        pairs = response.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has no matching pairs")
        left: list[str] = []
        right: list[str] = []
        for pair in pairs:
            if not isinstance(pair, Mapping) or not pair.get("left") or not pair.get("right"):
                raise SharedDocumentPrintMappingError(f"task {task.id!r} has malformed matching pairs")
            left.append(str(pair["left"]))
            right.append(str(pair["right"]))
        prompt += "\nMatch each item to its pair. Items: " + "; ".join(left)
        prompt += "\nPossible matches: " + "; ".join(right)
        answer = "; ".join(f"{pair['left']}: {pair['right']}" for pair in pairs)
    elif response_type == "ordered_items":
        items = response.get("items")
        order = evaluation.get("correct_order", evaluation.get("order"))
        if order is None:
            order = evaluation.get("answer", evaluation.get("correct_value"))
        if not isinstance(items, list) or not items or not isinstance(order, list) or not order:
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has invalid ordering data")
        prompt += "\nPut these in order: " + "; ".join(map(str, items))
        answer = " → ".join(map(str, order))
    elif response_type == "number":
        unit = response.get("unit") or evaluation.get("unit")
        if unit:
            prompt += f"\nGive your answer in {unit}."
        value = evaluation.get("value", evaluation.get("answer", evaluation.get("correct_value")))
        if value is not None:
            tolerance = evaluation.get("tolerance")
            answer = str(value)
            if tolerance not in (None, 0):
                answer += f" ± {tolerance}"
            if unit:
                answer += f" {unit}"
    elif response_type == "text":
        if evaluation.get("type") == "accepted_answers":
            accepted = evaluation.get("accepted_answers")
            if isinstance(accepted, list) and accepted:
                answer = str(accepted[0])
                alternatives = [str(value) for value in accepted[1:]]
        elif evaluation.get("type") == "exact_match":
            value = evaluation.get("answer", evaluation.get("correct_value"))
            if value is not None:
                answer = str(value)
        if answer is None:
            rubric_items = evaluation.get("criteria", evaluation.get("rubric"))
            rubric = "; ".join(map(str, rubric_items)) if isinstance(rubric_items, list) else str(rubric_items or task.expected_evidence)
            answer = task.expected_evidence
    else:
        raise SharedDocumentPrintMappingError(f"task {task.id!r} response has no Print question mapping")

    if not answer:
        rubric_items = evaluation.get("criteria", evaluation.get("rubric"))
        if rubric_items:
            rubric = "; ".join(map(str, rubric_items)) if isinstance(rubric_items, list) else str(rubric_items)
            answer = task.expected_evidence
        else:
            raise SharedDocumentPrintMappingError(f"task {task.id!r} has no representable Print answer key")
    item: dict[str, Any] = {"id": "", "prompt": prompt}
    if answer_lines is not None:
        item["answer_lines"] = answer_lines
    entry: dict[str, Any] = {"answer": answer}
    if alternatives:
        entry["alternatives"] = alternatives
    if rubric:
        entry["rubric"] = rubric
    return item, entry


def _task_block(task: SharedTaskSpec, *, index: int, position: int, anchor: TaskAnchor) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        assert_task_response_contract(task)
    except ValueError as exc:
        raise SharedDocumentPrintMappingError(f"task {task.id!r} fails shared response/evaluation contract") from exc
    if task.teaching_block_id != anchor.teaching_block_id:
        raise SharedDocumentPrintMappingError(f"task anchor {anchor.id!r} is bound to a different teaching block")
    treatment = print_treatment_for_learner_action(task.action)
    if treatment not in {"choices", "questions"}:
        raise SharedDocumentPrintMappingError(f"task {task.id!r} has no closed Print paper treatment")

    label = _human_label(index, prefix="Q")
    if treatment == "choices":
        content, answer = _choice_task(task)
        block_id = _human_label(index, prefix="Choice-")
        block = _object_block(block_id, position, "choices", content)
    else:
        item, answer_entry = _question_task(task)
        item["id"] = label
        block_id = label
        block = _object_block(block_id, position, "questions", {"items": [item]})
        answer = answer_entry["answer"]

    entry: dict[str, Any] = {"question_id": block_id, "answer": answer}
    if treatment == "questions":
        entry.update({key: value for key, value in answer_entry.items() if key != "answer"})
    return block, {"label": label, "anchor_id": anchor.id, "task_spec_id": task.id, "answer_entry": entry}


def realize_shared_document_for_print(
    stored: StoredSharedLessonDocument,
    *,
    expected_identity: SharedDocumentIdentity,
    figure_media: Sequence[FigureMediaResult] = (),
    document_id: str | None = None,
) -> SharedDocumentPrintRealization:
    """Copy exact shared content into LectioDocumentV2 and lower task anchors."""
    if stored.status != "ready":
        raise SharedDocumentPrintMappingError("only a READY SharedLessonDocument can enter Print")
    try:
        normalized = SharedLessonDocument.model_validate(
            stored.document.model_dump(mode="json"),
            context={"skip_content_hash_validation": True},
        )
    except Exception as exc:
        raise SharedDocumentPrintMappingError("shared document failed contract validation") from exc
    actual_hash = shared_lesson_content_hash(normalized)
    actual_identity = SharedDocumentIdentity(normalized.id, normalized.revision, actual_hash)
    if actual_hash != normalized.content_hash:
        raise SharedDocumentPrintMappingError("shared document content hash is stale")
    if actual_identity != expected_identity:
        raise SharedDocumentPrintMappingError("shared document identity differs from Print admission")
    if content_hash(normalized.model_dump(mode="json")) != stored.storage_hash:
        raise SharedDocumentPrintMappingError("shared document storage hash is stale")

    media_by_figure: dict[str, FigureMediaResult] = {}
    for media in figure_media:
        if media.figure_node_id in media_by_figure:
            raise SharedDocumentPrintMappingError(f"duplicate media for figure {media.figure_node_id!r}")
        try:
            verified = verify_bound_figure_media(media, normalized)
        except SharedFigureMediaError as exc:
            raise SharedDocumentPrintMappingError(f"figure {media.figure_node_id!r} media binding failed") from exc
        # A produced image with a visual-QC quality warning is still a usable
        # asset (same rule as shared media binding); only its absence blocks.
        if verified.status not in _USABLE_MEDIA_STATUSES or not verified.asset_url.lower().startswith(
            ("http://", "https://")
        ):
            raise SharedDocumentPrintMappingError(f"figure {media.figure_node_id!r} media is not ready")
        media_by_figure[media.figure_node_id] = verified

    tasks_by_id = {task.id: task for task in normalized.tasks}
    task_label_index = 0
    sections: list[dict[str, Any]] = []
    answer_entries: list[dict[str, Any]] = []
    task_metadata: list[dict[str, str]] = []
    for section in normalized.sections:
        blocks: list[dict[str, Any]] = []
        for node in section.nodes:
            position = len(blocks)
            if isinstance(node, TaskAnchor):
                task = tasks_by_id.get(node.task_spec_id)
                if task is None:
                    raise SharedDocumentPrintMappingError(f"task anchor {node.id!r} has no SharedTaskSpec")
                task_label_index += 1
                block, metadata = _task_block(
                    task,
                    index=task_label_index,
                    position=position,
                    anchor=node,
                )
                blocks.append(block)
                answer_entries.append(metadata.pop("answer_entry"))
                task_metadata.append(metadata)
            else:
                blocks.append(_ordinary_block(node, position, media_by_figure))
        sections.append({"id": section.id, "title": section.title, "blocks": blocks})

    doc_id = document_id or f"print-{normalized.id}-r{normalized.revision}"
    result: dict[str, Any] = {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": doc_id,
        "title": normalized.title,
        "language": "en",
        "metadata": {
            "catalogue_version": "1.2.0",
            "resource_type": "lesson",
            "source_document": {
                "id": normalized.id,
                "revision": normalized.revision,
                "content_hash": actual_hash,
            },
            "shared_tasks": task_metadata,
        },
        "sections": sections,
    }
    if answer_entries:
        result["answer_key"] = build_answer_key_block(
            document_id=doc_id,
            answer_entries=answer_entries,
        )
        validate_answer_key_integrity(
            [block for section in sections for block in section["blocks"]],
            answer_entries,
        )
    errors = validate_document(result)
    if errors:
        raise SharedDocumentPrintMappingError(
            "realized Print document failed the existing LectioDocumentV2 contract: "
            + "; ".join(errors[:8])
        )
    return SharedDocumentPrintRealization(source_identity=actual_identity, document=result)


__all__ = [
    "SharedDocumentIdentity",
    "SharedDocumentPrintMappingError",
    "SharedDocumentPrintRealization",
    "realize_shared_document_for_print",
]

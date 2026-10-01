"""Pure proofs for immutable reviewer-created SharedLessonDocument revisions."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass

from pydantic import ValidationError

from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument


class ReviewRevisionValidationError(ValueError):
    """A reviewer revision changed content outside the allowlisted text fields."""


@dataclass(frozen=True)
class ReviewRevisionProof:
    """Verified origin-to-revision identity and revalidation targets."""

    document_id: str
    origin_revision: int
    origin_hash: str
    revision: int
    content_hash: str
    changed_section_ids: tuple[str, ...]
    figure_section_ids: tuple[str, ...]
    changed_task_ids: tuple[str, ...] = ()


def _verify_content_hash(document: SharedLessonDocument, label: str) -> str:
    digest = shared_lesson_content_hash(document)
    if digest != document.content_hash:
        raise ReviewRevisionValidationError(f"{label} content hash is stale")
    return digest


def _normalize(document: SharedLessonDocument, label: str) -> SharedLessonDocument:
    try:
        return SharedLessonDocument.model_validate(
            document.model_dump(mode="json"),
            context={"skip_content_hash_validation": True},
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ReviewRevisionValidationError(f"{label} document schema is invalid") from exc


def _same_except(left: dict, right: dict, allowed_paths: tuple[tuple[str | int, ...], ...]) -> bool:
    candidate = deepcopy(right)
    for path in allowed_paths:
        target_left = left
        target_right = candidate
        for part in path[:-1]:
            target_left = target_left[part]
            target_right = target_right[part]
        target_right[path[-1]] = deepcopy(target_left[path[-1]])
    return candidate == left


def _node_edit_paths(origin: dict, revised: dict) -> tuple[tuple[str | int, ...], ...]:
    kind = origin.get("kind")
    if kind in {"paragraph", "heading"}:
        return (("display", "text"), ("accessibility", "description"))
    if kind == "callout":
        return (
            ("display", "title"),
            ("display", "body"),
            ("accessibility", "description"),
        )
    if kind == "figure":
        return (("display", "caption"), ("accessibility", "alt_text"))
    if kind == "list":
        original_items = origin["display"]["items"]
        revised_items = revised["display"]["items"]
        if len(original_items) != len(revised_items):
            raise ReviewRevisionValidationError("review revision changed list shape")
        return (
            *(("display", "items", index) for index in range(len(original_items))),
            ("accessibility", "description"),
        )
    if kind == "table":
        original_rows = origin["display"]["rows"]
        revised_rows = revised["display"]["rows"]
        if len(original_rows) != len(revised_rows) or any(
            len(left) != len(right) for left, right in zip(original_rows, revised_rows, strict=True)
        ):
            raise ReviewRevisionValidationError("review revision changed table shape")
        return (
            *(
                ("display", "rows", row_index, column_index)
                for row_index, row in enumerate(original_rows)
                for column_index, _cell in enumerate(row)
            ),
            ("accessibility", "description"),
        )
    return ()


def _node_matches_review_contract(origin: dict, revised: dict) -> bool:
    if origin.get("kind") == "task_anchor":
        return origin == revised
    if origin.get("kind") != revised.get("kind"):
        return False
    paths = _node_edit_paths(origin, revised)
    return bool(paths) and _same_except(origin, revised, paths)


# Task wording a reviewer may correct. The answer key (``evaluation``) and every
# identity/lineage field stay frozen. Option text is editable only for
# id-keyed choice responses, where the evaluation references option ids rather
# than the displayed text; for matching/ordering/classification/missing-value
# responses the displayed text *is* the answer key, so those stay frozen.
_TEXT_EDITABLE_RESPONSE_TYPES = frozenset({"single_choice", "multiple_choice"})


def _same_shape_text_only(origin: object, revised: object) -> bool:
    """Equal structure; only non-empty string leaves may differ."""
    if isinstance(origin, dict):
        return (
            isinstance(revised, dict)
            and origin.keys() == revised.keys()
            and all(_same_shape_text_only(origin[key], revised[key]) for key in origin)
        )
    if isinstance(origin, list):
        return (
            isinstance(revised, list)
            and len(origin) == len(revised)
            and all(_same_shape_text_only(a, b) for a, b in zip(origin, revised, strict=True))
        )
    if isinstance(origin, str):
        return isinstance(revised, str) and (revised == origin or bool(revised.strip()))
    return origin == revised


def _response_matches_review_contract(origin: dict, revised: dict) -> bool:
    if origin.get("type") not in _TEXT_EDITABLE_RESPONSE_TYPES:
        return origin == revised
    if origin.keys() != revised.keys():
        return False
    for key in origin:
        if key != "options" and origin[key] != revised[key]:
            return False
    options, revised_options = origin.get("options"), revised.get("options")
    if not isinstance(options, list) or not isinstance(revised_options, list):
        return options == revised_options
    if len(options) != len(revised_options):
        return False
    for option, revised_option in zip(options, revised_options, strict=True):
        if not isinstance(option, dict) or not isinstance(revised_option, dict):
            return option == revised_option
        if option.keys() != revised_option.keys():
            return False
        for key in option:
            if key == "text":
                text = revised_option[key]
                if not isinstance(text, str) or not text.strip():
                    return False
            elif option[key] != revised_option[key]:
                return False
    return True


def _task_matches_review_contract(origin: dict, revised: dict) -> bool:
    if origin.keys() != revised.keys():
        return False
    for key in origin:
        if key in {"prompt", "response", "feedback"}:
            continue
        if origin[key] != revised[key]:
            return False
    prompt = revised.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return False
    if not _response_matches_review_contract(
        origin.get("response") or {}, revised.get("response") or {}
    ):
        return False
    return _same_shape_text_only(origin.get("feedback"), revised.get("feedback"))


def _changed_task_ids(
    origin: SharedLessonDocument, revised: SharedLessonDocument
) -> tuple[str, ...]:
    if len(origin.tasks) != len(revised.tasks):
        raise ReviewRevisionValidationError("review revision changed task count")
    changed: list[str] = []
    for original_task, revised_task in zip(origin.tasks, revised.tasks, strict=True):
        original_data = original_task.model_dump(mode="json")
        revised_data = revised_task.model_dump(mode="json")
        if original_data == revised_data:
            continue
        if not _task_matches_review_contract(original_data, revised_data):
            raise ReviewRevisionValidationError(
                f"review revision changed protected task fields for {original_task.id!r}"
            )
        changed.append(original_task.id)
    return tuple(changed)


def prove_review_draft_revision(
    origin: SharedLessonDocument,
    revised: SharedLessonDocument,
) -> ReviewRevisionProof:
    """Verify a saved edit revision changes only existing review API text fields.

    This proof intentionally does not establish deterministic/media/boundary or
    semantic QA. Consumers must re-run those gates before READY promotion.
    """
    if not isinstance(origin, SharedLessonDocument) or not isinstance(
        revised, SharedLessonDocument
    ):
        raise ReviewRevisionValidationError("review revision inputs must be validated documents")
    origin = _normalize(origin, "origin")
    revised = _normalize(revised, "review revision")
    origin_hash = _verify_content_hash(origin, "origin")
    revision_hash = _verify_content_hash(revised, "review revision")
    if origin.id != revised.id:
        raise ReviewRevisionValidationError("review revision changed document identity")
    if revised.revision != origin.revision + 1:
        raise ReviewRevisionValidationError("review revision number is not sequential")
    if (
        origin.teaching_plan_id,
        origin.teaching_plan_revision,
        origin.teaching_plan_hash,
        origin.schema_version,
        origin.title,
        origin.provenance,
        origin.created_at,
        origin.diagnostics,
    ) != (
        revised.teaching_plan_id,
        revised.teaching_plan_revision,
        revised.teaching_plan_hash,
        revised.schema_version,
        revised.title,
        revised.provenance,
        revised.created_at,
        revised.diagnostics,
    ):
        raise ReviewRevisionValidationError("review revision changed document or source lineage")
    if revision_hash == origin_hash:
        raise ReviewRevisionValidationError("review revision contains no content correction")
    changed_tasks = _changed_task_ids(origin, revised)
    if len(origin.sections) != len(revised.sections):
        raise ReviewRevisionValidationError("review revision changed section count")

    changed_sections: list[str] = []
    figure_sections: list[str] = []
    for original_section, revised_section in zip(origin.sections, revised.sections, strict=True):
        if (
            original_section.id,
            original_section.title,
            original_section.position,
            original_section.provenance,
        ) != (
            revised_section.id,
            revised_section.title,
            revised_section.position,
            revised_section.provenance,
        ):
            raise ReviewRevisionValidationError("review revision changed section identity or provenance")
        if len(original_section.nodes) != len(revised_section.nodes):
            raise ReviewRevisionValidationError("review revision changed node count")

        section_changed = False
        for original_node, revised_node in zip(
            original_section.nodes, revised_section.nodes, strict=True
        ):
            original_data = original_node.model_dump(mode="json")
            revised_data = revised_node.model_dump(mode="json")
            if (
                original_data.get("id") != revised_data.get("id")
                or original_data.get("teaching_block_id") != revised_data.get("teaching_block_id")
                or not _node_matches_review_contract(original_data, revised_data)
            ):
                raise ReviewRevisionValidationError(
                    f"review revision changed node identity, shape, or protected fields in section {original_section.id!r}"
                )
            section_changed = section_changed or original_data != revised_data

        if section_changed:
            changed_sections.append(original_section.id)
            if any(node.kind == "figure" for node in original_section.nodes):
                figure_sections.append(original_section.id)

    if not changed_sections and not changed_tasks:
        raise ReviewRevisionValidationError("review revision contains no allowlisted text edits")
    return ReviewRevisionProof(
        document_id=origin.id,
        origin_revision=origin.revision,
        origin_hash=origin_hash,
        revision=revised.revision,
        content_hash=revision_hash,
        changed_section_ids=tuple(changed_sections),
        figure_section_ids=tuple(figure_sections),
        changed_task_ids=changed_tasks,
    )


@dataclass(frozen=True)
class ReviewRevisionChainProof:
    """Verified end-to-end identity for a contiguous run of saved revisions."""

    document_id: str
    baseline_revision: int
    baseline_hash: str
    revision: int
    content_hash: str
    changed_section_ids: tuple[str, ...]
    figure_section_ids: tuple[str, ...]
    changed_task_ids: tuple[str, ...] = ()


def prove_review_draft_chain(
    revisions: Sequence[SharedLessonDocument],
) -> ReviewRevisionChainProof:
    """Verify a contiguous chain of saved review-draft revisions.

    ``revisions`` must be ordered from the last QA-validated baseline through
    the latest saved draft (inclusive). Each adjacent pair is independently
    proven with :func:`prove_review_draft_revision`; the aggregate changed and
    figure-touched section sets span the whole chain, so a caller can reject
    any figure-containing edit made across any intermediate save, not only the
    final one.
    """
    if len(revisions) < 2:
        raise ReviewRevisionValidationError("review revision chain requires at least one edit")
    changed: dict[str, None] = {}
    figures: dict[str, None] = {}
    tasks: dict[str, None] = {}
    baseline = revisions[0]
    current = baseline
    for step in revisions[1:]:
        proof = prove_review_draft_revision(current, step)
        for section_id in proof.changed_section_ids:
            changed[section_id] = None
        for section_id in proof.figure_section_ids:
            figures[section_id] = None
        for task_id in proof.changed_task_ids:
            tasks[task_id] = None
        current = step
    final = current
    return ReviewRevisionChainProof(
        document_id=baseline.id,
        baseline_revision=baseline.revision,
        baseline_hash=baseline.content_hash,
        revision=final.revision,
        content_hash=final.content_hash,
        changed_section_ids=tuple(changed),
        figure_section_ids=tuple(figures),
        changed_task_ids=tuple(tasks),
    )


__all__ = [
    "ReviewRevisionChainProof",
    "ReviewRevisionProof",
    "ReviewRevisionValidationError",
    "prove_review_draft_chain",
    "prove_review_draft_revision",
]

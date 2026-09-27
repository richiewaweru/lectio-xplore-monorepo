"""Pure proofs for immutable reviewer-created SharedLessonDocument revisions."""

from __future__ import annotations

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
        return (("display", "text"),)
    if kind == "callout":
        return (("display", "title"), ("display", "body"))
    if kind == "figure":
        return (("display", "caption"), ("accessibility", "alt_text"))
    if kind == "list":
        original_items = origin["display"]["items"]
        revised_items = revised["display"]["items"]
        if len(original_items) != len(revised_items):
            raise ReviewRevisionValidationError("review revision changed list shape")
        return tuple(("display", "items", index) for index in range(len(original_items)))
    if kind == "table":
        original_rows = origin["display"]["rows"]
        revised_rows = revised["display"]["rows"]
        if len(original_rows) != len(revised_rows) or any(
            len(left) != len(right) for left, right in zip(original_rows, revised_rows, strict=True)
        ):
            raise ReviewRevisionValidationError("review revision changed table shape")
        return tuple(
            ("display", "rows", row_index, column_index)
            for row_index, row in enumerate(original_rows)
            for column_index, _cell in enumerate(row)
        )
    return ()


def _node_matches_review_contract(origin: dict, revised: dict) -> bool:
    if origin.get("kind") == "task_anchor":
        return origin == revised
    if origin.get("kind") != revised.get("kind"):
        return False
    paths = _node_edit_paths(origin, revised)
    return bool(paths) and _same_except(origin, revised, paths)


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
        origin.tasks,
        origin.provenance,
        origin.created_at,
        origin.diagnostics,
    ) != (
        revised.teaching_plan_id,
        revised.teaching_plan_revision,
        revised.teaching_plan_hash,
        revised.schema_version,
        revised.title,
        revised.tasks,
        revised.provenance,
        revised.created_at,
        revised.diagnostics,
    ):
        raise ReviewRevisionValidationError("review revision changed document or source lineage")
    if revision_hash == origin_hash:
        raise ReviewRevisionValidationError("review revision contains no content correction")
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

    if not changed_sections:
        raise ReviewRevisionValidationError("review revision contains no allowlisted text edits")
    return ReviewRevisionProof(
        document_id=origin.id,
        origin_revision=origin.revision,
        origin_hash=origin_hash,
        revision=revised.revision,
        content_hash=revision_hash,
        changed_section_ids=tuple(changed_sections),
        figure_section_ids=tuple(figure_sections),
    )


__all__ = [
    "ReviewRevisionProof",
    "ReviewRevisionValidationError",
    "prove_review_draft_revision",
]

"""Strict content validation for typed page-object forms."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from generation.page_objects.models import FORM_OUTPUTS


class UnsupportedObject(ValueError):
    def __init__(self, object_id: str) -> None:
        self.object_id = object_id
        super().__init__(f"unsupported page object {object_id!r}")


class ContentValidationError(ValueError):
    def __init__(self, object_id: str, errors: list[dict[str, Any]]) -> None:
        self.object_id = object_id
        self.errors = errors
        detail = "; ".join(
            f"{err.get('path', '')}: {err.get('message', '')}".strip(": ")
            for err in errors
        )
        super().__init__(
            f"content validation failed for {object_id!r}: {detail or 'invalid schema'}"
        )


def _format_pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        path = ".".join(str(part) for part in loc)
        out.append({"path": path, "message": str(err.get("msg") or "invalid")})
    return out


def validate_content(object_id: str, raw: object) -> dict[str, Any]:
    model = FORM_OUTPUTS.get(object_id)
    if model is None:
        raise UnsupportedObject(object_id)
    try:
        validated = model.model_validate(raw)
    except ValidationError as exc:
        raise ContentValidationError(object_id, _format_pydantic_errors(exc)) from exc
    return validated.model_dump(mode="json", exclude_none=True)


class AnswerKeyIntegrityError(ValueError):
    """Raised when answer entries do not match assessed question/choice IDs."""


def validate_answer_key_integrity(
    blocks: list[dict[str, Any]],
    answer_entries: list[dict[str, Any]],
) -> None:
    """Every answer points to an assessed id; every assessed id has exactly one answer.

    Assessed IDs are ``questions.items[].id`` and ``choices`` block ids.
    MCQ answers must be a letter present in the choices options.
    """
    assessed_ids: set[str] = set()
    choice_blocks: dict[str, dict[str, Any]] = {}

    for block in blocks:
        object_id = block.get("object")
        if object_id == "questions":
            content = block.get("content") or {}
            for item in content.get("items") or []:
                item_id = item.get("id")
                if item_id:
                    assessed_ids.add(str(item_id))
        elif object_id == "choices":
            block_id = str(block.get("id") or "")
            if block_id:
                assessed_ids.add(block_id)
                choice_blocks[block_id] = block

    answer_ids = [str(entry.get("question_id") or "") for entry in answer_entries]
    if any(not qid for qid in answer_ids):
        raise AnswerKeyIntegrityError("answer entry missing question_id")

    if len(answer_ids) != len(set(answer_ids)):
        seen: set[str] = set()
        dupes: list[str] = []
        for qid in answer_ids:
            if qid in seen:
                dupes.append(qid)
            seen.add(qid)
        raise AnswerKeyIntegrityError(
            f"duplicate answer question_id(s): {sorted(set(dupes))}"
        )

    answer_set = set(answer_ids)
    missing = sorted(assessed_ids - answer_set)
    orphan = sorted(answer_set - assessed_ids)
    if missing or orphan:
        parts: list[str] = []
        if missing:
            parts.append(f"missing answers for {missing}")
        if orphan:
            parts.append(f"orphan answers for {orphan}")
        raise AnswerKeyIntegrityError("; ".join(parts))

    for block_id, block in choice_blocks.items():
        content = block.get("content") or {}
        letters = {
            str(option.get("letter"))
            for option in (content.get("options") or [])
            if option.get("letter")
        }
        entry = next(e for e in answer_entries if str(e.get("question_id")) == block_id)
        answer = str(entry.get("answer") or "")
        if answer not in letters:
            raise AnswerKeyIntegrityError(
                f"MCQ answer {answer!r} not in options {sorted(letters)} for {block_id!r}"
            )

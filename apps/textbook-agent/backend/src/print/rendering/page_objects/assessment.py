"""Assessment assemblers: student content only + separated answer entries."""

from __future__ import annotations

from typing import Any

from print.rendering.page_objects.models import (
    AnswerEntry,
    AssessmentBundle,
    WriterContext,
    WriterError,
    WriterOutcome,
)


def _assert_fixed_object(ctx: WriterContext, expected: str) -> None:
    if ctx.planned.object != expected:
        raise WriterError(
            f"writer for {expected!r} cannot run on planned object {ctx.planned.object!r}"
        )


def _records_by_id(ctx: WriterContext) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in ctx.item_records}


def _option_letter(option: dict[str, Any]) -> str:
    return str(option.get("letter") or option.get("key") or "").strip()


def _option_text(option: dict[str, Any]) -> str:
    return str(option.get("text") or option.get("label") or "").strip()


def _normalize_choices_options(raw_options: list[Any]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        letter = _option_letter(option)
        text = _option_text(option)
        if letter and text:
            options.append({"letter": letter, "text": text})
    return options


def _shared_task(ctx: WriterContext) -> dict[str, Any] | None:
    order = ctx.print_work_order
    raw = getattr(order, "shared_task", None) if order is not None else None
    return dict(raw) if isinstance(raw, dict) else None


def _shared_task_evaluation(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get("evaluation")
    return dict(value) if isinstance(value, dict) else {}


def _shared_task_answer_entry(
    *,
    question_id: str,
    task: dict[str, Any],
) -> dict[str, Any] | None:
    evaluation = _shared_task_evaluation(task)
    # Shared tasks use plural keys for select-many and a singular key for
    # select-one.  Preserve those semantic keys in the Print answer key;
    # falling back to expected_evidence here would turn a choice answer into
    # prose that cannot be checked against the paper options.
    correct_keys = evaluation.get("correct_keys")
    if isinstance(correct_keys, list) and correct_keys:
        answer = ",".join(str(item).strip() for item in correct_keys if str(item).strip())
    else:
        correct = evaluation.get("correct")
        if isinstance(correct, list) and correct:
            answer = ",".join(str(item).strip() for item in correct if str(item).strip())
        else:
            answer = evaluation.get("answer") or evaluation.get("correct_key")
    expected = str(task.get("expected_evidence") or "").strip()
    rubric = evaluation.get("rubric") or evaluation.get("criteria")
    if answer is None and not expected and not rubric:
        return None
    entry: dict[str, Any] = {
        "question_id": question_id,
        "answer": str(answer if answer is not None else expected or "See rubric."),
    }
    if rubric:
        entry["rubric"] = (
            "; ".join(str(item) for item in rubric)
            if isinstance(rubric, list)
            else str(rubric)
        )
    return entry


def _answer_entry_from_record(
    *,
    question_id: str,
    record: dict[str, Any],
) -> dict[str, Any] | None:
    answer = record.get("answer")
    if answer is None or answer == "":
        answer = record.get("correct_key")
    if answer is None or answer == "":
        return None
    entry: dict[str, Any] = {
        "question_id": question_id,
        "answer": str(answer),
    }
    alternatives = record.get("alternatives")
    if isinstance(alternatives, list) and alternatives:
        entry["alternatives"] = [str(item) for item in alternatives]
    if record.get("working") is not None:
        entry["working"] = record.get("working")
    if record.get("rubric") is not None:
        entry["rubric"] = record.get("rubric")
    return entry


def assemble_questions(ctx: WriterContext) -> WriterOutcome:
    """Deterministic assembler. Student content only — no options/correct_key."""
    _assert_fixed_object(ctx, "questions")
    task = _shared_task(ctx)
    source_ids = tuple(ctx.planned.source_question_ids or ())
    if not source_ids:
        if ctx.planned.task_mode != "formative" or task is None:
            raise WriterError("questions block requires source_question_ids or a formative SharedTaskSpec")
        question_id = str(task.get("id") or ctx.planned.id)
        prompt = str(task.get("prompt") or "").strip()
        if not prompt:
            raise WriterError("formative SharedTaskSpec requires a prompt")
        response = task.get("response") if isinstance(task.get("response"), dict) else {}
        item: dict[str, Any] = {"id": question_id, "prompt": prompt}
        if response.get("answer_lines") is not None:
            item["answer_lines"] = response["answer_lines"]
        answer = _shared_task_answer_entry(question_id=question_id, task=task)
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"items": [item]},
            answer_entries=(answer,) if answer is not None else (),
        )
    by_id = _records_by_id(ctx)
    items: list[dict[str, Any]] = []
    answer_entries: list[dict[str, Any]] = []
    for qid in ctx.planned.source_question_ids:
        record = by_id.get(qid)
        if record is None:
            raise WriterError(f"missing item record for question id {qid!r}")
        if record.get("options"):
            raise WriterError(
                f"multiple-choice item {qid!r} must be assembled as choices"
            )
        item: dict[str, Any] = {
            "id": qid,
            "prompt": record.get("prompt") or record.get("stem") or f"Question {qid}",
        }
        if record.get("marks") is not None:
            item["marks"] = record.get("marks")
        if record.get("answer_lines") is not None:
            item["answer_lines"] = record.get("answer_lines")
        items.append(item)
        entry = _answer_entry_from_record(question_id=qid, record=record)
        if entry is not None:
            answer_entries.append(entry)
    content: dict[str, Any] = {"items": items}
    return WriterOutcome(
        block_id=ctx.planned.id,
        content=content,
        answer_entries=tuple(answer_entries),
    )


def assemble_choices(ctx: WriterContext) -> WriterOutcome:
    """Assemble one MCQ choices block from its exact teaching-owned item."""
    _assert_fixed_object(ctx, "choices")
    task = _shared_task(ctx)
    by_id = _records_by_id(ctx)
    source_ids = tuple(ctx.planned.source_question_ids or ())
    if not source_ids and ctx.planned.task_mode == "formative" and task is not None:
        stem = str(task.get("prompt") or "").strip()
        response = task.get("response") if isinstance(task.get("response"), dict) else {}
        options = _normalize_choices_options(list(response.get("options") or []))
        if not stem:
            raise WriterError("formative SharedTaskSpec requires a prompt")
        if len(options) < 2:
            raise WriterError(
                "formative SharedTaskSpec choices require at least two options; "
                f"response={response!r}"
            )
        answer = _shared_task_answer_entry(question_id=ctx.planned.id, task=task)
        if answer is None:
            raise WriterError("formative SharedTaskSpec choices require an evaluation")
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"stem": stem, "options": options},
            answer_entries=(answer,),
        )
    if len(source_ids) != 1:
        raise WriterError("choices block requires exactly one source_question_id")
    record = by_id.get(source_ids[0])
    if record is None:
        raise WriterError(f"missing item record for question id {source_ids[0]!r}")
    stem = str(record.get("stem") or record.get("prompt") or "").strip()
    if not stem:
        raise WriterError("choices item record requires a stem")
    options = _normalize_choices_options(list(record.get("options") or []))
    content: dict[str, Any] = {"stem": stem, "options": options}
    if record.get("marks") is not None:
        content["marks"] = record.get("marks")
    if len(options) < 2:
        raise WriterError("choices block requires at least two options")
    entry = _answer_entry_from_record(question_id=ctx.planned.id, record=record)
    if entry is None:
        raise WriterError("choices item record requires a correct answer")
    answer_entries = (entry,)

    return WriterOutcome(
        block_id=ctx.planned.id,
        content=content,
        answer_entries=answer_entries,
    )


def build_assessment_bundle(ctx: WriterContext) -> AssessmentBundle:
    """Build student WriterOutcome(s) plus AnswerEntry models for questions or choices."""
    if ctx.planned.object == "questions":
        result = assemble_questions(ctx)
    elif ctx.planned.object == "choices":
        result = assemble_choices(ctx)
    else:
        raise WriterError(
            f"assessment bundle requires questions or choices, got {ctx.planned.object!r}"
        )
    entries = [
        AnswerEntry.model_validate(entry) for entry in result.answer_entries
    ]
    return AssessmentBundle(student_blocks=[result], answer_entries=entries)

"""Native page-object writers and questions assembler.

Typed 8-form registry with assessment bundle support and informed repair.
Stub APIs remain stable for existing offline unit tests.
"""

from __future__ import annotations

from generation.page_objects.assessment import (
    assemble_choices,
    assemble_questions,
    build_assessment_bundle,
)
from generation.page_objects.models import (
    FORM_OUTPUTS,
    GENERATED_FORM_IDS,
    AnswerEntry,
    AsideContent,
    AssessmentBundle,
    ChoicesContent,
    ChoicesOption,
    FigureAsset,
    FigureContent,
    ListContent,
    ProseContent,
    QuestionsContent,
    QuestionsItem,
    TableContent,
    WorkedExampleContent,
    WriterContext,
    WriterError,
    WriterResult,
)
from generation.page_objects.prompts import build_repair_prompt, build_writer_prompt
from generation.page_objects.registry import (
    dispatch_writer,
    dispatch_writer_async,
    write_aside,
    write_figure,
    write_list,
    write_prose,
    write_table,
    write_worked_example,
)
from generation.page_objects.validation import (
    AnswerKeyIntegrityError,
    ContentValidationError,
    UnsupportedObject,
    validate_answer_key_integrity,
    validate_content,
)

__all__ = [
    "FORM_OUTPUTS",
    "GENERATED_FORM_IDS",
    "AnswerEntry",
    "AnswerKeyIntegrityError",
    "AsideContent",
    "AssessmentBundle",
    "ChoicesContent",
    "ChoicesOption",
    "ContentValidationError",
    "FigureAsset",
    "FigureContent",
    "ListContent",
    "ProseContent",
    "QuestionsContent",
    "QuestionsItem",
    "TableContent",
    "UnsupportedObject",
    "WorkedExampleContent",
    "WriterContext",
    "WriterError",
    "WriterResult",
    "assemble_choices",
    "assemble_questions",
    "build_assessment_bundle",
    "build_repair_prompt",
    "build_writer_prompt",
    "dispatch_writer",
    "dispatch_writer_async",
    "validate_answer_key_integrity",
    "validate_content",
    "write_aside",
    "write_figure",
    "write_list",
    "write_prose",
    "write_table",
    "write_worked_example",
]

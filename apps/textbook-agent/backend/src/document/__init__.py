"""Neutral ordinary document vocabulary shared by Print and Learn.

Six primitives only. No pagination, CSS, component IDs, interaction scoring,
video, simulation, or generic Media.
"""

from document.composer import compose_document_plan, heuristic_compose_document_plan
from document.composition import CompositionDecision, CompositionPlan
from document.models import (
    DOCUMENT_PRIMITIVE_KINDS,
    CalloutNode,
    DocumentNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
)
from document.shared_lesson import (
    SharedLessonDocument,
    SharedProvenance,
    SharedSection,
    TaskAnchor,
    build_shared_lesson_document,
    shared_lesson_content_hash,
    verify_shared_lesson_source,
)
from document.validation import DocumentValidationError, validate_document_nodes
from document.writer import write_document_primitive
from document.writer_prompts import (
    COMPOSITION_TEMPLATE,
    DOCUMENT_COMPOSER_PROMPT_NAME,
    DOCUMENT_WRITER_PROMPT_NAME,
    FIGURE_PIPELINE_NOTE,
    GENERIC_WRITER_TEMPLATE,
    document_composer_prompt,
    document_writer_prompt,
)

__all__ = [
    "COMPOSITION_TEMPLATE",
    "DOCUMENT_COMPOSER_PROMPT_NAME",
    "DOCUMENT_PRIMITIVE_KINDS",
    "DOCUMENT_WRITER_PROMPT_NAME",
    "FIGURE_PIPELINE_NOTE",
    "GENERIC_WRITER_TEMPLATE",
    "CalloutNode",
    "CompositionDecision",
    "CompositionPlan",
    "DocumentNode",
    "DocumentValidationError",
    "FigureNode",
    "HeadingNode",
    "ListNode",
    "ParagraphNode",
    "SharedLessonDocument",
    "SharedProvenance",
    "SharedSection",
    "TableNode",
    "TaskAnchor",
    "build_shared_lesson_document",
    "compose_document_plan",
    "document_composer_prompt",
    "document_writer_prompt",
    "heuristic_compose_document_plan",
    "shared_lesson_content_hash",
    "validate_document_nodes",
    "verify_shared_lesson_source",
    "write_document_primitive",
]

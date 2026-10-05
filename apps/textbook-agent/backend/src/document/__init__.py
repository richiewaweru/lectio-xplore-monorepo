"""Neutral ordinary document vocabulary shared by Print and Learn.

Ordinary document primitives only. No pagination, CSS, component IDs, interaction scoring,
video, simulation, or generic Media.
"""

from document.composition import CompositionDecision, CompositionPlan
from document.models import (
    DOCUMENT_PRIMITIVE_KINDS,
    CalloutNode,
    CompareNode,
    DocumentNode,
    EquationNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
    QuoteNode,
)
from document.shared_lesson import (
    AssemblyIssue,
    SharedLessonAssemblyError,
    SharedLessonAssemblyResult,
    SharedLessonDocument,
    SharedProvenance,
    SharedSection,
    TaskAnchor,
    assemble_shared_lesson_document,
    build_shared_lesson_document,
    shared_lesson_content_hash,
    verify_shared_lesson_source,
)
from document.validation import DocumentValidationError, validate_document_nodes

__all__ = [
    "DOCUMENT_PRIMITIVE_KINDS",
    "CalloutNode",
    "CompareNode",
    "AssemblyIssue",
    "CompositionDecision",
    "CompositionPlan",
    "DocumentNode",
    "EquationNode",
    "DocumentValidationError",
    "FigureNode",
    "HeadingNode",
    "ListNode",
    "ParagraphNode",
    "SharedLessonDocument",
    "SharedLessonAssemblyError",
    "SharedLessonAssemblyResult",
    "SharedProvenance",
    "SharedSection",
    "TableNode",
    "QuoteNode",
    "TaskAnchor",
    "build_shared_lesson_document",
    "assemble_shared_lesson_document",
    "shared_lesson_content_hash",
    "validate_document_nodes",
    "verify_shared_lesson_source",
]

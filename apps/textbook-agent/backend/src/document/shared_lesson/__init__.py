"""Path-neutral shared lesson artifact contract."""

from document.shared_lesson.composer import (
    CompositionChoice,
    CompositionItem,
    CompositionPolicy,
    CompositionValidationError,
    SectionCompositionDraft,
    SectionCompositionPlan,
    compose_section,
    validate_and_build_composition,
    validate_composition_plan,
)
from document.shared_lesson.hashing import (
    canonical_shared_lesson_payload,
    shared_lesson_content_hash,
    verify_shared_lesson_source,
)
from document.shared_lesson.models import (
    CalloutNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    SharedLessonDocument,
    SharedProvenance,
    SharedSection,
    TableNode,
    TaskAnchor,
    build_shared_lesson_document,
)

__all__ = [
    "CalloutNode",
    "CompositionChoice",
    "CompositionItem",
    "CompositionPolicy",
    "CompositionValidationError",
    "FigureNode",
    "HeadingNode",
    "ListNode",
    "ParagraphNode",
    "SharedLessonDocument",
    "SharedProvenance",
    "SharedSection",
    "SectionCompositionDraft",
    "SectionCompositionPlan",
    "TableNode",
    "TaskAnchor",
    "build_shared_lesson_document",
    "canonical_shared_lesson_payload",
    "compose_section",
    "shared_lesson_content_hash",
    "validate_and_build_composition",
    "validate_composition_plan",
    "verify_shared_lesson_source",
]

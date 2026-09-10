"""Learn document contracts: legacy LessonDocument v1 and LearnDocument v2.

v1 remains for existing component-centric production until Phase M deletes it.
v2 is the ordered-node LearnDocument built from document primitives + interactions.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from document.models import (
    DOCUMENT_PRIMITIVE_KINDS,
    CalloutNode,
    DocumentNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
    document_node_adapter,
)

REQUIRED_DOCUMENT_FIELDS = (
    "version",
    "id",
    "title",
    "subject",
    "preset_id",
    "source",
    "source_generation_id",
    "sections",
    "blocks",
    "media",
    "created_at",
    "updated_at",
)

REQUIRED_SECTION_FIELDS = (
    "id",
    "template_id",
    "block_ids",
    "title",
    "position",
)

REQUIRED_BLOCK_FIELDS = (
    "id",
    "component_id",
    "content",
    "position",
)

GENERATION_ONLY_FIELDS = frozenset(
    {
        "schema",
        "plan_hash",
        "plan_revision",
        "human_revision",
        "partial",
        "pipeline",
        "status",
    }
)

RETAINED_INTERACTION_TYPES = frozenset(
    {
        "choice",
        "multi-select",
        "fill-blank",
        "classify",
        "match-pairs",
        "sequence",
        "numeric",
        "short-response",
    }
)

InteractionType = Literal[
    "choice",
    "multi-select",
    "fill-blank",
    "classify",
    "match-pairs",
    "sequence",
    "numeric",
    "short-response",
]

FORBIDDEN_NODE_FIELDS = frozenset({"component_id", "template_id", "page_break", "ruled_lines", "media"})


class LessonDocumentValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class LearnDocumentValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class InteractionNode(BaseModel):
    """Explicit Learn interaction island — no component_id / template_id."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: Literal["interaction"] = "interaction"
    interaction_type: InteractionType
    teaching_block_id: str | None = None
    prompt: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    feedback: dict[str, Any] | str | None = None


LearnNode = Annotated[
    ParagraphNode
    | HeadingNode
    | ListNode
    | FigureNode
    | TableNode
    | CalloutNode
    | InteractionNode,
    Field(discriminator="kind"),
]

learn_node_adapter: TypeAdapter[LearnNode] = TypeAdapter(LearnNode)


class LearnDocument(BaseModel):
    """Ordered-node LearnDocument (version 2)."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    id: str = Field(min_length=1)
    title: str
    subject: str
    source: str
    source_generation_id: str | None = None
    nodes: list[LearnNode] = Field(default_factory=list)
    created_at: str
    updated_at: str
    teaching_plan_id: str | None = None
    teaching_plan_revision: int | None = None


def validate_lesson_document(document: Any) -> list[str]:
    """Validate legacy LessonDocument v1 (component/sections/blocks).

    Deprecated: prefer ``validate_learn_document`` for LearnDocument v2.
    Kept until Phase M removes the component-centric contract.
    """
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["LessonDocument must be an object"]

    leaked = sorted(key for key in GENERATION_ONLY_FIELDS if key in document)
    if leaked:
        errors.append(f"generation-runtime fields must not appear on LessonDocument: {leaked}")

    for field in REQUIRED_DOCUMENT_FIELDS:
        if field not in document:
            errors.append(f"Missing required field: {field}")

    if document.get("version") != 1:
        errors.append(f"Unsupported document version: {document.get('version')!r}. Expected 1.")

    if not isinstance(document.get("id"), str) or not str(document.get("id")).strip():
        errors.append("id must be a non-empty string")
    if not isinstance(document.get("title"), str):
        errors.append("title must be a string")
    if not isinstance(document.get("subject"), str):
        errors.append("subject must be a string")
    if not isinstance(document.get("preset_id"), str):
        errors.append("preset_id must be a string")
    if document.get("source") not in {"generated", "manual", "imported"} and not isinstance(
        document.get("source"), str
    ):
        errors.append("source must be a string")

    sections = document.get("sections")
    blocks = document.get("blocks")
    media = document.get("media")
    if not isinstance(sections, list):
        errors.append("sections must be an array")
        return errors
    if not isinstance(blocks, dict) or isinstance(blocks, list):
        errors.append("blocks must be an object")
        return errors
    if not isinstance(media, dict) or isinstance(media, list):
        errors.append("media must be an object")

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"sections[{index}] must be an object")
            continue
        for field in REQUIRED_SECTION_FIELDS:
            if field not in section:
                errors.append(f"sections[{index}] missing required field: {field}")
        if not isinstance(section.get("block_ids"), list):
            errors.append(f"sections[{index}].block_ids must be an array")
            continue
        if not isinstance(section.get("template_id"), str) or not section.get("template_id"):
            errors.append(f"sections[{index}].template_id must be a non-empty string")
        if not isinstance(section.get("position"), int):
            errors.append(f"sections[{index}].position must be an integer")
        for block_id in section.get("block_ids") or []:
            if block_id not in blocks:
                errors.append(f"sections[{index}] references missing block id {block_id!r}")

    for block_id, block in blocks.items():
        if not isinstance(block, dict):
            errors.append(f"blocks[{block_id!r}] must be an object")
            continue
        for field in REQUIRED_BLOCK_FIELDS:
            if field not in block:
                errors.append(f"blocks[{block_id!r}] missing required field: {field}")
        if block.get("id") != block_id:
            errors.append(f"blocks[{block_id!r}].id must equal its key")

    return errors


def assert_valid_lesson_document(document: Any) -> dict[str, Any]:
    errors = validate_lesson_document(document)
    if errors:
        raise LessonDocumentValidationError(errors)
    return document


def validate_learn_document(document: Any) -> list[str]:
    """Validate LearnDocument v2 (ordered document + interaction nodes)."""
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["LearnDocument must be an object"]

    if document.get("version") != 2:
        errors.append(f"Unsupported document version: {document.get('version')!r}. Expected 2.")

    for field in ("id", "title", "subject", "source", "nodes", "created_at", "updated_at"):
        if field not in document:
            errors.append(f"Missing required field: {field}")

    if not isinstance(document.get("id"), str) or not str(document.get("id")).strip():
        errors.append("id must be a non-empty string")
    if not isinstance(document.get("title"), str):
        errors.append("title must be a string")
    if not isinstance(document.get("subject"), str):
        errors.append("subject must be a string")
    if not isinstance(document.get("source"), str):
        errors.append("source must be a string")
    if document.get("source_generation_id") is not None and not isinstance(
        document.get("source_generation_id"), str
    ):
        errors.append("source_generation_id must be a string or null")
    if document.get("teaching_plan_id") is not None and not isinstance(
        document.get("teaching_plan_id"), str
    ):
        errors.append("teaching_plan_id must be a string or null")
    if document.get("teaching_plan_revision") is not None and not isinstance(
        document.get("teaching_plan_revision"), int
    ):
        errors.append("teaching_plan_revision must be an integer or null")

    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        errors.append("nodes must be an array")
        return errors

    seen_ids: set[str] = set()
    for index, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            errors.append(f"nodes[{index}] must be an object")
            continue
        leaked = sorted(k for k in FORBIDDEN_NODE_FIELDS if k in raw)
        if leaked:
            errors.append(f"nodes[{index}] contains forbidden fields: {leaked}")
            continue
        kind = raw.get("kind")
        try:
            if kind == "interaction":
                node = InteractionNode.model_validate(raw)
            elif kind in DOCUMENT_PRIMITIVE_KINDS:
                node = document_node_adapter.validate_python(raw)
            else:
                errors.append(
                    f"nodes[{index}] kind {kind!r} is not a LearnDocument node "
                    f"(document primitives or interaction)"
                )
                continue
        except ValidationError as exc:
            errors.append(f"nodes[{index}]: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            errors.append(f"nodes[{index}]: {exc}")
            continue
        node_id = getattr(node, "id", None)
        if not isinstance(node_id, str) or not node_id.strip():
            errors.append(f"nodes[{index}].id must be a non-empty string")
            continue
        if node_id in seen_ids:
            errors.append(f"duplicate node id {node_id!r}")
            continue
        seen_ids.add(node_id)

    return errors


def assert_valid_learn_document(document: Any) -> LearnDocument:
    errors = validate_learn_document(document)
    if errors:
        raise LearnDocumentValidationError(errors)
    return LearnDocument.model_validate(document)


__all__ = [
    "DOCUMENT_PRIMITIVE_KINDS",
    "FORBIDDEN_NODE_FIELDS",
    "InteractionNode",
    "InteractionType",
    "LearnDocument",
    "LearnDocumentValidationError",
    "LearnNode",
    "LessonDocumentValidationError",
    "RETAINED_INTERACTION_TYPES",
    "assert_valid_learn_document",
    "assert_valid_lesson_document",
    "learn_node_adapter",
    "validate_learn_document",
    "validate_lesson_document",
    # Re-export primitives for callers that import from this contract module.
    "CalloutNode",
    "DocumentNode",
    "FigureNode",
    "HeadingNode",
    "ListNode",
    "ParagraphNode",
    "TableNode",
]

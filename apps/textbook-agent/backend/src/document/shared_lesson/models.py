"""Closed, path-neutral SharedLessonDocument v1 contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationInfo,
    model_validator,
)

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.shared_tasks.validation import assert_task_response_contract
from document.shared_lesson.hashing import shared_lesson_content_hash

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class _FrozenDict(dict[str, Any]):
    def _immutable(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("ready shared lesson task meaning is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class _FrozenList(list[Any]):
    def _immutable(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("ready shared lesson task meaning is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze_json(item) for item in value)
    return value


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _NodeBase(_ClosedModel):
    id: str = Field(min_length=1)
    teaching_block_id: str | None = None


class NodeAccessibility(_ClosedModel):
    description: str = ""


class FigureAccessibility(_ClosedModel):
    #: Empty while the figure is pending; media binding fills it from the
    #: ready result. Final-document assembly requires it to be non-empty.
    alt_text: str = ""


class ParagraphDisplay(_ClosedModel):
    text: str = Field(min_length=1)


class HeadingDisplay(_ClosedModel):
    text: str = Field(min_length=1)
    level: int = Field(default=2, ge=1, le=3)


class ListDisplay(_ClosedModel):
    ordered: bool = False
    items: tuple[str, ...] = Field(min_length=1)


class FigureDisplay(_ClosedModel):
    asset_id: str | None = None
    caption: str = ""


class TableDisplay(_ClosedModel):
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    caption: str = ""


class CalloutDisplay(_ClosedModel):
    tone: Literal["note", "warning", "tip", "important"] = "note"
    title: str = ""
    body: str | None = Field(default=None, exclude_if=lambda value: value is None)
    variant: Literal["key_idea", "note", "misconception"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    belief: str | None = Field(default=None, exclude_if=lambda value: value is None)
    evidence: str | None = Field(default=None, exclude_if=lambda value: value is None)
    conclusion: str | None = Field(default=None, exclude_if=lambda value: value is None)
    aside: str | None = Field(default=None, exclude_if=lambda value: value is None)


class EquationDisplay(_ClosedModel):
    label: str | None = Field(default=None, exclude_if=lambda value: value is None)
    inputs: tuple[str, ...] = Field(min_length=1)
    condition: str | None = Field(default=None, exclude_if=lambda value: value is None)
    outputs: tuple[str, ...] = Field(min_length=1)


class QuoteDisplay(_ClosedModel):
    text: str = Field(min_length=1)
    attribution: str | None = Field(default=None, exclude_if=lambda value: value is None)


class CompareItem(_ClosedModel):
    label: str | None = Field(default=None, exclude_if=lambda value: value is None)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class CompareDisplay(_ClosedModel):
    items: tuple[CompareItem, ...] = Field(min_length=2)


class ParagraphNode(_NodeBase):
    kind: Literal["paragraph"] = "paragraph"
    display: ParagraphDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class HeadingNode(_NodeBase):
    kind: Literal["heading"] = "heading"
    display: HeadingDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class ListNode(_NodeBase):
    kind: Literal["list"] = "list"
    display: ListDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class FigureNode(_NodeBase):
    kind: Literal["figure"] = "figure"
    display: FigureDisplay
    accessibility: FigureAccessibility


class TableNode(_NodeBase):
    kind: Literal["table"] = "table"
    display: TableDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class CalloutNode(_NodeBase):
    kind: Literal["callout"] = "callout"
    display: CalloutDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class EquationNode(_NodeBase):
    kind: Literal["equation"] = "equation"
    display: EquationDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class QuoteNode(_NodeBase):
    kind: Literal["quote"] = "quote"
    display: QuoteDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class CompareNode(_NodeBase):
    kind: Literal["compare"] = "compare"
    display: CompareDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class TaskAnchor(_ClosedModel):
    id: str = Field(min_length=1)
    kind: Literal["task_anchor"] = "task_anchor"
    task_spec_id: str = Field(min_length=1)
    teaching_block_id: str = Field(min_length=1)
    role: str | None = None


SharedLessonNode = Annotated[
    ParagraphNode
    | HeadingNode
    | ListNode
    | FigureNode
    | TableNode
    | CalloutNode
    | EquationNode
    | QuoteNode
    | CompareNode
    | TaskAnchor,
    Field(discriminator="kind"),
]
shared_lesson_node_adapter: TypeAdapter[SharedLessonNode] = TypeAdapter(SharedLessonNode)


class SharedProvenance(_ClosedModel):
    source_ids: tuple[str, ...] = ()
    source_hashes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_provenance(self) -> SharedProvenance:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("provenance source_ids must be unique")
        for source_id, digest in self.source_hashes.items():
            if not source_id or not _HASH_PATTERN.fullmatch(digest):
                raise ValueError("provenance hashes must be lowercase SHA-256 digests")
        object.__setattr__(self, "source_hashes", _FrozenDict(self.source_hashes))
        return self


class SharedSection(_ClosedModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    position: int = Field(ge=0)
    nodes: tuple[SharedLessonNode, ...] = ()
    provenance: SharedProvenance = Field(default_factory=SharedProvenance)


class FrozenSharedTaskSpec(SharedTaskSpec):
    """Immutable snapshot retaining the complete SharedTaskSpec field contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    sourcebook_refs: tuple[str, ...] = ()
    approved_source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _freeze_nested_task_meaning(self) -> FrozenSharedTaskSpec:
        assert_task_response_contract(self)
        object.__setattr__(self, "response", _freeze_json(self.response))
        object.__setattr__(self, "evaluation", _freeze_json(self.evaluation))
        if self.feedback is not None:
            object.__setattr__(self, "feedback", _freeze_json(self.feedback))
        if self.option_notes is not None:
            object.__setattr__(self, "option_notes", _freeze_json(self.option_notes))
        return self


class SharedLessonDocument(_ClosedModel):
    schema_version: Literal[1] = 1
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    teaching_plan_id: str = Field(min_length=1)
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(min_length=1)
    sections: tuple[SharedSection, ...] = Field(min_length=1)
    tasks: tuple[FrozenSharedTaskSpec, ...] = ()
    provenance: SharedProvenance = Field(default_factory=SharedProvenance)
    created_at: datetime
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_complete_immutable_artifact(self, info: ValidationInfo) -> SharedLessonDocument:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        positions = [section.position for section in self.sections]
        if positions != list(range(len(self.sections))):
            raise ValueError("section positions must be unique and contiguous from zero")

        ids: list[str] = [self.id]
        anchors: list[TaskAnchor] = []
        for section in self.sections:
            ids.append(section.id)
            for node in section.nodes:
                ids.append(node.id)
                if isinstance(node, TaskAnchor):
                    anchors.append(node)
        ids.extend(task.id for task in self.tasks)
        if len(ids) != len(set(ids)):
            raise ValueError("document, section, node, and task IDs must be unique")

        tasks_by_id = {task.id: task for task in self.tasks}
        anchors_by_task: dict[str, list[TaskAnchor]] = {}
        for anchor in anchors:
            anchors_by_task.setdefault(anchor.task_spec_id, []).append(anchor)
            task = tasks_by_id.get(anchor.task_spec_id)
            if task is None:
                raise ValueError(f"task anchor {anchor.id!r} references an unknown task")
            if anchor.teaching_block_id != task.teaching_block_id:
                raise ValueError(f"task anchor {anchor.id!r} has the wrong teaching block owner")
        if set(anchors_by_task) != set(tasks_by_id):
            raise ValueError("every registered task must have a TaskAnchor")
        if any(len(items) != 1 for items in anchors_by_task.values()):
            raise ValueError("each registered task must have exactly one TaskAnchor")

        for task in self.tasks:
            if (
                task.teaching_plan_id != self.teaching_plan_id
                or task.teaching_plan_revision != self.teaching_plan_revision
                or task.teaching_plan_hash != self.teaching_plan_hash
            ):
                raise ValueError(f"task {task.id!r} has mismatched Teaching Plan lineage")

        if (
            not (info.context or {}).get("skip_content_hash_validation")
            and shared_lesson_content_hash(self) != self.content_hash
        ):
            raise ValueError("content_hash does not match canonical shared lesson content")
        return self


def build_shared_lesson_document(payload: Mapping[str, Any]) -> SharedLessonDocument:
    """Build an immutable artifact while deriving its canonical content hash."""
    data = dict(payload)
    data.setdefault("schema_version", 1)
    data.pop("content_hash", None)
    data["content_hash"] = "0" * 64
    normalized = SharedLessonDocument.model_validate(
        data, context={"skip_content_hash_validation": True}
    )
    return normalized.model_copy(update={"content_hash": shared_lesson_content_hash(normalized)})


__all__ = [
    "CompareDisplay",
    "CompareItem",
    "CompareNode",
    "CalloutDisplay",
    "CalloutNode",
    "EquationDisplay",
    "EquationNode",
    "FigureAccessibility",
    "FigureDisplay",
    "FigureNode",
    "FrozenSharedTaskSpec",
    "HeadingDisplay",
    "HeadingNode",
    "ListDisplay",
    "ListNode",
    "NodeAccessibility",
    "ParagraphDisplay",
    "ParagraphNode",
    "QuoteDisplay",
    "QuoteNode",
    "SharedLessonDocument",
    "SharedLessonNode",
    "SharedProvenance",
    "SharedSection",
    "TableDisplay",
    "TableNode",
    "TaskAnchor",
    "build_shared_lesson_document",
    "shared_lesson_node_adapter",
]

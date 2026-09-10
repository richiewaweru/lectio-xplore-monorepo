"""Minimal ordinary document primitives for Print and Learn realizers."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


DOCUMENT_PRIMITIVE_KINDS = frozenset(
    {"paragraph", "heading", "list", "figure", "table", "callout"}
)


class _NodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    teaching_block_id: str | None = None


class ParagraphNode(_NodeBase):
    kind: Literal["paragraph"] = "paragraph"
    text: str = Field(min_length=1)


class HeadingNode(_NodeBase):
    kind: Literal["heading"] = "heading"
    text: str = Field(min_length=1)
    level: int = Field(default=2, ge=1, le=3)


class ListNode(_NodeBase):
    kind: Literal["list"] = "list"
    ordered: bool = False
    items: list[str] = Field(min_length=1)


class FigureNode(_NodeBase):
    kind: Literal["figure"] = "figure"
    asset_id: str | None = None
    caption: str = ""
    alt: str = ""


class TableNode(_NodeBase):
    kind: Literal["table"] = "table"
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str = ""


class CalloutNode(_NodeBase):
    kind: Literal["callout"] = "callout"
    tone: Literal["note", "warning", "tip", "important"] = "note"
    title: str = ""
    body: str = Field(min_length=1)


DocumentNode = Annotated[
    ParagraphNode | HeadingNode | ListNode | FigureNode | TableNode | CalloutNode,
    Field(discriminator="kind"),
]

document_node_adapter: TypeAdapter[DocumentNode] = TypeAdapter(DocumentNode)

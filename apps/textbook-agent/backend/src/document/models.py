"""Minimal ordinary document primitives for Print and Learn realizers."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

DOCUMENT_PRIMITIVE_KINDS = frozenset(
    {"paragraph", "heading", "list", "figure", "table", "callout", "equation", "quote", "compare"}
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
    body: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    variant: Literal["key_idea", "note", "misconception"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    belief: str | None = Field(default=None, exclude_if=lambda value: value is None)
    evidence: str | None = Field(default=None, exclude_if=lambda value: value is None)
    conclusion: str | None = Field(default=None, exclude_if=lambda value: value is None)
    aside: str | None = Field(default=None, exclude_if=lambda value: value is None)


class EquationNode(_NodeBase):
    kind: Literal["equation"] = "equation"
    label: str | None = None
    inputs: list[str] = Field(min_length=1)
    condition: str | None = None
    outputs: list[str] = Field(min_length=1)


class QuoteNode(_NodeBase):
    kind: Literal["quote"] = "quote"
    text: str = Field(min_length=1)
    attribution: str | None = None


class CompareItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class CompareNode(_NodeBase):
    kind: Literal["compare"] = "compare"
    items: list[CompareItem] = Field(min_length=2)


DocumentNode = Annotated[
    ParagraphNode
    | HeadingNode
    | ListNode
    | FigureNode
    | TableNode
    | CalloutNode
    | EquationNode
    | QuoteNode
    | CompareNode,
    Field(discriminator="kind"),
]

document_node_adapter: TypeAdapter[DocumentNode] = TypeAdapter(DocumentNode)

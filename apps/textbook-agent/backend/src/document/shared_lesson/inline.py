"""Total parser for the small learner-facing inline markup language.

The parser deliberately returns data rather than HTML.  Renderers can then
escape text at their output boundary while preserving literal unmatched
markers and arbitrary text such as ``<script>``.
"""

from __future__ import annotations

from typing import Literal, TypedDict


InlineKind = Literal["text", "strong", "emphasis", "subscript", "superscript"]


class InlineTextNode(TypedDict):
    type: Literal["text"]
    value: str


class InlineSpanNode(TypedDict):
    type: Literal["strong", "emphasis", "subscript", "superscript"]
    children: list["InlineNode"]


InlineNode = InlineTextNode | InlineSpanNode


def _text(value: str) -> InlineNode:
    return {"type": "text", "value": value}


def _span(kind: InlineKind, children: list[InlineNode]) -> InlineNode:
    assert kind != "text"
    return {"type": kind, "children": children}


def _append(nodes: list[InlineNode], node: InlineNode) -> None:
    if node["type"] == "text" and not node["value"]:
        return
    if nodes and node["type"] == "text" and nodes[-1]["type"] == "text":
        nodes[-1]["value"] += node["value"]
    else:
        nodes.append(node)


def _plain(value: str) -> list[InlineNode]:
    return [_text(value)] if value else []


def _marker_run_is_exact(value: str, index: int, marker: str) -> bool:
    """Only an isolated delimiter run can open or close a span."""
    char = marker[0]
    left = index > 0 and value[index - 1] == char
    right_index = index + len(marker)
    right = right_index < len(value) and value[right_index] == char
    return not left and not right


def _find_close(value: str, marker: str, start: int) -> int:
    candidate = value.find(marker, start)
    while candidate >= 0:
        if _marker_run_is_exact(value, candidate, marker):
            return candidate
        candidate = value.find(marker, candidate + 1)
    return -1


def _parse_segment(
    value: str, *, allow_emphasis: bool, allow_sub_sup: bool
) -> list[InlineNode]:
    nodes: list[InlineNode] = []
    text_start = 0
    index = 0

    def flush(until: int) -> None:
        nonlocal text_start
        if until > text_start:
            _append(nodes, _text(value[text_start:until]))

    while index < len(value):
        marker: str | None = None
        kind: InlineKind | None = None
        nested = False
        if value.startswith("**", index):
            marker, kind, nested = "**", "strong", True
        elif allow_emphasis and value[index] == "*":
            marker, kind = "*", "emphasis"
        elif allow_sub_sup and value[index] in "~^":
            marker = value[index]
            kind = "subscript" if marker == "~" else "superscript"

        if marker is None or kind is None:
            index += 1
            continue

        if not _marker_run_is_exact(value, index, marker):
            index += len(marker)
            continue

        close = _find_close(value, marker, index + len(marker))
        if close < 0:
            index += len(marker)
            continue
        if close == index + len(marker):
            index += len(marker)
            continue

        flush(index)
        body = value[index + len(marker) : close]
        children = (
            _parse_segment(body, allow_emphasis=False, allow_sub_sup=True)
            if nested
            else _plain(body)
        )
        _append(nodes, _span(kind, children))
        index = close + len(marker)
        text_start = index

    flush(len(value))
    return nodes


def parse_inline_markup(value: str) -> list[InlineNode]:
    """Parse inline markup without raising for any input string."""

    return _parse_segment(value, allow_emphasis=True, allow_sub_sup=True)


__all__ = ["InlineKind", "InlineNode", "parse_inline_markup"]

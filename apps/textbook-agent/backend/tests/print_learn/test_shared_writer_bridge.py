from __future__ import annotations

from inspect import getsource

from print.generation.shared_writer_bridge import document_node_to_print_content
from print.rendering.page_objects.registry import dispatch_writer_async


def test_shared_writer_maps_ordinary_nodes_to_page_objects() -> None:
    prose = document_node_to_print_content(
        "prose", {"kind": "paragraph", "text": "Leaves make food."}
    )
    assert prose == {"paragraphs": ["Leaves make food."]}
    listed = document_node_to_print_content(
        "list", {"kind": "list", "ordered": True, "items": ["One", "Two"]}
    )
    assert listed["style"] == "ordered"
    assert listed["items"][0]["text"] == "One"
    aside = document_node_to_print_content(
        "aside", {"kind": "callout", "tone": "note", "title": "Watch", "body": "Light matters."}
    )
    assert aside["label"] == "Watch"
    assert aside["body"] == "Light matters."


def test_llm_ordinary_dispatch_uses_shared_document_writer() -> None:
    source = getsource(dispatch_writer_async)
    assert "write_ordinary_via_shared_writer" in source
    assert "write_prose" not in source

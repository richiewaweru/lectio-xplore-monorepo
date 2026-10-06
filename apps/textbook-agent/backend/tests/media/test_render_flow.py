from __future__ import annotations

import io
from typing import Any

import pytest
from pydantic import TypeAdapter

from media.render.contracts import FlowSpec, RenderSpec
from media.render.families import flow
from media.render.style import drawing

_ADAPTER = TypeAdapter(RenderSpec)


def _spec(name: str) -> FlowSpec:
    spec = _ADAPTER.validate_python(flow.GALLERY[name])
    assert isinstance(spec, FlowSpec)
    return spec


def _svg(spec: FlowSpec) -> bytes:
    with drawing():
        fig = flow.draw(spec)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="svg", metadata={"Date": None})
    return buffer.getvalue()


def _codes(**fields: Any) -> list[str]:
    return [error.code for error in flow.validate(FlowSpec(**fields))]


def _nodes(*ids: str) -> list[dict[str, str]]:
    return [{"id": i, "text": f"Step {i}"} for i in ids]


@pytest.mark.parametrize("name", sorted(flow.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = _spec(name)
    assert flow.validate(spec) == []
    first = _svg(spec)
    assert first.startswith(b"<?xml")
    assert first == _svg(spec)
    assert flow.numbers(spec) == []
    assert flow.describe(spec)


def test_decision_gallery_layers_and_no_back_edges() -> None:
    layers, back = flow.edge_classes(_spec("flow_decision"))
    assert back == set()
    assert layers == {"start": 0, "even": 1, "half": 2, "triple": 2, "write": 3, "end": 4}


def test_loop_gallery_detects_the_back_edge() -> None:
    spec = _spec("flow_loop")
    layers, back = flow.edge_classes(spec)
    assert back == {3}
    assert layers == {"plan": 0, "draft": 1, "review": 2, "revise": 3}


def test_describe_linear_and_branching() -> None:
    assert flow.describe(_spec("flow_linear")).startswith("Flow of 5 steps: Gather the materials → ")
    assert "—Yes→" in flow.describe(_spec("flow_decision"))


def test_duplicate_node_id() -> None:
    nodes = [{"id": "a", "text": "One"}, {"id": "a", "text": "Two"}]
    assert "duplicate_node_id" in _codes(nodes=nodes, edges=[{"start": "a", "end": "a"}])


def test_unknown_node() -> None:
    errors = flow.validate(FlowSpec(nodes=_nodes("a", "b"), edges=[{"start": "a", "end": "z"}]))
    assert [(e.code, e.path) for e in errors if e.code == "unknown_node"] == [
        ("unknown_node", "edges[0].end")
    ]


def test_self_loop() -> None:
    assert "self_loop" in _codes(
        nodes=_nodes("a", "b"), edges=[{"start": "a", "end": "b"}, {"start": "b", "end": "b"}]
    )


def test_duplicate_edge() -> None:
    assert "duplicate_edge" in _codes(
        nodes=_nodes("a", "b"), edges=[{"start": "a", "end": "b"}, {"start": "a", "end": "b"}]
    )


def test_unreachable_node() -> None:
    errors = flow.validate(
        FlowSpec(nodes=_nodes("a", "b", "c"), edges=[{"start": "a", "end": "b"}])
    )
    assert [(e.code, e.path) for e in errors] == [("unreachable_node", "nodes[2]")]


def test_decision_needs_two_labelled_edges() -> None:
    nodes = [
        {"id": "a", "text": "Ready?", "kind": "decision"},
        {"id": "b", "text": "Go"},
        {"id": "c", "text": "Wait"},
    ]
    only_one = flow.validate(
        FlowSpec(nodes=nodes[:2], edges=[{"start": "a", "end": "b", "label": "Yes"}])
    )
    assert [e.code for e in only_one] == ["decision_needs_labels"]
    unlabelled = flow.validate(
        FlowSpec(
            nodes=nodes,
            edges=[{"start": "a", "end": "b", "label": "Yes"}, {"start": "a", "end": "c"}],
        )
    )
    assert [(e.code, e.path) for e in unlabelled] == [("decision_needs_labels", "edges[1].label")]


def test_node_text_too_long() -> None:
    long = "Pneumonoultramicroscopic"
    errors = flow.validate(
        FlowSpec(
            nodes=[{"id": "a", "text": long}, {"id": "b", "text": "Next"}],
            edges=[{"start": "a", "end": "b"}],
        )
    )
    assert [(e.code, e.path) for e in errors] == [("node_text_too_long", "nodes[0].text")]

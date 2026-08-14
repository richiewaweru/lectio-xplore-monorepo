from __future__ import annotations

import pytest
from pydantic import ValidationError

from planning.whole_lesson.visual_topology import (
    TopologyPlanV1,
    TopologyValidationError,
    validate_topology_plan,
)


def _plan(**overrides):
    payload = {
        "layout": "flow",
        "nodes": [
            {"id": "n0", "label_id": "l0", "evidence_keys": ["ev.a"]},
            {"id": "n1", "label_id": "l1", "evidence_keys": ["ev.b"]},
        ],
        "edges": [
            {
                "id": "e0",
                "from_ref": "n0",
                "to_ref": "n1",
                "direction": "forward",
                "evidence_keys": ["ev.a"],
            }
        ],
        "labels": [
            {"id": "l0", "placement": "node", "ref": "n0"},
            {"id": "l1", "placement": "node", "ref": "n1"},
        ],
        "cues": ["arrow"],
    }
    payload.update(overrides)
    return payload


def test_valid_plan_uses_authoritative_ids_and_aliases():
    plan = validate_topology_plan(
        _plan(),
        source={
            "label_ids": ["l0", "l1"],
            "evidence_keys": ["ev.a", "ev.b"],
            "cue_ids": ["arrow"],
        },
    )
    assert isinstance(plan, TopologyPlanV1)
    assert plan.edges[0].from_ref == "n0"


@pytest.mark.parametrize(
    "mutator,needle",
    [
        (lambda p: p["labels"].pop(), "missing label"),
        (lambda p: p["edges"].__setitem__(0, {**p["edges"][0], "to_ref": "n9"}), "unknown node"),
        (lambda p: p["edges"].__setitem__(0, {**p["edges"][0], "from_ref": "n1"}), "self-edge"),
        (lambda p: p.update(exclusions=["invented"]), "exclusions"),
        (lambda p: p.update(cues=["invented"]), "cues"),
    ],
)
def test_validator_fails_closed(mutator, needle):
    payload = _plan()
    mutator(payload)
    with pytest.raises(TopologyValidationError, match=needle):
        validate_topology_plan(
            payload,
            source={
                "label_ids": ["l0", "l1"],
                "evidence_keys": ["ev.a", "ev.b"],
                "cue_ids": ["arrow"],
            },
        )


def test_schema_forbids_renderable_free_text_and_unknown_fields():
    with pytest.raises(ValidationError):
        TopologyPlanV1(**{**_plan(), "caption": "draw a river"})


def test_cycle_requires_closed_degree_two_graph():
    payload = _plan(layout="cycle")
    with pytest.raises(TopologyValidationError, match="closed cycle"):
        validate_topology_plan(
            payload,
            source={"label_ids": ["l0", "l1"], "evidence_keys": ["ev.a", "ev.b"]},
        )

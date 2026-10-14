"""Learners must never receive answer keys from a published Learn document."""

from __future__ import annotations

import copy

from learn.publishing.learner_safe import learner_safe_document

ANSWER_KEY_FIELDS = {
    "correct_option_id",
    "correct_option_ids",
    "answers",
    "accepted_answers",
    "value",
    "tolerance",
    "pairs",
    "order",
    "correct_placements",
    "review_guidance",
    "rubric_criteria",
}


def _node(kind: str, config: dict, task_id: str | None = None) -> dict:
    node = {
        "id": f"ix-{kind}",
        "kind": "interaction",
        "interaction_type": kind,
        "prompt": f"Prompt for {kind}",
        "config": config,
        "feedback": {"correct": "Yes", "incorrect": "No"},
        "role": "practice",
        "option_notes": {"a": "note"},
        "contract": {
            "id": f"ix-{kind}",
            "kind": kind,
            "config": copy.deepcopy(config),
            "shared_task": {"id": task_id or f"task-{kind}"},
        },
    }
    return node


PAIRS = [
    {"left": "water", "right": "roots"},
    {"left": "light", "right": "leaves"},
    {"left": "air", "right": "stomata"},
]


def _document() -> dict:
    return {
        "version": 2,
        "nodes": [
            {"id": "p1", "kind": "paragraph", "text": "Hello"},
            _node(
                "choice",
                {
                    "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                    "correct_option_id": "a",
                },
            ),
            _node(
                "multi-select",
                {
                    "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                    "correct_option_ids": ["a"],
                },
            ),
            _node(
                "fill-blank",
                {"answers": ["x", "y"], "answer_lines": 1, "case_sensitive": False},
            ),
            _node("numeric", {"value": 4, "tolerance": 0.1, "unit": "cm", "min": 0, "max": 10}),
            _node(
                "short-response",
                {
                    "evaluation": "teacher-review",
                    "review_guidance": "Look for X",
                    "rubric_criteria": ["X"],
                    "placeholder": "Write",
                },
            ),
            _node(
                "match-pairs",
                {"pairs": PAIRS, "left_items": ["water", "light", "air"], "right_items": ["leaves", "stomata", "roots"]},
            ),
            _node(
                "classify",
                {
                    "items": ["water", "light"],
                    "categories": [{"id": "roots", "label": "roots"}],
                    "pairs": PAIRS[:2],
                    "correct_placements": {"water": "roots"},
                },
            ),
            _node("sequence", {"items": ["b", "a", "c"], "order": ["a", "b", "c"]}),
        ],
    }


def _interactions(doc: dict) -> dict[str, dict]:
    return {n["interaction_type"]: n for n in doc["nodes"] if n.get("kind") == "interaction"}


def test_no_answer_key_fields_or_contract_remain() -> None:
    safe = learner_safe_document(_document())
    nodes = _interactions(safe)
    assert len(nodes) == 8  # every interaction kind
    for node in nodes.values():
        assert "contract" not in node
        assert not (ANSWER_KEY_FIELDS & set(node["config"]))
        assert node["feedback"] == {"correct": "Yes", "incorrect": "No"}
        assert node["role"] == "practice"
        assert node["option_notes"] == {"a": "note"}
        assert node["prompt"].startswith("Prompt for")


def test_display_fields_survive_and_are_present() -> None:
    nodes = _interactions(learner_safe_document(_document()))
    assert nodes["choice"]["config"]["options"]
    assert nodes["numeric"]["config"]["unit"] == "cm"
    assert nodes["numeric"]["config"]["min"] == 0
    assert nodes["fill-blank"]["config"]["blank_count"] == 2
    assert nodes["short-response"]["config"]["evaluation"] == "teacher-review"
    assert nodes["short-response"]["config"]["placeholder"] == "Write"
    assert nodes["match-pairs"]["config"]["left_items"] == ["water", "light", "air"]
    assert nodes["match-pairs"]["config"]["right_items"] == ["leaves", "stomata", "roots"]
    assert nodes["classify"]["config"]["items"] == ["water", "light"]
    assert nodes["classify"]["config"]["categories"] == [{"id": "roots", "label": "roots"}]
    assert nodes["sequence"]["config"]["items"] == ["b", "a", "c"]


def test_input_document_is_not_mutated() -> None:
    document = _document()
    snapshot = copy.deepcopy(document)
    learner_safe_document(document)
    assert document == snapshot


def test_old_releases_without_display_fields_get_them() -> None:
    document = {
        "version": 2,
        "nodes": [
            _node("match-pairs", {"pairs": PAIRS}, task_id="t-old-match"),
            _node("fill-blank", {"answers": ["x", "y", "z"]}),
            _node("classify", {"pairs": PAIRS}),
            _node("sequence", {"order": ["a", "b", "c", "d"]}, task_id="t-old-seq"),
        ],
    }
    nodes = _interactions(learner_safe_document(document))
    match = nodes["match-pairs"]["config"]
    assert match["left_items"] == ["water", "light", "air"]
    assert sorted(match["right_items"]) == ["leaves", "roots", "stomata"]
    assert all(match["right_items"][i] != PAIRS[i]["right"] for i in range(3))
    assert nodes["fill-blank"]["config"]["blank_count"] == 3
    classify = nodes["classify"]["config"]
    assert classify["items"] == ["water", "light", "air"]
    assert [c["id"] for c in classify["categories"]] == ["roots", "leaves", "stomata"]
    seq = nodes["sequence"]["config"]["items"]
    assert sorted(seq) == ["a", "b", "c", "d"] and seq != ["a", "b", "c", "d"]
    for node in nodes.values():
        assert not (ANSWER_KEY_FIELDS & set(node["config"]))
        assert "contract" not in node


def test_old_match_order_uses_shared_task_id_like_print() -> None:
    from curriculum.shared_tasks.ordering import derange_for_display

    document = {"version": 2, "nodes": [_node("match-pairs", {"pairs": PAIRS}, task_id="t-key")]}
    shown = _interactions(learner_safe_document(document))["match-pairs"]["config"]["right_items"]
    assert shown == derange_for_display("t-key", ["roots", "leaves", "stomata"])


def test_non_document_inputs_are_tolerated() -> None:
    assert learner_safe_document({}) == {}
    assert learner_safe_document({"nodes": "nope"}) == {"nodes": "nope"}

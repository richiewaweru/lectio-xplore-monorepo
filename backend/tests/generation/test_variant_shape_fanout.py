from __future__ import annotations

from generation.v3_studio.router import _variant_plan_for_fanout


def test_fanout_uses_variant_sections_and_latest_approved_shared_cards() -> None:
    state = {
        "structural_plan": {
            "lesson_intent": {"goal": "Exact path objective"},
            "cards": [{"id": "concept", "misconceptions": [{"text": "Approved edit"}]}],
            "sections": [{"id": "core-explain", "role": "explain"}],
        },
        "variant_structural_plans": {
            "Support": {
                "lesson_intent": {"goal": "stale copy"},
                "cards": [{"id": "concept", "misconceptions": []}],
                "sections": [
                    {"id": "support-model", "role": "model"},
                    {"id": "support-check", "role": "check"},
                ],
            }
        },
    }

    selected = _variant_plan_for_fanout(state, "Support")

    assert selected is not None
    assert [section["role"] for section in selected["sections"]] == ["model", "check"]
    assert selected["lesson_intent"]["goal"] == "Exact path objective"
    assert selected["cards"][0]["misconceptions"] == [{"text": "Approved edit"}]
    assert state["variant_structural_plans"]["Support"]["cards"][0]["misconceptions"] == []


def test_fanout_falls_back_to_canonical_plan_for_legacy_state() -> None:
    state = {"structural_plan": {"cards": [], "sections": [{"role": "check"}]}}
    assert _variant_plan_for_fanout(state, "Core") == state["structural_plan"]

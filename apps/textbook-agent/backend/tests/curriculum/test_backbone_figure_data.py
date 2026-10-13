"""Backbone figure data validator: numbers in labels must agree with the figure's data."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from curriculum.backbone import writer
from curriculum.backbone.errors import BackboneOutputInvalidError
from curriculum.backbone.figure_data import figure_data_errors
from curriculum.backbone.models import LessonBackbone

LESSON_1_FIG_2 = {
    "id": "fig-2",
    "purpose": "Compare weekly heights of two seedlings.",
    "must_show": ["Height of each seedling at each weekly check"],
    "labels_required": ["Day", "Height of Seedling A (cm)", "Height of Seedling B (cm)"],
    "mode": "render",
    "data": {
        "Day": [0, 7, 14, 21, 28],
        "Height of Seedling A (cm)": [5, 12, 22, 35, 48],
        "Height of Seedling B (cm)": [5, 6, 7, 8, 9],
    },
}


def _backbone(*figures: dict[str, Any]) -> LessonBackbone:
    return LessonBackbone.model_validate(
        {"anchor": {"story": "Seedlings.", "data": {}}, "figures": list(figures)}
    )


def test_lesson_1_fig_2_is_clean() -> None:
    assert figure_data_errors(_backbone(LESSON_1_FIG_2)) == []


def test_unequal_series_lengths() -> None:
    fig = dict(LESSON_1_FIG_2, data={"Day": [0, 7, 14], "A": [5, 12]}, labels_required=["Day"])
    errors = figure_data_errors(_backbone(fig))
    assert len(errors) == 1
    assert errors[0].startswith("BACKBONE_FIGURE_SERIES_LENGTH") and "fig-2" in errors[0]


def test_label_number_not_in_data() -> None:
    fig = dict(LESSON_1_FIG_2, labels_required=["Day 28: 49 cm"])
    errors = figure_data_errors(_backbone(fig))
    assert len(errors) == 1
    assert errors[0].startswith("BACKBONE_FIGURE_LABEL_NUMBER")
    assert "fig-2" in errors[0] and "49" in errors[0] and "28" not in errors[0]


def test_label_with_day_and_value_both_in_data_is_clean() -> None:
    fig = dict(LESSON_1_FIG_2, labels_required=["Day 28: 48 cm"], must_show=["Day 7: 12 cm"])
    assert figure_data_errors(_backbone(fig)) == []


def test_numbers_in_labels_with_empty_data() -> None:
    fig = {
        "id": "fig-9",
        "purpose": "Heights",
        "must_show": ["a plant"],
        "labels_required": ["Day 28: 48 cm"],
        "data": {},
    }
    errors = figure_data_errors(_backbone(fig))
    assert len(errors) == 1
    assert errors[0].startswith("BACKBONE_FIGURE_DATA_MISSING") and "fig-9" in errors[0]


def test_decimal_comparison_and_no_numbers() -> None:
    fig = dict(LESSON_1_FIG_2, data={"x": [1.50, 2]}, labels_required=["1.5 m"], must_show=[])
    assert figure_data_errors(_backbone(fig)) == []
    plain = {"id": "fig-3", "purpose": "A cell", "must_show": ["nucleus"], "labels_required": []}
    assert figure_data_errors(_backbone(plain)) == []


LESSON_1_FIG_1 = {
    "id": "fig-1",
    "purpose": "Compare two maize seedlings.",
    "must_show": [
        "two maize seedlings side by side",
        "Seedling A: tall and green in an open garden with sunlight",
        "Seedling B: short and pale yellow in a dark store with no light",
        "both seedlings have the same height label at Day 0",
    ],
    "labels_required": [
        "Seedling A: open garden, direct sunlight",
        "Seedling B: dark store, no light",
        "Height Day 0: 5 cm",
        "Height Day 0: 5 cm",
        "Height Day 28: 48 cm",
        "Height Day 28: 9 cm",
        "Leaf colour: green",
        "Leaf colour: pale yellow",
        "Water: 50 ml per day each",
    ],
    "data": {
        "water_ml_per_day_each": 50,
        "seedling_a_leaf_colour": "green",
        "seedling_b_leaf_colour": "pale yellow",
        "seedling_a_height_day_0_cm": 5,
        "seedling_b_height_day_0_cm": 5,
        "seedling_a_height_day_28_cm": 48,
        "seedling_b_height_day_28_cm": 9,
    },
    "mode": "diagram",
}


def test_numbers_in_key_names_count_as_present() -> None:
    assert figure_data_errors(_backbone(LESSON_1_FIG_1)) == []


def test_series_in_diagram_needs_render() -> None:
    errors = figure_data_errors(_backbone(dict(LESSON_1_FIG_2, mode="diagram")))
    assert len(errors) == 1 and errors[0].startswith("BACKBONE_FIGURE_SERIES_NEEDS_RENDER")
    assert figure_data_errors(_backbone(dict(LESSON_1_FIG_2, mode=None))) == errors


def test_series_too_large_for_render() -> None:
    long = dict(LESSON_1_FIG_2, data={"Day": list(range(13)), "A": list(range(13))},
                labels_required=["Day"])
    assert figure_data_errors(_backbone(long))[0].startswith("BACKBONE_FIGURE_SERIES_TOO_LARGE")
    wide = dict(LESSON_1_FIG_2, data={f"s{i}": [1, 2] for i in range(9)}, labels_required=[])
    assert figure_data_errors(_backbone(wide))[0].startswith("BACKBONE_FIGURE_SERIES_TOO_LARGE")


def test_render_mode_loads_and_old_hash_unchanged() -> None:
    old = _backbone({"id": "f", "purpose": "p"})
    assert "mode" not in old.figures[0].model_dump(mode="json")
    assert old.figures[0].effective_mode == "diagram"
    assert _backbone(LESSON_1_FIG_2).figures[0].effective_mode == "render"


def _draft_json(backbone: LessonBackbone) -> dict[str, Any]:
    data = backbone.model_dump(mode="json")
    data["anchor"].pop("id", None)
    for variant in data.get("variants", []):
        variant.pop("id", None)
    return data


def test_materialize_raises_contract_error_with_messages() -> None:
    bad = _backbone(dict(LESSON_1_FIG_2, labels_required=["Day 28: 49 cm"]))
    with pytest.raises(writer._BackboneContractError) as info:
        writer._materialize(_draft_json(bad))
    assert info.value.errors[0].startswith("BACKBONE_FIGURE_LABEL_NUMBER")


def test_writer_retry_receives_messages_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _draft_json(_backbone(dict(LESSON_1_FIG_2, labels_required=["Day 28: 49 cm"])))
    prompts: list[str] = []

    class FakeAgent:
        def __init__(self, **_: Any) -> None:
            pass

    async def fake_run_llm(*, user_prompt: str, **_: Any) -> Any:
        prompts.append(user_prompt)
        return SimpleNamespace(output=bad)

    monkeypatch.setattr(
        writer, "prepare_structured_agent", lambda **_: (object(), object(), None, object(), "t")
    )
    monkeypatch.setattr(writer, "get_v3_slot", lambda _n: "slot")
    monkeypatch.setattr(writer, "get_v3_model_settings", lambda _n: None)
    monkeypatch.setattr(writer, "lesson_backbone_writer_prompt", lambda: "prompt")
    monkeypatch.setattr(writer, "Agent", FakeAgent)
    monkeypatch.setattr(writer, "run_llm", fake_run_llm)

    inputs = SimpleNamespace(payload=dict)
    with pytest.raises(BackboneOutputInvalidError) as info:
        asyncio.run(writer.generate_backbone(inputs))  # type: ignore[arg-type]
    assert len(prompts) == 2
    assert "validation_errors" not in prompts[0]
    assert "BACKBONE_FIGURE_LABEL_NUMBER" in prompts[1] and "fig-2" in prompts[1]
    assert any("BACKBONE_FIGURE_LABEL_NUMBER" in d for d in info.value.details)


def test_lesson_1_backbone_fig_1_diagram_and_fig_2_render_passes() -> None:
    backbone = _backbone(LESSON_1_FIG_1, LESSON_1_FIG_2)
    assert [f.effective_mode for f in backbone.figures] == ["diagram", "render"]
    assert figure_data_errors(backbone) == []


def test_lesson_1_backbone_fails_series_needs_render_when_fig_2_is_diagram() -> None:
    errors = figure_data_errors(_backbone(LESSON_1_FIG_1, dict(LESSON_1_FIG_2, mode="diagram")))
    assert len(errors) == 1
    assert errors[0].startswith("BACKBONE_FIGURE_SERIES_NEEDS_RENDER") and "fig-2" in errors[0]

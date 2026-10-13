from __future__ import annotations

from decimal import Decimal

from document.shared_lesson.figure_numbers import (
    allowed_text_numbers,
    number_warnings,
    without_number_warnings,
)
from document.shared_lesson.media import build_figure_work_order
from tests.document.test_shared_lesson_media import (
    _prose_shape,
    _section_with_prose,
    _source,
)

SERIES = {
    "days": [0, 7, 14, 21, 28],
    "height_seedling_a_cm": [5, 12, 22, 35, 48],
}
ALLOWED = {Decimal(n) for n in (5, 12, 22, 35, 48, 0, 7, 14, 21, 28)}


def test_unsupported_caption_number_is_flagged_once_and_sorted() -> None:
    out = number_warnings(
        caption="Seedling A grew 19 cm, then 12.5 cm and 19 cm",
        section_text="",
        data=None,
        allowed=ALLOWED,
    )
    assert out == ["number_unsupported:12.5", "number_unsupported:19"]


def test_prose_numbers_are_checked_too() -> None:
    out = number_warnings(
        caption="Heights", section_text="After 3 weeks it was 19 cm.", data=None, allowed=ALLOWED
    )
    assert out == ["number_unsupported:3", "number_unsupported:19"]


def test_supported_numbers_raise_nothing() -> None:
    allowed = allowed_text_numbers(
        data=SERIES,
        approved_fact_texts=["Seedling B was 9 cm on day 28."],
        objective="Compare growth over 4 weeks.",
        brief_and_labels=["Day 0: 5 cm"],
    )
    assert number_warnings(
        caption="Seedling A reached 48 cm; B reached 9 cm",
        section_text="Over 4 weeks, from day 0 to day 28.",
        data=SERIES,
        allowed=allowed,
    ) == []


def test_data_figure_whose_text_states_no_value_is_advisory() -> None:
    out = number_warnings(
        caption="Seedling growth", section_text="Plants grow.", data=SERIES, allowed=ALLOWED
    )
    assert out == ["figure_value_missing_in_text:0"]


def test_scalar_data_does_not_demand_a_value() -> None:
    assert number_warnings(
        caption="Seedlings", section_text="", data={"day_0_height_cm": 5}, allowed=ALLOWED
    ) == []


def test_without_number_warnings_keeps_label_warnings() -> None:
    mixed = ["label_missing:Leaf", "number_unsupported:19", "figure_value_missing_in_text:0"]
    assert without_number_warnings(mixed) == ["label_missing:Leaf"]


def _order(caption: str, paragraph: str, *, data: dict | None = None):
    return build_figure_work_order(
        _source(data),
        _section_with_prose(caption, paragraph),
        figure_node_id="figure-a",
        expected_shape=_prose_shape(),
        approved_source_facts={"fact-leaf": "The leaf receives sunlight."},
    )


def test_media_order_carries_number_warnings_and_still_builds() -> None:
    work = _order("Sunlight and the leaf: 19 cm", "Sunlight on a Leaf.")
    assert work.warnings == ["number_unsupported:19"]
    assert work.work_order.visual.purpose  # the order itself is intact


def test_media_order_has_no_number_warning_for_supported_text() -> None:
    work = _order("Sunlight and the leaf", "Sunlight on a Leaf.")
    assert work.warnings == []


def test_order_stored_before_number_warnings_still_verifies() -> None:
    import pytest

    from document.shared_lesson.media_runtime import MediaSourceConflict, _verify_accepted_section

    section = _section_with_prose("Sunlight and the leaf: 19 cm", "Sunlight on a Leaf.")
    work = _order("Sunlight and the leaf: 19 cm", "Sunlight on a Leaf.")
    assert work.warnings == ["number_unsupported:19"]

    old_style = work.model_copy(update={"warnings": []})  # admitted before this check
    _verify_accepted_section(old_style, section, _source())
    _verify_accepted_section(work, section, _source())

    # Other warning kinds are still compared.
    forged = work.model_copy(update={"warnings": ["label_missing:Nope"]})
    with pytest.raises(MediaSourceConflict):
        _verify_accepted_section(forged, section, _source())

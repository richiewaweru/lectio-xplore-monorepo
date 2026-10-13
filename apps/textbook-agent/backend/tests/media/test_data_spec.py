from __future__ import annotations

from media.render.data_spec import is_data_figure, spec_from_data

FIG2 = {
    "days": [0, 7, 14, 21, 28],
    "height_seedling_a_cm": [5, 12, 22, 35, 48],
    "height_seedling_b_cm": [5, 6, 7, 8, 9],
}
LABELS = ["Day", "Height of Seedling A (cm)", "Height of Seedling B (cm)"]


def test_lesson_1_fig_2_uses_required_labels() -> None:
    spec = spec_from_data(FIG2, LABELS, [])
    assert spec is not None
    assert spec.columns == LABELS
    assert spec.rows == [[0, 5, 5], [7, 12, 6], [14, 22, 7], [21, 35, 8], [28, 48, 9]]
    assert all(type(v) is int for row in spec.rows for v in row)


def test_label_count_mismatch_uses_readable_keys() -> None:
    spec = spec_from_data(FIG2, ["Day", "Height"], ["x"])
    assert spec is not None
    assert spec.columns == ["Days", "Height seedling a (cm)", "Height seedling b (cm)"]


def test_no_labels_uses_readable_keys() -> None:
    spec = spec_from_data({"a": [1, 2], "rainfall_mm": [3, 4]}, None, None)
    assert spec is not None
    assert spec.columns == ["A", "Rainfall (mm)"]


def test_unequal_lengths_return_none() -> None:
    assert spec_from_data({"a": [1, 2, 3], "b": [1, 2]}, [], []) is None


def test_scalar_only_returns_none() -> None:
    assert spec_from_data({"day_0_height_cm": 5, "day_28_height_cm": 48}, [], []) is None


def test_mixed_scalar_and_list_returns_none() -> None:
    assert spec_from_data({"a": [1, 2], "b": 3}, [], []) is None


def test_empty_and_none_return_none() -> None:
    assert spec_from_data({}, [], []) is None
    assert spec_from_data(None, [], []) is None


def test_single_element_lists_return_none() -> None:
    assert spec_from_data({"a": [1], "b": [2]}, [], []) is None


def test_nested_values_return_none() -> None:
    assert spec_from_data({"a": [[1], [2]], "b": [1, 2]}, [], []) is None
    assert spec_from_data({"a": [{"x": 1}, {"x": 2}], "b": [1, 2]}, [], []) is None


def test_floats_and_strings_are_not_rounded_or_coerced() -> None:
    spec = spec_from_data({"x": [0.1, 12.5], "note": ["low", "5"]}, [], [])
    assert spec is not None
    assert spec.rows == [[0.1, "low"], [12.5, "5"]]
    assert type(spec.rows[1][1]) is str and type(spec.rows[1][0]) is float


def test_too_many_columns_or_rows_return_none() -> None:
    assert spec_from_data({f"c{i}": [1, 2] for i in range(9)}, [], []) is None
    assert spec_from_data({"a": list(range(13)), "b": list(range(13))}, [], []) is None


def test_header_over_limit_returns_none() -> None:
    assert spec_from_data({"a": [1, 2], "b": [3, 4]}, ["ok", "L" * 41], []) is None


def test_is_data_figure() -> None:
    assert is_data_figure(FIG2)
    assert is_data_figure({"a": [1.5, 2]})
    assert not is_data_figure(None)
    assert not is_data_figure({})
    assert not is_data_figure({"a": 5})
    assert not is_data_figure({"a": [5]})
    assert not is_data_figure({"a": [True, False]})
    assert not is_data_figure({"a": [1, "2"]})
    assert not is_data_figure({"a": ["x", "y"]})

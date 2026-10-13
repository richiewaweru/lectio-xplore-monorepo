from __future__ import annotations

import io
from typing import Any

import pytest

from media.render.contracts import RenderSpecResult, TableSpec
from media.render.families import table
from media.render.style import drawing


def _svg(spec: TableSpec) -> bytes:
    with drawing():
        fig = table.draw(spec)
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", metadata={"Date": None})
    return buf.getvalue()


def _cell_texts(spec: TableSpec) -> list[str]:
    with drawing():
        fig = table.draw(spec)
        return [t.get_text() for t in fig.axes[0].texts]


def _codes(**fields: Any) -> list[str]:
    base: dict[str, Any] = {"columns": ["A", "B"], "rows": [[1, 2], [3, 4]]}
    base.update(fields)
    return [e.code for e in table.validate(TableSpec.model_validate(base))]


@pytest.mark.parametrize("name", sorted(table.GALLERY))
def test_gallery_validates_and_draws_deterministically(name: str) -> None:
    spec = TableSpec.model_validate(table.GALLERY[name])
    assert table.validate(spec) == []
    assert table.describe(spec)
    first = _svg(spec)
    assert first.startswith(b"<?xml") and first == _svg(spec)


def test_values_are_shown_exactly() -> None:
    spec = TableSpec.model_validate(
        {"columns": ["A", "B"], "rows": [[12.5, 48], [3.0, "n/a"], [0.1, 1234567]]}
    )
    texts = _cell_texts(spec)
    for expected in ("12.5", "48", "3.0", "n/a", "0.1", "1234567"):
        assert expected in texts


def test_ints_and_strings_are_not_coerced() -> None:
    spec = TableSpec.model_validate({"columns": ["A", "B"], "rows": [[5, "5"], [5.0, 7]]})
    assert [type(v) for v in spec.rows[0]] == [int, str]
    assert [type(v) for v in spec.rows[1]] == [float, int]


def test_long_headers_wrap_inside_the_figure() -> None:
    spec = TableSpec.model_validate(
        {
            "columns": ["Height of Seedling A (cm)", "Height of Seedling B (cm)", "Day"],
            "rows": [[48, 9, 28]],
        }
    )
    assert _svg(spec)
    assert any("\n" in t for t in _cell_texts(spec))


def test_numbers_include_numeric_cells_and_numbers_in_text() -> None:
    spec = TableSpec.model_validate(
        {"columns": ["A", "B"], "rows": [[1, "5 cm and -2.5"], [2.5, "none"]]}
    )
    assert table.numbers(spec) == [1.0, 5.0, -2.5, 2.5]


def test_describe_lists_columns_and_rows() -> None:
    spec = TableSpec.model_validate(table.GALLERY["table_weekly_growth"])
    text = table.describe(spec)
    assert "Day, Seedling A height (cm)" in text and "row 5" in text and "48.5" in text


def test_valid_spec_has_no_errors() -> None:
    assert _codes() == []


def test_row_length_mismatch() -> None:
    assert _codes(rows=[[1, 2], [3]]) == ["row_length_mismatch"]


def test_duplicate_column() -> None:
    assert _codes(columns=["A", "a"]) == ["duplicate_column"]


def test_empty_cell() -> None:
    assert _codes(rows=[[1, " "]]) == ["empty_cell"]


def test_size_limits_in_schema() -> None:
    with pytest.raises(ValueError):
        TableSpec.model_validate({"columns": ["A"], "rows": [[1]]})
    with pytest.raises(ValueError):
        TableSpec.model_validate({"columns": ["A", "B"], "rows": [[1, 2]] * 13})


def test_result_union_accepts_table() -> None:
    result = RenderSpecResult.model_validate(
        {"family": "table", "spec": table.GALLERY["table_weekly_growth"]}
    )
    assert isinstance(result.spec, TableSpec)

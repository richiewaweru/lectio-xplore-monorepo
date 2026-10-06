from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from media.render.contracts import PolygonAreaSpec, RenderSpecResult
from media.render.export import InvalidRenderSpec, render_spec
from media.render.validate import validate_spec

L_ROOM = [[0, 0], [9, 0], [9, 5], [6, 5], [6, 7], [0, 7]]


def _codes(**fields: Any) -> list[str]:
    return [error.code for error in validate_spec(PolygonAreaSpec(**fields))]


def test_valid_l_room_has_no_errors() -> None:
    assert _codes(points=L_ROOM, edge_labels=[{"edge": i} for i in range(6)]) == []


def test_clockwise_points_are_accepted() -> None:
    assert _codes(points=list(reversed(L_ROOM)), edge_labels=[{"edge": 0}]) == []


def test_degenerate_polygon() -> None:
    assert _codes(points=[[0, 0], [1, 1], [2, 2]]) == ["degenerate_polygon"]


def test_duplicate_point() -> None:
    assert _codes(points=[[0, 0], [0, 0], [3, 0], [3, 3]]) == ["duplicate_point"]


def test_self_intersecting_bow_tie() -> None:
    assert "self_intersecting" in _codes(points=[[0, 0], [4, 4], [4, 0], [0, 4]])


def test_bad_and_duplicate_edge_index() -> None:
    codes = _codes(points=L_ROOM, edge_labels=[{"edge": 9}, {"edge": 1}, {"edge": 1}])
    assert codes == ["bad_edge_index", "duplicate_edge_label"]


def test_awkward_computed_length_must_be_symbol_or_hidden() -> None:
    triangle = [[0, 0], [2, 0], [0, 2]]  # hypotenuse 2.828...
    assert _codes(points=triangle, edge_labels=[{"edge": 1}]) == ["awkward_length"]
    assert _codes(points=triangle, edge_labels=[{"edge": 1, "kind": "symbol", "text": "x"}]) == []
    assert _codes(points=triangle, edge_labels=[{"edge": 1, "kind": "hidden"}]) == []


def test_symbol_needs_text_and_computed_rejects_text() -> None:
    assert _codes(points=L_ROOM, edge_labels=[{"edge": 0, "kind": "symbol"}]) == ["symbol_needs_text"]
    assert _codes(points=L_ROOM, edge_labels=[{"edge": 0, "text": "9 m"}]) == ["unexpected_text"]


def test_segment_outside_the_notch() -> None:
    # (5,6)->(8,6) crosses the cut-out top-right corner.
    assert _codes(points=L_ROOM, segments=[{"start": [5, 6], "end": [8, 6]}]) == ["segment_outside"]


def test_right_angle_mark_needs_boundary_endpoint() -> None:
    codes = _codes(points=L_ROOM, segments=[{"start": [3, 1], "end": [3, 4], "right_angle_at": "start"}])
    assert codes == ["right_angle_off_boundary"]


def test_region_outside_and_overlapping_regions() -> None:
    assert _codes(points=L_ROOM, regions=[{"points": [[6, 0], [9, 0], [9, 7], [6, 7]]}]) == ["region_outside"]
    whole = {"points": [[0, 0], [6, 0], [6, 7], [0, 7]]}
    assert _codes(points=L_ROOM, regions=[whole, whole]) == ["regions_overlap"]


def test_render_spec_raises_with_all_errors_for_repair() -> None:
    spec = PolygonAreaSpec(points=L_ROOM, edge_labels=[{"edge": 9}, {"edge": 0, "kind": "symbol"}])
    with pytest.raises(InvalidRenderSpec) as caught:
        render_spec(spec)
    assert [e.code for e in caught.value.errors] == ["bad_edge_index", "symbol_needs_text"]


def test_schema_caps_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PolygonAreaSpec(points=[[i, i * i] for i in range(21)])
    with pytest.raises(ValidationError):
        PolygonAreaSpec(points=L_ROOM, svg="<svg/>")


def test_spec_result_family_must_match() -> None:
    assert RenderSpecResult(family="none").spec is None
    ok = RenderSpecResult.model_validate({"family": "polygon_area", "spec": {"family": "polygon_area", "points": L_ROOM}})
    assert ok.spec is not None
    with pytest.raises(ValidationError):
        RenderSpecResult.model_validate({"family": "flow", "spec": {"family": "polygon_area", "points": L_ROOM}})
    with pytest.raises(ValidationError):
        RenderSpecResult(family="polygon_area")


def test_grid_needs_whole_points_and_a_small_span() -> None:
    assert _codes(points=L_ROOM, grid=True) == []
    assert _codes(points=[[0, 0], [2.5, 0], [2.5, 2], [0, 2]], grid=True) == ["grid_needs_whole_points"]
    assert _codes(points=[[0, 0], [40, 0], [40, 2], [0, 2]], grid=True) == ["grid_too_large"]

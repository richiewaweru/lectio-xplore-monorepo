from __future__ import annotations

import re

import pytest
from pydantic import TypeAdapter

from media.render import geometry as g
from media.render.contracts import PolygonAreaSpec, RenderSpec
from media.render.export import render_spec
from media.render.families.polygon import place_labels
from media.render.gallery import GALLERY, L_ROOM_POINTS
from media.render.validate import cross_check_numbers

_ADAPTER = TypeAdapter(RenderSpec)


def _spec(name: str) -> PolygonAreaSpec:
    spec = _ADAPTER.validate_python(GALLERY[name])
    assert isinstance(spec, PolygonAreaSpec)
    return spec


def _svg_text(svg: bytes) -> list[str]:
    # With svg.fonttype=path matplotlib keeps each text as an XML comment.
    return re.findall(r"<!-- (.*?) -->", svg.decode("utf-8"))


def test_l_room_geometry_and_notch_top_right() -> None:
    spec = _spec("polygon_l_room")
    assert g.area(spec.points) == pytest.approx(57.0)
    assert g.inside_or_on((1.0, 6.0), spec.points)  # top-left is floor
    assert not g.inside_or_on((7.5, 6.0), spec.points)  # top-right is the notch


def test_l_room_labels_are_measured_and_each_appears_once() -> None:
    spec = _spec("polygon_l_room")
    labels = [label.text for label in place_labels(spec)]
    assert labels == ["9 m", "5 m", "3 m", "2 m", "6 m", "7 m"]
    texts = _svg_text(render_spec(spec).svg)
    for label in labels:
        assert texts.count(label) == 1


def test_l_room_label_positions_sit_outside_their_edges() -> None:
    spec = _spec("polygon_l_room")
    by_text = {label.text: label for label in place_labels(spec)}
    assert by_text["9 m"].y < 0  # below the bottom edge
    assert by_text["7 m"].x < 0  # left of the left edge
    assert by_text["3 m"].y > 5 and 6 < by_text["3 m"].x < 9  # above the notch floor
    assert by_text["2 m"].x > 6 and 5 < by_text["2 m"].y < 7  # right of the notch wall


def test_split_figure_reuses_the_same_points_and_regions_tile_the_shape() -> None:
    whole = _spec("polygon_l_room")
    split = _spec("polygon_l_room_split")
    assert split.points == whole.points == [tuple(p) for p in L_ROOM_POINTS]
    assert sum(g.area(r.points) for r in split.regions) == pytest.approx(g.area(split.points))
    texts = _svg_text(render_spec(split).svg)
    assert texts.count("A") == 1 and texts.count("B") == 1


def test_render_is_byte_for_byte_repeatable() -> None:
    spec = _spec("polygon_l_room_split")
    first, second = render_spec(spec), render_spec(spec)
    assert first.svg == second.svg
    assert first.png == second.png
    assert first.svg.lstrip().startswith(b"<?xml")
    assert first.png.startswith(b"\x89PNG")


def test_symbol_and_hidden_edges() -> None:
    spec = _spec("polygon_triangle_height")
    labels = {label.text: label for label in place_labels(spec)}
    assert labels["x"].italic
    assert "8 cm" in labels and "5 cm" in labels
    assert len([lab for lab in labels.values() if lab.kind == "edge"]) == 2  # one edge hidden


def test_alt_text_comes_from_the_spec() -> None:
    alt = render_spec(_spec("polygon_l_room_split")).alt_text
    assert "9 m" in alt and "(A, B)" in alt


@pytest.mark.parametrize("name", sorted(GALLERY))
def test_every_gallery_spec_renders(name: str) -> None:
    rendered = render_spec(_ADAPTER.validate_python(GALLERY[name]))
    assert rendered.svg and rendered.png and rendered.alt_text


def test_cross_check_flags_numbers_missing_from_text() -> None:
    spec = _spec("polygon_l_room")
    full = "The room is 9 m by 7 m. An alcove 3 m wide and 2 m deep is cut out; the walls are 5 m and 6 m."
    assert cross_check_numbers(spec, [full]) == []
    warnings = cross_check_numbers(spec, ["The room is 9 m by 7 m."])
    assert len(warnings) == 1 and "5, 3, 2, 6" in warnings[0]
    # 19 must not count as a mention of 9.
    assert cross_check_numbers(spec, ["19 m 17 m 13 m 12 m 15 m 16 m"]) != []


def test_layout_check_catches_text_over_a_line() -> None:
    from matplotlib.figure import Figure

    from media.render.layout import find_clashes

    fig = Figure(figsize=(3, 3))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    (line,) = ax.plot([5, 5], [0, 10])
    over = ax.text(5, 5, "4 cm", ha="center", va="center")
    clear = ax.text(1, 1, "9 m")
    assert find_clashes(fig, [over, clear], [line]) == [("4 cm", "<line>")]


def test_height_label_is_placed_on_the_roomier_side() -> None:
    spec = _spec("polygon_trapezium")
    height = next(label for label in place_labels(spec) if label.kind == "segment")
    assert height.x > 2  # right of the height line, away from the slanted left edge

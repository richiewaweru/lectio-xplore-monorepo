"""Reference specs for every implemented family.

Used by the review gallery (``scripts/render_gallery.py``) and by tests, so the
figures a human approves are the same ones the snapshot tests pin.
"""

from __future__ import annotations

from typing import Any

L_ROOM_POINTS = [[0, 0], [9, 0], [9, 5], [6, 5], [6, 7], [0, 7]]

POLYGON_GALLERY: dict[str, dict[str, Any]] = {
    "polygon_l_room": {
        "family": "polygon_area",
        "points": L_ROOM_POINTS,
        "unit": "m",
        "edge_labels": [{"edge": i} for i in range(6)],
        "mark_right_angles": True,
    },
    "polygon_l_room_split": {
        "family": "polygon_area",
        "points": L_ROOM_POINTS,
        "unit": "m",
        "edge_labels": [{"edge": 0}, {"edge": 2}, {"edge": 3}, {"edge": 5}],
        "segments": [{"start": [6, 0], "end": [6, 5]}],
        "regions": [
            {"points": [[0, 0], [6, 0], [6, 7], [0, 7]], "label": "A"},
            {"points": [[6, 0], [9, 0], [9, 5], [6, 5]], "label": "B"},
        ],
    },
    "polygon_l_room_grid": {
        "family": "polygon_area",
        "points": L_ROOM_POINTS,
        "segments": [{"start": [6, 0], "end": [6, 5], "style": "solid", "label": "cut"}],
        "regions": [
            {"points": [[0, 0], [6, 0], [6, 7], [0, 7]], "label": "A"},
            {"points": [[6, 0], [9, 0], [9, 5], [6, 5]], "label": "B"},
        ],
        "grid": True,
    },
    "polygon_triangle_height": {
        "family": "polygon_area",
        "points": [[0, 0], [8, 0], [3, 5]],
        "unit": "cm",
        "edge_labels": [
            {"edge": 0},
            {"edge": 1, "kind": "hidden"},
            {"edge": 2, "kind": "symbol", "text": "x"},
        ],
        "segments": [{"start": [3, 0], "end": [3, 5], "label": "5 cm", "right_angle_at": "start"}],
    },
    "polygon_trapezium": {
        "family": "polygon_area",
        "points": [[0, 0], [10, 0], [7, 4], [2, 4]],
        "unit": "cm",
        "edge_labels": [{"edge": 0}, {"edge": 1}, {"edge": 2}, {"edge": 3, "kind": "hidden"}],
        "segments": [{"start": [2, 0], "end": [2, 4], "label": "4 cm", "right_angle_at": "start"}],
    },
}


def _all_families() -> dict[str, dict[str, Any]]:
    from media.render.families import bar_chart, cycle, flow, function_graph, number_line

    merged = dict(POLYGON_GALLERY)
    for module in (number_line, bar_chart, function_graph, flow, cycle):
        merged.update(module.GALLERY)
    return merged


GALLERY: dict[str, dict[str, Any]] = _all_families()


__all__ = ["GALLERY", "L_ROOM_POINTS", "POLYGON_GALLERY"]

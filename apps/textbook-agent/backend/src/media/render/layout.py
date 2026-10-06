"""Shared layout checks: labels must not collide with each other or with lines."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from matplotlib.artist import Artist
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.text import Text

from media.render.contracts import RenderLayoutError
from media.render.style import FONT_SIZE, MIN_FONT_SIZE

_PAD_PX = 2.0

# build(font_size) -> (figure, labels to keep clear, line artists labels must not cross)
Build = Callable[[float], tuple[Figure, Sequence[Text], Sequence[Artist]]]


def find_clashes(
    fig: Figure, texts: Sequence[Text], obstacles: Sequence[Artist] = ()
) -> list[tuple[str, str]]:
    canvas = fig.canvas if isinstance(fig.canvas, FigureCanvasAgg) else FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    boxes = [
        (t.get_text(), t.get_window_extent(renderer).padded(_PAD_PX))
        for t in texts
        if t.get_text().strip()
    ]
    clashes: list[tuple[str, str]] = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][1].overlaps(boxes[j][1]):
                clashes.append((boxes[i][0], boxes[j][0]))
    paths = [artist.get_transform().transform_path(artist.get_path()) for artist in obstacles]
    for text, box in boxes:
        if any(path.intersects_bbox(box, filled=False) for path in paths):
            clashes.append((text, "<line>"))
    return clashes


def fit_labels(build: Build) -> Figure:
    """Draw at the house font size, shrinking to the print minimum if labels clash."""
    size = float(FONT_SIZE)
    clashes: list[tuple[str, str]] = []
    while size >= MIN_FONT_SIZE:
        fig, texts, obstacles = build(size)
        clashes = find_clashes(fig, texts, obstacles)
        if not clashes:
            return fig
        size -= 1.0
    detail = ", ".join(f"{a!r}/{b!r}" for a, b in clashes[:3])
    raise RenderLayoutError(f"labels overlap at the minimum print size: {detail}")


__all__ = ["Build", "find_clashes", "fit_labels"]

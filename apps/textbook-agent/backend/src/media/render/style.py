"""House style shared by every render family.

matplotlib keeps rcParams in process-global state, so all drawing and export
happens inside ``drawing()``: one lock plus one rc context. Renders take
milliseconds, so serialising them is cheaper than reasoning about shared state.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import matplotlib

matplotlib.use("Agg")

from matplotlib import rc_context  # noqa: E402

RENDERER_VERSION = "render/1"

INK = "#1f2933"
MUTED = "#52606d"
GRID = "#d9dee4"
SHADES = ("#dbe4ee", "#b9c9da", "#eef2f6", "#9fb3c8", "#cfd8e2", "#e6ebf0")
FILL = "#eef2f6"
BACKGROUND = "#ffffff"

LINE = 2.0
THIN = 1.2
FONT_SIZE = 13
MIN_FONT_SIZE = 9
LABEL_FONT_SIZE = 14
PNG_DPI = 200

RC = {
    "font.family": "DejaVu Sans",
    "font.size": FONT_SIZE,
    "text.color": INK,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.unicode_minus": True,
    # Text becomes outlines: identical on every machine and printer.
    "svg.fonttype": "path",
    # Fixed salt keeps SVG element ids, and so the bytes, repeatable.
    "svg.hashsalt": "lectio-render",
    "path.simplify": False,
    "savefig.facecolor": BACKGROUND,
}

_LOCK = threading.Lock()


@contextmanager
def drawing() -> Iterator[None]:
    with _LOCK, rc_context(RC):
        yield


__all__ = [
    "BACKGROUND",
    "FILL",
    "FONT_SIZE",
    "GRID",
    "INK",
    "LABEL_FONT_SIZE",
    "LINE",
    "MIN_FONT_SIZE",
    "MUTED",
    "PNG_DPI",
    "RC",
    "RENDERER_VERSION",
    "SHADES",
    "THIN",
    "drawing",
]

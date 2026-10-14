"""``table``: exact values in rows and columns.

Cell text is the value exactly as given: strings unchanged, ints as ``str(int)``
and floats as their shortest round-trip form. Nothing is rounded or reformatted.
Headers and long cells wrap inside their column so text never leaves its cell.
"""

from __future__ import annotations

import math
import re
import textwrap

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.text import Text

from media.render.contracts import RenderLayoutError, RenderSpecError, TableSpec
from media.render.layout import find_clashes
from media.render.style import FILL, FONT_SIZE, INK, MIN_FONT_SIZE, MUTED, SHADES, THIN

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_MAX_CELL_CHARS = 80
_WIDTH = 6.2
_MARGIN = 0.1
_CELL_PAD = 0.09  # inches either side of cell text
_CHAR_EM = 0.62  # conservative average glyph width in em


def cell_text(value: str | float) -> str:
    """The value as shown in the table, with no rounding."""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return repr(float(value))


def _wrap(text: str, chars: int) -> str:
    return "\n".join(textwrap.wrap(text, width=chars, break_long_words=False)) or text


def _column_widths(weights: list[float], minimums: list[float], usable: float) -> list[float]:
    """Share ``usable`` by ``weights`` while every column keeps at least its minimum.

    Columns whose share falls below their minimum are pinned to it and the rest
    is re-shared among the others. When the minimums alone exceed ``usable`` the
    widths follow the minimums and the caller's fit check shrinks the font.
    """
    if sum(minimums) >= usable:
        total = sum(minimums)
        return [usable * m / total for m in minimums]
    pinned: dict[int, float] = {}
    while True:
        free = [i for i in range(len(weights)) if i not in pinned]
        space = usable - sum(pinned.values())
        total = sum(weights[i] for i in free)
        shares = {i: space * weights[i] / total for i in free}
        short = [i for i in free if shares[i] < minimums[i]]
        if not short:
            return [pinned.get(i, shares.get(i, 0.0)) for i in range(len(weights))]
        for i in short:
            pinned[i] = minimums[i]


def _layout(spec: TableSpec, font_size: float) -> tuple[list[float], list[list[str]], list[float]]:
    """Column widths, wrapped cell text (header first) and row heights, in inches."""
    grid = [[*spec.columns]] + [[cell_text(c) for c in row] for row in spec.rows]
    usable = _WIDTH - 2 * _MARGIN
    em_in = font_size / 72.0
    weights = []
    minimums = []
    for col in range(len(spec.columns)):
        longest_word = max(len(w) for row in grid for w in (row[col].split() or [""]))
        longest_cell = max(len(row[col]) for row in grid)
        weights.append(max(4.0, min(float(longest_cell), 22.0), float(longest_word)))
        # A word never breaks, so its column must hold it plus the cell padding.
        minimums.append((longest_word + 1) * em_in * _CHAR_EM + 2 * _CELL_PAD)
    widths = _column_widths(weights, minimums, usable)
    wrapped = [
        [
            _wrap(text, max(3, int((widths[i] - 2 * _CELL_PAD) / (em_in * _CHAR_EM))))
            for i, text in enumerate(row)
        ]
        for row in grid
    ]
    line_h = em_in * 1.35
    heights = [max(t.count("\n") + 1 for t in row) * line_h + 0.2 for row in wrapped]
    return widths, wrapped, heights


def _build(spec: TableSpec, font_size: float) -> tuple[Figure, list[Text]]:
    widths, wrapped, heights = _layout(spec, font_size)
    note_h = (font_size / 72.0) * 1.6 if spec.unit_note else 0.0
    height = sum(heights) + 2 * _MARGIN + note_h
    fig = Figure(figsize=(_WIDTH, height))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, _WIDTH)
    ax.set_ylim(height, 0)
    ax.axis("off")
    texts: list[Text] = []
    y = _MARGIN
    for r, row in enumerate(wrapped):
        x = _MARGIN
        row_h = heights[r]
        shade = SHADES[1] if r == 0 else (FILL if r % 2 == 0 else "#ffffff")
        for c, text in enumerate(row):
            ax.add_patch(
                Rectangle((x, y), widths[c], row_h, facecolor=shade, edgecolor=INK, linewidth=THIN)
            )
            texts.append(
                ax.text(
                    x + widths[c] / 2,
                    y + row_h / 2,
                    text,
                    ha="center",
                    va="center",
                    fontsize=font_size,
                    fontweight="bold" if r == 0 else "normal",
                    linespacing=1.2,
                )
            )
            x += widths[c]
        y += row_h
    if spec.unit_note:
        ax.text(
            _MARGIN,
            y + note_h * 0.6,
            spec.unit_note,
            ha="left",
            va="center",
            fontsize=font_size - 1,
            color=MUTED,
        )
    return fig, texts


def _overflowing(fig: Figure, spec: TableSpec, font_size: float, texts: list[Text]) -> list[str]:
    widths, _, heights = _layout(spec, font_size)
    canvas = fig.canvas if isinstance(fig.canvas, FigureCanvasAgg) else FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    n_cols = len(widths)
    bad: list[str] = []
    for index, text in enumerate(texts):
        col, row = index % n_cols, index // n_cols
        box = text.get_window_extent(renderer)
        w_in, h_in = box.width / fig.dpi, box.height / fig.dpi
        if w_in > widths[col] - _CELL_PAD or h_in > heights[row] - 0.04:
            bad.append(text.get_text())
    return bad


def draw(spec: TableSpec) -> Figure:
    size = float(FONT_SIZE)
    problem = ""
    while size >= MIN_FONT_SIZE:
        fig, texts = _build(spec, size)
        overflow = _overflowing(fig, spec, size, texts)
        if not overflow and not find_clashes(fig, texts):
            return fig
        problem = ", ".join(repr(t) for t in overflow[:3]) or "cells overlap"
        size -= 1.0
    raise RenderLayoutError(
        f"table text does not fit its cells at the minimum print size: {problem}"
    )


def validate(spec: TableSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    n = len(spec.columns)
    seen: set[str] = set()
    for index, column in enumerate(spec.columns):
        key = column.strip().casefold()
        if key in seen:
            errors.append(
                RenderSpecError(
                    "duplicate_column",
                    f"columns[{index}]",
                    f"column {column!r} appears twice; rename one",
                )
            )
        seen.add(key)
    for r_index, row in enumerate(spec.rows):
        if len(row) != n:
            errors.append(
                RenderSpecError(
                    "row_length_mismatch",
                    f"rows[{r_index}]",
                    f"row has {len(row)} cells but there are {n} columns; "
                    "give exactly one cell per column",
                )
            )
            continue
        for c_index, value in enumerate(row):
            path = f"rows[{r_index}][{c_index}]"
            if isinstance(value, str):
                if not value.strip():
                    errors.append(
                        RenderSpecError("empty_cell", path, "cell text must not be blank")
                    )
                elif len(value) > _MAX_CELL_CHARS:
                    errors.append(
                        RenderSpecError(
                            "cell_too_long",
                            path,
                            f"cell text is {len(value)} characters; use at most {_MAX_CELL_CHARS}",
                        )
                    )
            elif isinstance(value, float) and not math.isfinite(value):
                errors.append(RenderSpecError("non_finite_value", path, "numbers must be finite"))
    return errors


def describe(spec: TableSpec) -> str:
    parts = [f"Table with columns {', '.join(spec.columns)}"]
    for index, row in enumerate(spec.rows, start=1):
        cells = ", ".join(f"{c} {cell_text(v)}" for c, v in zip(spec.columns, row))
        parts.append(f"row {index}: {cells}")
    text = "; ".join(parts) + "."
    if spec.unit_note:
        text += f" {spec.unit_note}"
    return text


def numbers(spec: TableSpec) -> list[float]:
    out: list[float] = []
    for row in spec.rows:
        for value in row:
            if isinstance(value, str):
                out.extend(float(m) for m in _NUMBER.findall(value))
            else:
                out.append(float(value))
    return out


GALLERY: dict[str, dict] = {
    "table_weekly_growth": {
        "family": "table",
        "columns": ["Day", "Seedling A height (cm)", "Seedling B height (cm)"],
        "rows": [[0, 5, 5], [7, 12, 6], [14, 22, 7], [21, 35, 8], [28, 48.5, 9]],
        "unit_note": "Heights measured at the start of each day.",
    },
}

__all__ = ["GALLERY", "cell_text", "describe", "draw", "numbers", "validate"]

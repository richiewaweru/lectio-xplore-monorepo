"""Build a ``table`` render spec straight from a figure's exact data.

When a plan carries numbers for a figure, the table is built by code from those
numbers, so no model can alter, round or invent a value. Pure functions; this
module must stay independent of ``document`` and ``curriculum``.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from media.render.contracts import TableSpec

_UNIT_TOKENS = frozenset(
    {"cm", "mm", "m", "km", "kg", "g", "mg", "s", "ms", "min", "ml", "l", "pct", "degc", "degf"}
)
_UNIT_SYMBOLS = {"pct": "%", "degc": "°C", "degf": "°F"}
_HEADER_MAX = 40


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_data_figure(data: dict | None) -> bool:
    """True when some value is a list of two or more numbers (a series)."""
    if not isinstance(data, dict):
        return False
    return any(
        isinstance(v, list) and len(v) >= 2 and all(_is_number(x) for x in v) for v in data.values()
    )


def readable_key(key: str) -> str:
    """``height_seedling_a_cm`` -> ``Height seedling a (cm)``."""
    tokens = [t for t in re.split(r"[_\s]+", key.strip()) if t]
    if not tokens:
        return ""
    unit = ""
    if len(tokens) > 1 and tokens[-1].lower() in _UNIT_TOKENS:
        raw = tokens.pop().lower()
        unit = _UNIT_SYMBOLS.get(raw, raw)
    text = " ".join(tokens)
    text = text[0].upper() + text[1:]
    return f"{text} ({unit})" if unit else text


def _cell_ok(value: Any) -> bool:
    return _is_number(value) or isinstance(value, str)


def spec_from_data(
    data: dict | None,
    labels_required: list[str] | None = None,
    must_show: list[str] | None = None,
) -> TableSpec | None:
    """A table of ``data`` (one column per key, one row per index), or ``None``.

    ``None`` means the data is not a clean set of equal-length series, or would not
    fit the table limits; the caller then falls through to its other routes.
    ``must_show`` is accepted for call-site symmetry and does not affect the table.
    """
    if not isinstance(data, dict) or not data:
        return None
    series = list(data.values())
    if not all(isinstance(v, list) for v in series):
        return None
    length = len(series[0])
    if length < 2 or any(len(v) != length for v in series):
        return None
    if not all(_cell_ok(x) for v in series for x in v):
        return None
    labels = [str(label).strip() for label in labels_required or []]
    if len(labels) == len(data) and all(labels):
        headers = labels
    else:
        headers = [readable_key(str(key)) for key in data]
    if any(not h or len(h) > _HEADER_MAX for h in headers):
        return None
    rows = [[column[i] for column in series] for i in range(length)]
    try:
        return TableSpec(columns=headers, rows=rows)
    except ValidationError:
        return None


__all__ = ["is_data_figure", "readable_key", "spec_from_data"]

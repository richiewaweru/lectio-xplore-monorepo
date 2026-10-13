"""Numbers a figure may show: the figure's own data and approved facts only.

A spec or required label carrying a number outside this set is rejected, so
no model can invent a value. Pure functions over the work order; this module
must stay independent of ``document`` and ``curriculum``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from media.generation.contracts import VisualGeneratorWorkOrder
from media.render.data_spec import is_data_figure

# A leading minus counts only when it is not glued to a preceding word character,
# so "5-10" reads as 5 and 10 and "Day-7" as 7.
_NUMBER = re.compile(r"(?:(?<![\w.])-)?\d+(?:\.\d+)?")
_CONTEXT_PREFIX = "context:"


def _normalise(raw: str | int | float) -> Decimal | None:
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    value = value.normalize()
    return Decimal(0) if value == 0 else value


def numbers_in(text: str) -> set[Decimal]:
    """Numeric tokens of ``text`` as normalised Decimals (``5`` equals ``5.0``)."""
    found: set[Decimal] = set()
    for token in _NUMBER.findall(text or ""):
        value = _normalise(token)
        if value is not None:
            found.add(value)
    return found


def numbers_of(values: Any) -> set[Decimal]:
    """Numbers in raw numbers, strings and nested lists or dicts (dict keys ignored)."""
    if isinstance(values, bool) or values is None:
        return set()
    if isinstance(values, (int, float)):
        value = _normalise(values)
        return {value} if value is not None else set()
    if isinstance(values, str):
        return numbers_in(values)
    found: set[Decimal] = set()
    if isinstance(values, dict):
        values = list(values.values())
    if isinstance(values, Iterable):
        for item in values:
            found |= numbers_of(item)
    return found


def allowed_numbers(order: VisualGeneratorWorkOrder) -> set[Decimal]:
    """Data, must_show, labels_required and approved (non ``context:``) source facts."""
    visual = order.visual
    allowed = numbers_of(visual.data) | numbers_of(list(visual.must_show))
    allowed |= numbers_of(list(visual.labels_required))
    for entry in order.source_of_truth:
        if not entry.key.startswith(_CONTEXT_PREFIX):
            allowed |= numbers_in(entry.text)
    return allowed


def with_derived_sides(allowed: set[Decimal]) -> set[Decimal]:
    """``allowed`` plus every pairwise sum and absolute difference (a side found from given sides)."""
    values = sorted(allowed)
    out = set(allowed)
    for i, a in enumerate(values):
        for b in values[i + 1 :]:
            for derived in (a + b, abs(a - b)):
                normalised = _normalise(derived)
                if normalised is not None:
                    out.add(normalised)
    return out


def allowed_numbers_for(order: VisualGeneratorWorkOrder, family: str) -> set[Decimal]:
    """Allowed numbers for a spec family; polygon_area may also show a derived side."""
    allowed = allowed_numbers(order)
    if family == "polygon_area" and not is_data_figure(order.visual.data):
        return with_derived_sides(allowed)
    return allowed


def unsupported_numbers(spec_numbers: Iterable[float | int], allowed: set[Decimal]) -> list[Decimal]:
    """Spec numbers missing from ``allowed``, in first-seen order without repeats."""
    out: list[Decimal] = []
    for raw in spec_numbers:
        value = _normalise(raw)
        if value is not None and value not in allowed and value not in out:
            out.append(value)
    return out


def label_numbers_outside_data(order: VisualGeneratorWorkOrder) -> list[Decimal]:
    """For a data figure: numbers in labels or must_show that the data does not hold."""
    data = order.visual.data
    if not is_data_figure(data):
        return []
    in_data = numbers_of(data)
    shown = numbers_of(list(order.visual.labels_required)) | numbers_of(list(order.visual.must_show))
    return sorted(shown - in_data)


def format_number(value: Decimal) -> str:
    """Plain (non-exponent) text of a normalised Decimal."""
    return format(value, "f")


__all__ = [
    "allowed_numbers",
    "allowed_numbers_for",
    "format_number",
    "label_numbers_outside_data",
    "numbers_in",
    "numbers_of",
    "unsupported_numbers",
    "with_derived_sides",
]

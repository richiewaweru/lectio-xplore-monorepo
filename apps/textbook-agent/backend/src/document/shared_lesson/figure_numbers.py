"""Deterministic, non-blocking check of the numbers a figure's text states.

A figure caption or the section prose around it may only state numbers the
lesson supports: the figure data, approved source facts, the lesson objective,
the block brief and the visual's labels. Anything else is recorded as a
warning (never gating). For a data figure the text should also state at least
one of the data values.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

from media.render.data_spec import is_data_figure
from media.render.number_guard import format_number, numbers_in, numbers_of

NUMBER_UNSUPPORTED_PREFIX = "number_unsupported:"
VALUE_MISSING_PREFIX = "figure_value_missing_in_text:"
NUMBER_WARNING_PREFIXES = (NUMBER_UNSUPPORTED_PREFIX, VALUE_MISSING_PREFIX)


def allowed_text_numbers(
    *,
    data: Mapping[str, Any] | None,
    approved_fact_texts: Iterable[str],
    objective: str,
    brief_and_labels: Iterable[str],
) -> set[Decimal]:
    """Numbers the caption and prose may state."""
    allowed = numbers_of(dict(data)) if data else set()
    for text in (*approved_fact_texts, objective, *brief_and_labels):
        allowed |= numbers_in(text or "")
    return allowed


def _first_data_value(data: Mapping[str, Any]) -> Decimal | None:
    for value in data.values():
        if isinstance(value, list) and value:
            first = numbers_of(value[0])
            if first:
                return min(first)
    return None


def number_warnings(
    *,
    caption: str,
    section_text: str,
    data: Mapping[str, Any] | None,
    allowed: set[Decimal],
) -> list[str]:
    """``number_unsupported:<n>`` per stray number, plus a data-value advisory."""
    stated = numbers_in(caption) | numbers_in(section_text)
    warnings = [
        f"{NUMBER_UNSUPPORTED_PREFIX}{format_number(value)}"
        for value in sorted(stated - allowed)
    ]
    plain = dict(data) if data else None
    if plain and is_data_figure(plain) and not (stated & numbers_of(plain)):
        first = _first_data_value(plain)
        if first is not None:
            warnings.append(f"{VALUE_MISSING_PREFIX}{format_number(first)}")
    return warnings


def without_number_warnings(warnings: Iterable[str]) -> list[str]:
    """``warnings`` minus the figure-number ones (for compatibility comparisons)."""
    return [w for w in warnings if not w.startswith(NUMBER_WARNING_PREFIXES)]

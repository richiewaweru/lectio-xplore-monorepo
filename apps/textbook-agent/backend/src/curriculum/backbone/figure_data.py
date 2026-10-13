"""Deterministic checks that a backbone figure's numbers agree with its own data.

Kept out of the pydantic model on purpose so stored backbones still load; the
backbone writer calls this on freshly generated output and feeds the messages
into its repair prompt.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from curriculum.backbone.models import LessonBackbone

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _numbers_in_text(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(Decimal(token))
        except InvalidOperation:  # pragma: no cover - regex guarantees a number
            continue
    return found


def _numbers_in_value(value: Any) -> set[Decimal]:
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float)):
        return {Decimal(str(value))}
    if isinstance(value, str):
        return _numbers_in_text(value)
    if isinstance(value, dict):
        found: set[Decimal] = set()
        for item in value.values():
            found |= _numbers_in_value(item)
        return found
    if isinstance(value, (list, tuple)):
        found = set()
        for item in value:
            found |= _numbers_in_value(item)
        return found
    return set()


def _fmt(number: Decimal) -> str:
    return format(number.normalize(), "f")


def figure_data_errors(backbone: LessonBackbone) -> list[str]:
    """Return one message per problem; each names the figure id."""
    errors: list[str] = []
    for figure in backbone.figures:
        data = figure.data or {}
        label_numbers: set[Decimal] = set()
        for entry in [*figure.labels_required, *figure.must_show]:
            label_numbers |= _numbers_in_text(str(entry))

        lengths = {
            key: len(value) for key, value in data.items() if isinstance(value, (list, tuple))
        }
        if len(set(lengths.values())) > 1:
            detail = ", ".join(f"{key}={size}" for key, size in lengths.items())
            errors.append(
                f"BACKBONE_FIGURE_SERIES_LENGTH: figure {figure.id} data series have "
                f"unequal lengths ({detail}); every series needs one value per label"
            )

        if not label_numbers:
            continue
        if not data:
            errors.append(
                f"BACKBONE_FIGURE_DATA_MISSING: figure {figure.id} labels or must_show "
                "contain numbers but data is empty; put every number in data"
            )
            continue
        missing = sorted(label_numbers - _numbers_in_value(data))
        if missing:
            listed = ", ".join(_fmt(number) for number in missing)
            errors.append(
                f"BACKBONE_FIGURE_LABEL_NUMBER: figure {figure.id} labels or must_show "
                f"use number(s) {listed} that are not in its data"
            )
    return errors


__all__ = ["figure_data_errors"]

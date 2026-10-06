"""Spec validation (structural, feeds repair) and the text cross-check (soft)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from media.render.contracts import RenderSpecError
from media.render.families import renderer_for
from media.render.geometry import format_number


def validate_spec(spec: object) -> list[RenderSpecError]:
    """Every structural problem with ``spec``; empty means it can be drawn."""
    family = getattr(spec, "family", None)
    renderer = renderer_for(str(family))
    if renderer is None:
        return [RenderSpecError("unsupported_family", "family", f"no renderer for {family!r}")]
    return renderer.validate(spec)


def _mentions(value: float, text: str) -> bool:
    shown = format_number(value)
    forms = {shown}
    if "." not in shown:
        forms.add(f"{shown}.0")
    return any(re.search(rf"(?<![\d.]){re.escape(form)}(?![\d])", text) for form in forms)


def cross_check_numbers(spec: object, context_texts: Iterable[str]) -> list[str]:
    """Warnings for computed values the lesson text never states.

    A miss is a signal for the teacher, not a reason to withhold the figure:
    the figure may be right and the text simply silent.
    """
    renderer = renderer_for(str(getattr(spec, "family", "")))
    if renderer is None:
        return []
    text = "\n".join(context_texts)
    missing: list[str] = []
    for value in renderer.numbers(spec):
        shown = format_number(value)
        if not _mentions(value, text) and shown not in missing:
            missing.append(shown)
    if not missing:
        return []
    return [f"figure shows {', '.join(missing)} but the lesson text does not state {'it' if len(missing) == 1 else 'them'}"]


__all__ = ["cross_check_numbers", "validate_spec"]

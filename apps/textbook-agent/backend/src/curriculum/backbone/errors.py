"""Typed failure for the backbone writer (maps to error_code ``backbone_invalid``)."""

from __future__ import annotations

from collections.abc import Iterable


class BackboneOutputInvalidError(RuntimeError):
    """Backbone output stayed invalid after the outer attempt budget."""

    def __init__(self, *, attempt_count: int, details: Iterable[str]) -> None:
        normalized = tuple(
            text for detail in details for text in (str(detail).strip(),) if text
        )
        self.attempt_count = attempt_count
        self.details = normalized
        suffix = f": {'; '.join(normalized)}" if normalized else ""
        super().__init__(
            f"backbone generation returned invalid output after {attempt_count} attempts{suffix}"
        )


__all__ = ["BackboneOutputInvalidError"]

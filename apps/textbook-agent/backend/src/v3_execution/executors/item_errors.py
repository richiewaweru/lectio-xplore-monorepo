"""Typed failures for item-generation retry/recovery."""

from __future__ import annotations

from collections.abc import Iterable


class ItemGenerationOutputInvalidError(RuntimeError):
    """Item-generation output stayed invalid after the outer attempt budget."""

    def __init__(
        self,
        *,
        attempt_count: int,
        details: Iterable[str],
    ) -> None:
        normalized = tuple(
            text for detail in details for text in (str(detail).strip(),) if text
        )
        self.attempt_count = attempt_count
        self.details = normalized
        suffix = f": {'; '.join(normalized)}" if normalized else ""
        super().__init__(
            "item generation returned invalid output after "
            f"{attempt_count} attempts{suffix}"
        )


__all__ = ["ItemGenerationOutputInvalidError"]


"""Narrow failure types for the whole-lesson teaching planner boundary."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior


class TeachingPlanOutputInvalidError(RuntimeError):
    """The provider returned teaching output that stayed invalid after repair."""

    def __init__(
        self,
        *,
        attempt_count: int,
        details: Iterable[str],
    ) -> None:
        normalized = tuple(text for detail in details if (text := str(detail).strip()))
        self.attempt_count = attempt_count
        self.details = normalized
        suffix = f": {'; '.join(normalized)}" if normalized else ""
        super().__init__(
            "lesson approach planner returned invalid output after "
            f"{attempt_count} attempts{suffix}"
        )


def is_recognized_teaching_output_error(exc: BaseException) -> bool:
    """Recognize schema/output-validation failures without widening generic errors."""
    if isinstance(exc, ValidationError):
        return True
    if not isinstance(exc, UnexpectedModelBehavior):
        return False

    messages: list[str] = [str(exc), str(getattr(exc, "message", ""))]
    cause = getattr(exc, "__cause__", None)
    seen: set[int] = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, ValidationError):
            return True
        messages.extend((type(cause).__name__, str(cause)))
        cause = getattr(cause, "__cause__", None)

    joined = " ".join(messages).lower()
    return "exceeded maximum output retries" in joined or (
        "exceeded maximum retries" in joined
        and ("output validation" in joined or "result validation" in joined)
    )

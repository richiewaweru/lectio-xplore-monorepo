from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol


class GenerationCommand(Protocol):
    generation_id: str | None
    subject: str
    context: str
    grade_band: str
    template_id: str
    preset_id: str
    learner_fit: str
    section_count: int


class GenerationResult(Protocol):
    document: Any
    completed_nodes: list[str]
    generation_time_seconds: float


class GenerationEngine(Protocol):
    async def run_streaming(
        self,
        command: GenerationCommand,
        on_event: Callable[[Any], Awaitable[None] | None] | None = None,
    ) -> GenerationResult: ...

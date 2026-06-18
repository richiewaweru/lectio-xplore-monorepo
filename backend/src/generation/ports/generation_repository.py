from abc import ABC, abstractmethod
from datetime import datetime

from generation.entities.generation import Generation


class GenerationRepository(ABC):
    """Abstract repository for generation job persistence."""

    @abstractmethod
    async def create(self, generation: Generation) -> Generation: ...

    @abstractmethod
    async def update_status(
        self,
        generation_id: str,
        status: str,
        document_path: str | None = None,
        error: str | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
        resolved_template_id: str | None = None,
        resolved_preset_id: str | None = None,
        quality_passed: bool | None = None,
        generation_time_seconds: float | None = None,
    ) -> None: ...

    @abstractmethod
    async def find_by_id(self, generation_id: str) -> Generation | None: ...

    @abstractmethod
    async def list_by_user(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> list[Generation]: ...

    @abstractmethod
    async def count_active_by_user(self, user_id: str) -> int: ...

    @abstractmethod
    async def update_heartbeat(
        self,
        generation_id: str,
        heartbeat_at: datetime | None = None,
    ) -> None: ...


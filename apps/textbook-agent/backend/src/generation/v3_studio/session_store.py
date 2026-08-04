from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.models import ProductionBlueprint


@dataclass
class StoredBlueprint:
    blueprint: ProductionBlueprint
    template_id: str
    form: V3InputForm | None = None
    planning_source: dict[str, Any] | None = None


class V3StudioSessionStore:
    """In-memory blueprint sessions and v3 generation SSE queues (single-worker deployments)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._blueprints: dict[tuple[str, str], StoredBlueprint] = {}
        self._chunked_queues: dict[str, asyncio.Queue[str | None]] = {}
        self._generation_queues: dict[str, asyncio.Queue[str | None]] = {}
        self._owners: dict[str, str] = {}
        self._generation_blueprint: dict[str, str] = {}
        self._print_snapshots: dict[str, dict] = {}

    async def put_blueprint(
        self,
        user_id: str,
        blueprint_id: str,
        blueprint: ProductionBlueprint,
        template_id: str,
        form: V3InputForm | None = None,
        planning_source: dict[str, Any] | None = None,
    ) -> None:
        async with self._lock:
            self._blueprints[(user_id, blueprint_id)] = StoredBlueprint(
                blueprint=blueprint,
                template_id=template_id,
                form=form,
                planning_source=planning_source,
            )

    async def get_blueprint(self, user_id: str, blueprint_id: str) -> StoredBlueprint | None:
        async with self._lock:
            return self._blueprints.get((user_id, blueprint_id))

    async def delete_blueprint(self, user_id: str, blueprint_id: str) -> None:
        async with self._lock:
            self._blueprints.pop((user_id, blueprint_id), None)

    async def register_chunked_stream(
        self,
        *,
        user_id: str,
        generation_id: str,
        blueprint_id: str,
        queue: asyncio.Queue[str | None],
    ) -> None:
        async with self._lock:
            self._chunked_queues[generation_id] = queue
            self._owners[generation_id] = user_id
            self._generation_blueprint[generation_id] = blueprint_id

    async def register_generation_stream(
        self,
        *,
        user_id: str,
        generation_id: str,
        blueprint_id: str,
        queue: asyncio.Queue[str | None],
    ) -> None:
        async with self._lock:
            self._generation_queues[generation_id] = queue
            self._owners[generation_id] = user_id
            self._generation_blueprint[generation_id] = blueprint_id

    async def get_chunked_queue(self, generation_id: str) -> asyncio.Queue[str | None] | None:
        async with self._lock:
            return self._chunked_queues.get(generation_id)

    async def get_generation_queue(self, generation_id: str) -> asyncio.Queue[str | None] | None:
        async with self._lock:
            return self._generation_queues.get(generation_id)

    async def owns_generation(self, user_id: str, generation_id: str) -> bool:
        async with self._lock:
            return self._owners.get(generation_id) == user_id

    async def get_generation_owner(self, generation_id: str) -> str | None:
        async with self._lock:
            return self._owners.get(generation_id)

    async def get_blueprint_for_generation(self, generation_id: str) -> StoredBlueprint | None:
        async with self._lock:
            user_id = self._owners.get(generation_id)
            blueprint_id = self._generation_blueprint.get(generation_id)
        if user_id is None or blueprint_id is None:
            return None
        return await self.get_blueprint(user_id, blueprint_id)

    async def get_blueprint_id_for_generation(self, generation_id: str) -> str | None:
        async with self._lock:
            return self._generation_blueprint.get(generation_id)

    async def put_print_snapshot(self, generation_id: str, payload: dict) -> None:
        async with self._lock:
            self._print_snapshots[generation_id] = payload

    async def get_print_snapshot(self, generation_id: str) -> dict | None:
        async with self._lock:
            snap = self._print_snapshots.get(generation_id)
            return dict(snap) if snap is not None else None

    async def delete_print_snapshot(self, generation_id: str) -> None:
        async with self._lock:
            self._print_snapshots.pop(generation_id, None)

    async def cleanup_chunked_stream(self, generation_id: str) -> None:
        async with self._lock:
            self._chunked_queues.pop(generation_id, None)

    async def cleanup_generation_stream(self, generation_id: str) -> None:
        """Drop the execution SSE queue when the stream ends; retain owner/blueprint for PDF and lookups."""
        async with self._lock:
            self._generation_queues.pop(generation_id, None)


v3_studio_store = V3StudioSessionStore()

__all__ = ["StoredBlueprint", "V3StudioSessionStore", "v3_studio_store"]

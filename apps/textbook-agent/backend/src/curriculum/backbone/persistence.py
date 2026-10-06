"""Backbone persistence inside the preparation's chunked state.

Storage keys (siblings of, never inside, ``structural_plan`` / ``context``, so
the Preparation Run's source hash is unaffected):

* ``chunked_state["backbone"] = {"backbone": {...}, "hash": "<sha256>", "input_hash": "..."}``
* ``chunked_state["backbone_generation"] = {"attempts": [...], "failures": [...], "updated_at": ...}``

Writers lock the generation row (``SELECT ... FOR UPDATE``) because
``persist_chunked_state`` is an unlocked read-modify-write.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from curriculum.backbone.models import LessonBackbone, backbone_hash
from curriculum.planning.persistence import load_chunked_state, persist_chunked_state

LOGGER = logging.getLogger(__name__)

BACKBONE_KEY = "backbone"
BACKBONE_JOURNAL_KEY = "backbone_generation"


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _attempt_key(record: dict[str, Any]) -> tuple[str, int]:
    return str(record.get("correlation_id") or ""), int(record.get("attempt") or 0)


async def _lock_generation(session: AsyncSession, generation_id: str) -> None:
    await session.execute(
        select(GenerationModel.id).where(GenerationModel.id == generation_id).with_for_update()
    )


def _merged_journal(
    current: dict[str, Any],
    *,
    attempts: list[dict[str, Any]],
    error: str | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    journal = dict(current.get(BACKBONE_JOURNAL_KEY) or {})
    existing = [dict(r) for r in (journal.get("attempts") or []) if isinstance(r, dict)]
    seen = {_attempt_key(r) for r in existing}
    for record in attempts:
        if isinstance(record, dict) and _attempt_key(record) not in seen:
            seen.add(_attempt_key(record))
            existing.append(dict(record))
    journal["attempts"] = existing
    failures = [dict(r) for r in (journal.get("failures") or []) if isinstance(r, dict)]
    if error:
        failures.append(
            {"correlation_id": correlation_id, "error": error[:500], "recorded_at": _stamp()}
        )
    journal["failures"] = failures
    journal["updated_at"] = _stamp()
    return journal


async def append_backbone_journal(
    session: AsyncSession,
    generation_id: str,
    *,
    attempts: list[dict[str, Any]],
    error: str | None = None,
    correlation_id: str | None = None,
) -> None:
    """Append attempt records (and an optional failure) under the generation lock."""
    if not attempts and not error:
        return
    await _lock_generation(session, generation_id)
    current = await load_chunked_state(generation_id, session)
    await persist_chunked_state(
        generation_id,
        {
            BACKBONE_JOURNAL_KEY: _merged_journal(
                current, attempts=attempts, error=error, correlation_id=correlation_id
            )
        },
        session,
    )


async def store_backbone(
    session: AsyncSession,
    generation_id: str,
    backbone: LessonBackbone,
    *,
    input_hash: str,
    attempts: list[dict[str, Any]] | None = None,
    correlation_id: str | None = None,
) -> str:
    """Persist the backbone + journal atomically under the generation lock; returns its hash."""
    await _lock_generation(session, generation_id)
    current = await load_chunked_state(generation_id, session)
    digest = backbone_hash(backbone)
    await persist_chunked_state(
        generation_id,
        {
            BACKBONE_KEY: {
                "backbone": backbone.model_dump(mode="json"),
                "hash": digest,
                "input_hash": input_hash,
            },
            BACKBONE_JOURNAL_KEY: _merged_journal(
                current,
                attempts=list(attempts or []),
                error=None,
                correlation_id=correlation_id,
            ),
        },
        session,
    )
    return digest


def _record_from_state(state: dict[str, Any]) -> tuple[LessonBackbone, str, str | None] | None:
    raw = state.get(BACKBONE_KEY)
    if not isinstance(raw, dict) or not isinstance(raw.get("backbone"), dict):
        return None
    try:
        backbone = LessonBackbone.model_validate(raw["backbone"])
    except ValidationError:
        LOGGER.warning("Stored lesson backbone failed validation; treating as absent")
        return None
    digest = backbone_hash(backbone)
    if raw.get("hash") != digest:
        LOGGER.warning("Stored lesson backbone hash mismatch; treating as absent")
        return None
    input_hash = raw.get("input_hash")
    return backbone, digest, str(input_hash) if input_hash else None


async def load_backbone_record(
    session: AsyncSession, generation_id: str
) -> tuple[LessonBackbone, str, str | None] | None:
    """(backbone, hash, input_hash) or None when absent/invalid."""
    try:
        state = await load_chunked_state(generation_id, session)
    except ValueError:
        return None
    return _record_from_state(state)


async def load_backbone(session: AsyncSession, generation_id: str) -> LessonBackbone | None:
    record = await load_backbone_record(session, generation_id)
    return record[0] if record else None


__all__ = [
    "BACKBONE_JOURNAL_KEY",
    "BACKBONE_KEY",
    "append_backbone_journal",
    "load_backbone",
    "load_backbone_record",
    "store_backbone",
]

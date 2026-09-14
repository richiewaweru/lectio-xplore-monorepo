"""Caller-scoped effect idempotency for save/publish/export (P02 G08)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import CallerEffectKeyModel

EffectKind = Literal["builder_save", "learn_publish", "print_export"]


class EffectPayloadConflictError(Exception):
    """Same effect key reused with a different payload."""


class EffectOwnerMismatchError(Exception):
    """Effect key belongs to a different owner or resource."""


def payload_digest(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def remember_effect(
    session: AsyncSession,
    *,
    owner_user_id: str,
    kind: EffectKind,
    resource_id: str,
    request_key: str,
    payload_hash: str,
    outcome_json: dict[str, Any] | None = None,
) -> tuple[CallerEffectKeyModel, bool]:
    """Insert or reuse a caller effect key. Returns (row, created).

    Conflict when the key exists for this owner/kind/resource with a different hash.
    """
    existing = await session.scalar(
        select(CallerEffectKeyModel).where(
            CallerEffectKeyModel.owner_user_id == owner_user_id,
            CallerEffectKeyModel.kind == kind,
            CallerEffectKeyModel.resource_id == resource_id,
            CallerEffectKeyModel.request_key == request_key,
        )
    )
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise EffectPayloadConflictError(
                "Effect request key reused with a different payload"
            )
        return existing, False

    row = CallerEffectKeyModel(
        owner_user_id=owner_user_id,
        kind=kind,
        resource_id=resource_id,
        request_key=request_key,
        payload_hash=payload_hash,
        outcome_json=outcome_json,
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        raced = await session.scalar(
            select(CallerEffectKeyModel).where(
                CallerEffectKeyModel.owner_user_id == owner_user_id,
                CallerEffectKeyModel.kind == kind,
                CallerEffectKeyModel.resource_id == resource_id,
                CallerEffectKeyModel.request_key == request_key,
            )
        )
        if raced is None:
            raise
        if raced.payload_hash != payload_hash:
            raise EffectPayloadConflictError(
                "Effect request key reused with a different payload"
            ) from None
        return raced, False
    return row, True


__all__ = [
    "EffectKind",
    "EffectOwnerMismatchError",
    "EffectPayloadConflictError",
    "payload_digest",
    "remember_effect",
]

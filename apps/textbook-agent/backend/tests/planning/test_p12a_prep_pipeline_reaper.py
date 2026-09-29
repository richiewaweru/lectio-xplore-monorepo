"""P12A: stage-2 preparation pipeline heartbeat + orphan reaper."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from application.unit_lesson import native_pipeline
from application.unit_lesson.native_pipeline import (
    _PIPELINE_HEARTBEAT_KEY,
    _stamp_pipeline_heartbeat,
    _write_pipeline_heartbeat,
    reap_orphaned_preparation_pipelines,
)
from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory

OWNER_ID = "p12a-reaper-owner"


async def _ensure_user() -> None:
    async with async_session_factory() as session:
        if await session.get(UserModel, OWNER_ID) is None:
            session.add(UserModel(id=OWNER_ID, email="p12a@example.invalid", name="P12A"))
            await session.commit()


def _marker(*, age_seconds: float, boot_id: str = "other-boot") -> dict[str, Any]:
    return {
        "owner_boot_id": boot_id,
        "pid": 1,
        "heartbeat_at": (datetime.now(UTC) - timedelta(seconds=age_seconds)).isoformat(),
    }


async def _seed(
    *, status: str = "running", marker: dict[str, Any] | None = None, stage: str = "stage2_running"
) -> str:
    await _ensure_user()
    gid = str(uuid.uuid4())
    chunked: dict[str, Any] = {"stage": stage, "progress": "items-done"}
    if marker is not None:
        chunked[_PIPELINE_HEARTBEAT_KEY] = marker
    async with async_session_factory() as session:
        session.add(
            GenerationModel(
                id=gid,
                user_id=OWNER_ID,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status=status,
                mode="v3",
                chunked_state_json=chunked,
            )
        )
        await session.commit()
    return gid


async def _load(gid: str) -> GenerationModel:
    async with async_session_factory() as session:
        row = await session.get(GenerationModel, gid)
        assert row is not None
        return row


@pytest.mark.asyncio
async def test_stale_heartbeat_is_reaped_to_recoverable_and_marker_cleared() -> None:
    gid = await _seed(marker=_marker(age_seconds=600))
    await reap_orphaned_preparation_pipelines(threshold_seconds=60)
    row = await _load(gid)
    assert row.status == "failed_recoverable"
    chunked = dict(row.chunked_state_json or {})
    assert _PIPELINE_HEARTBEAT_KEY not in chunked
    page = chunked.get("page_document_v2") or {}
    assert page["execution"]["last_error"]["code"] == "PIPELINE_ORPHANED"
    # Reaping is idempotent.
    await reap_orphaned_preparation_pipelines(threshold_seconds=60)
    assert (await _load(gid)).status == "failed_recoverable"


@pytest.mark.asyncio
async def test_fresh_heartbeat_from_other_process_is_untouched() -> None:
    gid = await _seed(marker=_marker(age_seconds=1, boot_id="live-sibling-process"))
    await reap_orphaned_preparation_pipelines(threshold_seconds=60)
    assert (await _load(gid)).status == "running"


@pytest.mark.asyncio
async def test_unmarked_and_settled_rows_are_untouched() -> None:
    unmarked = await _seed(marker=None)
    approved = await _seed(
        status="awaiting_review", marker=_marker(age_seconds=600), stage="awaiting_review"
    )
    await reap_orphaned_preparation_pipelines(threshold_seconds=60)
    assert (await _load(unmarked)).status == "running"
    assert (await _load(approved)).status == "awaiting_review"


@pytest.mark.asyncio
async def test_row_owned_by_live_task_in_this_process_is_untouched() -> None:
    gid = await _seed(marker=_marker(age_seconds=600))
    blocker = asyncio.Event()
    task = asyncio.create_task(blocker.wait())
    native_pipeline._chunked_stage2_tasks[gid] = task
    try:
        await reap_orphaned_preparation_pipelines(threshold_seconds=60)
        assert (await _load(gid)).status == "running"
    finally:
        blocker.set()
        await task
        native_pipeline._chunked_stage2_tasks.pop(gid, None)


@pytest.mark.asyncio
async def test_heartbeat_write_touches_only_its_own_key() -> None:
    gid = await _seed(marker=None)
    await _stamp_pipeline_heartbeat(gid)
    chunked = dict((await _load(gid)).chunked_state_json or {})
    assert chunked["progress"] == "items-done"
    assert chunked["stage"] == "stage2_running"
    assert chunked[_PIPELINE_HEARTBEAT_KEY]["owner_boot_id"] == native_pipeline._PIPELINE_BOOT_ID
    await _write_pipeline_heartbeat(gid, None)
    chunked = dict((await _load(gid)).chunked_state_json or {})
    assert _PIPELINE_HEARTBEAT_KEY not in chunked
    assert chunked["progress"] == "items-done"

"""Durable generation recovery used during application startup.

Recovery deliberately lives outside any individual generation pipeline.  A
worker restart can leave *any* generation row in ``running``; the row and its
durable state are the only source of truth available to the next process.
Legacy pipeline implementations must not be imported to reconcile that state.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dict_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            decoded = None
        if isinstance(decoded, dict):
            return decoded
    return {}


def _ready_section_ids(document: dict[str, Any]) -> set[str]:
    progress = document.get("progress")
    statuses = progress.get("sections") if isinstance(progress, dict) else None
    if not isinstance(statuses, dict):
        return set()
    return {
        str(section_id)
        for section_id, status in statuses.items()
        if isinstance(section_id, str) and status == "ready"
    }


def _is_durably_complete(state: dict[str, Any], document: dict[str, Any]) -> bool:
    """Return true only when the persisted state says execution completed.

    Presence of a partial document is not enough: treating it as complete would
    make a restarted process expose an incomplete lesson as a successful one.
    """

    stage = str(state.get("stage") or "").strip().lower()
    if stage not in {"complete", "completed"}:
        progress = document.get("progress")
        stage = str(progress.get("stage") or "").strip().lower() if isinstance(progress, dict) else ""
    return stage in {"complete", "completed"} and bool(document)


async def reconcile_stale_generations(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Finalize rows left running by a process restart.

    Completed durable snapshots are promoted to ``completed``.  Every other
    stale run is made terminal and remains readable as a failed/partial
    snapshot, with no attempt to invoke a provider or a retired pipeline.
    The operation is idempotent because it selects only rows still marked
    ``running``.
    """

    async with session_factory() as session:
        result = await session.execute(
            select(GenerationModel).where(GenerationModel.status == "running")
        )
        models = list(result.scalars().all())
        now = _now_naive()
        for model in models:
            state = _dict_value(model.chunked_state_json)
            document = _dict_value(model.document_json)
            ready_ids = _ready_section_ids(document)
            if _is_durably_complete(state, document):
                model.status = "completed"
                model.quality_passed = True
                model.error = None
                model.error_type = None
                model.error_code = None
                state.update(
                    {
                        "stage": "complete",
                        "execution_started": False,
                        "recovered_at": now.isoformat(),
                    }
                )
            else:
                model.status = "failed"
                model.quality_passed = False
                model.error = "Generation was interrupted by a server restart."
                model.error_type = "server_restart"
                model.error_code = "generation_interrupted_by_restart"
                state.update(
                    {
                        "stage": "assembly_blocked" if ready_ids else "failed",
                        "execution_started": False,
                        "failed_blocks": list(state.get("failed_blocks") or []),
                        "recovered_at": now.isoformat(),
                        "error": model.error,
                        "error_type": model.error_type,
                        "error_code": model.error_code,
                    }
                )
            model.chunked_state_json = state
            model.document_json = document or model.document_json
            model.completed_at = now
            model.last_heartbeat = now
            report = _dict_value(model.report_json)
            if report:
                report["process_status"] = "completed" if model.status == "completed" else "failed"
                model.report_json = report
        if models:
            await session.commit()
        return len(models)


__all__ = ["reconcile_stale_generations"]

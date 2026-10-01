"""Restart-safe orchestration for composition and section writing.

The dispatcher advances an already admitted SharedDocument Run.  It derives
section inputs from the persisted semantic-input and composer admission
adapters; callers cannot provide a replacement task or source projection.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from document.shared_lesson.composer_admission import (
    ComposerSectionAdmission,
    admit_composer_work_items,
)
from document.shared_lesson.runtime import (
    SECTION_WRITER_LEASE_SECONDS,
    SectionWriterJob,
    TeachingPlanSource,
    compose_section_work_item,
    verify_teaching_plan_source,
    write_section_work_items,
)
from document.shared_lesson.semantic_inputs import load_verified_semantic_inputs
from document.shared_lesson.writer_admission import (
    WriterSectionAdmission,
    admit_writer_work_items,
)
from infra.generation_runtime import (
    LeaseLostError,
    SourceIdentity,
    WorkItemUnavailable,
    active_work_items,
    get_run_status,
)

LOGGER = logging.getLogger(__name__)


class SectionDispatcherError(ValueError):
    """A section stage cannot be safely advanced."""


@dataclass(frozen=True)
class SectionDispatchOutcome:
    run_id: str
    composer_dispatched: int = 0
    writer_dispatched: int = 0
    writer_preserved: int = 0
    blocked: bool = False


def _expired(item: Any, now: datetime) -> bool:
    expiry = item.lease_expires_at
    if expiry is None:
        return False
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry <= now


def _eligible(item: Any, now: datetime) -> bool:
    return item.status == "queued" or (item.status == "running" and _expired(item, now))


def _active_by_prefix(run: Any, prefix: str) -> dict[str, Any]:
    active = active_work_items(tuple(run.work_items))
    result: dict[str, Any] = {}
    for item in active:
        if item.item_key.startswith(prefix):
            if item.item_key in result:
                raise SectionDispatcherError(f"duplicate active WorkItem {item.item_key!r}")
            result[item.item_key] = item
    return result


class SharedSectionDispatcher:
    """Advance composition and writer leaves on one existing Run."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str,
        composer_provider: Callable[[dict[str, Any]], Any] | None = None,
        writer_provider: Callable[[dict[str, Any]], Any] | None = None,
        lease_seconds: int = 300,
        writer_lease_seconds: int | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if writer_lease_seconds is not None and writer_lease_seconds <= 0:
            raise ValueError("writer_lease_seconds must be positive")
        self.session_factory = session_factory
        self.worker_id = worker_id
        self.composer_provider = composer_provider
        self.writer_provider = writer_provider
        self.lease_seconds = lease_seconds
        self.writer_lease_seconds = max(
            lease_seconds,
            writer_lease_seconds or SECTION_WRITER_LEASE_SECONDS,
        )

    async def run_one(
        self,
        *,
        run_id: str,
        owner_user_id: str,
        source: TeachingPlanSource,
        source_verifier: Callable[..., Any],
        session: Any | None = None,
        now: datetime | None = None,
    ) -> SectionDispatchOutcome:
        """Admit and dispatch eligible composer/writer leaves for one Run."""
        current = now or datetime.now(UTC).replace(tzinfo=None)
        if current.tzinfo is not None:
            current = current.astimezone(UTC).replace(tzinfo=None)

        owns_session = session is None
        if owns_session:
            async with self.session_factory() as admission_session:
                return await self._run_one(
                    admission_session,
                    run_id=run_id,
                    owner_user_id=owner_user_id,
                    source=source,
                    source_verifier=source_verifier,
                    now=current,
                )
        return await self._run_one(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            source_verifier=source_verifier,
            now=current,
        )

    async def _run_one(
        self,
        admission_session: Any,
        *,
        run_id: str,
        owner_user_id: str,
        source: TeachingPlanSource,
        source_verifier: Callable[..., Any],
        now: datetime,
    ) -> SectionDispatchOutcome:
        expected = verify_teaching_plan_source(source)
        observed = source_verifier(admission_session, expected)
        if inspect.isawaitable(observed):
            observed = await observed
        if not isinstance(observed, SourceIdentity) or observed != expected:
            raise SectionDispatcherError("persisted source differs from the admitted Teaching Plan")

        run = await get_run_status(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
        )
        if run is None or run.run_type != "shared_document":
            raise SectionDispatcherError("SharedDocument Run is unavailable to this owner")
        if (
            run.source_artifact_type,
            run.source_artifact_id,
            run.source_revision,
            run.source_hash,
        ) != (
            expected.source_artifact_type,
            expected.source_artifact_id,
            expected.source_revision,
            expected.source_hash,
        ):
            raise SectionDispatcherError("Run source identity differs from the approved source")

        # This read is deliberately authoritative and read-only. Both
        # admission adapters reload the same semantic inputs before creating
        # any composer or writer leaf.
        await load_verified_semantic_inputs(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
        composer_admissions = await admit_composer_work_items(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            source_verifier=source_verifier,
        )
        await admission_session.commit()

        composer_dispatched = await self._dispatch_composers(
            composer_admissions,
            source=source,
            now=now,
        )

        # Reload on the admission session after independent composer sessions
        # have committed. Stale or missing composer leaves stop writer
        # admission; no writer provider call can cross that boundary.
        await admission_session.rollback()
        run = await get_run_status(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
        )
        if run is None:
            raise SectionDispatcherError("SharedDocument Run disappeared during section dispatch")
        composer_leaves = _active_by_prefix(run, "compose:")
        if any(
            composer_leaves.get(f"compose:{section.slot_id}") is None
            or composer_leaves[f"compose:{section.slot_id}"].status != "ready"
            for section in source.plan.sections
        ):
            return SectionDispatchOutcome(
                run_id=run_id,
                composer_dispatched=composer_dispatched,
                blocked=True,
            )

        writer_admissions = await admit_writer_work_items(
            admission_session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
            source_verifier=source_verifier,
        )
        await admission_session.commit()
        writer_dispatched, writer_preserved = await self._dispatch_writers(
            writer_admissions,
            source=source,
            now=now,
        )
        return SectionDispatchOutcome(
            run_id=run_id,
            composer_dispatched=composer_dispatched,
            writer_dispatched=writer_dispatched,
            writer_preserved=writer_preserved,
        )

    async def _dispatch_composers(
        self,
        admissions: tuple[ComposerSectionAdmission, ...],
        *,
        source: TeachingPlanSource,
        now: datetime,
    ) -> int:
        dispatched = 0
        for admission in admissions:
            async with self.session_factory() as stage_session:
                # Composer runtime claims the generic leaf and accepts an
                # expired running leaf through the same lease primitive.
                # Pydantic admission objects do not carry ORM state. Query the
                # generic WorkItem explicitly instead of trusting a caller map.
                from infra.database.models import GenerationWorkItemModel

                item = await stage_session.get(GenerationWorkItemModel, admission.work_item_id)
                if item is None or not _eligible(item, now):
                    continue
                try:
                    await compose_section_work_item(
                        stage_session,
                        work_item_id=item.id,
                        worker_id=self.worker_id,
                        source=source,
                        section=admission.section,
                        tasks=admission.tasks,
                        sources=admission.sources,
                        provider=self.composer_provider,
                        lease_seconds=self.lease_seconds,
                    )
                    await stage_session.commit()
                    dispatched += 1
                except (LeaseLostError, WorkItemUnavailable):
                    # Claim rejection or a lost fence did not produce a
                    # durable execution failure. Roll back only this stage
                    # session and let the next poll/retry own the item.
                    await stage_session.rollback()
                except Exception:
                    # The corrected composer runtime records a typed failure
                    # under its live lease before raising. Commit only when a
                    # fresh read proves that durable state exists; otherwise
                    # do not erase a live lease or hide a programming error.
                    fresh = await stage_session.get(GenerationWorkItemModel, item.id)
                    if fresh is None or fresh.status not in {
                        "failed_recoverable",
                        "failed_terminal",
                    }:
                        await stage_session.rollback()
                        raise
                    try:
                        await stage_session.commit()
                    except Exception:
                        await stage_session.rollback()
                        raise
                    LOGGER.exception("section composer failed for %s", item.id)
        return dispatched

    async def _dispatch_writers(
        self,
        admissions: tuple[WriterSectionAdmission, ...],
        *,
        source: TeachingPlanSource,
        now: datetime,
    ) -> tuple[int, int]:
        selected: list[tuple[WriterSectionAdmission, Any, Any]] = []
        preserved = 0
        async with AsyncExitStack() as stack:
            from infra.database.models import GenerationWorkItemModel

            for admission in admissions:
                stage_session = await stack.enter_async_context(self.session_factory())
                item = await stage_session.get(GenerationWorkItemModel, admission.work_item_id)
                if item is None:
                    continue
                if item.status == "ready":
                    preserved += 1
                    continue
                if not _eligible(item, now):
                    continue
                selected.append((admission, stage_session, item))

            if not selected:
                return 0, preserved
            # Source is attached by _dispatch_writer_jobs; each job owns a
            # distinct session and the runtime enforces the cap of four.
            jobs = [
                SectionWriterJob(
                    session=stage_session,
                    work_item_id=item.id,
                    worker_id=self.worker_id,
                    source=source,
                    request=admission.request,
                    status="queued",
                    provider=self.writer_provider,
                    lease_seconds=self.writer_lease_seconds,
                )
                for admission, stage_session, item in selected
            ]
            outcomes = await write_section_work_items(jobs)
            writer_dispatched = sum(1 for outcome in outcomes if outcome.result is not None)
            preserved += sum(1 for outcome in outcomes if outcome.preserved_ready)
            return writer_dispatched, preserved


__all__ = [
    "SectionDispatchOutcome",
    "SectionDispatcherError",
    "SharedSectionDispatcher",
]

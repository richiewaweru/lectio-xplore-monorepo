"""Shared-runtime worker for Preparation Runs (Option D, 3A).

A ``preparation`` Run turns an approved lesson structure into a lesson backbone,
per-card practice items and a draft V2 Teaching Plan:

* ``backbone`` - the structured anchor (scenario, exact data, answer, figure
  specs, variants) the questions are written against; runs first.  The worker
  admits the ``items:*`` items once it is ready.  Runs admitted before the
  backbone stage existed have no ``backbone`` item and skip straight to items.
* ``items:{concept_card_id}`` - one work item per concept card (independently
  retryable); the worker generates that card's items and writes ``pack_items``
  with the same rules the old whole-pack loop had.
* ``teaching_plan`` - admitted by this worker once every ``items:*`` item is
  ready; runs the planner + semantic reviewer unchanged, which writes the draft
  revision (``teaching_review.status = pending``) into ``page_document_v2``.
  The Run is then finalized against a verified ``teaching_plan_revision``
  artifact.

Teacher approval is not a job: a ready Run with a pending review *is* the
"awaiting approval" state.

Leases: a claimed item holds a ``lease_seconds`` (default 300 s) lease that a
background heartbeat extends every third of the lease while the provider call
runs, so a long planner call is never reclaimed from a live worker; a dead
worker's lease expires and any worker reclaims the item (bounded attempts).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from core.database.models import GenerationModel
from application.unit_lesson.preparation_backbone import generate_lesson_backbone
from application.unit_lesson.preparation_items import generate_card_items
from application.unit_lesson.preparation_runs import (
    BACKBONE_ITEM_KEY,
    ITEMS_KEY_PREFIX,
    LEGACY_DEFINITION_VERSION,
    PLAN_ARTIFACT_TYPE,
    TEACHING_ITEM_KEY,
    TEACHING_ITEM_STAGE,
    TEACHING_SECTION_KEY_PREFIX,
    TEACHING_SPINE_KEY,
    DEFINITION_VERSION,
    PreparationRunError,
    add_card_items,
    load_current_source,
    run_source,
)
from curriculum.planning.persistence import load_chunked_state, persist_chunked_state
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.generation_runtime import (
    ErrorClass,
    RecoveryAction,
    RunFinalization,
    SourceIdentity,
    VerifiedArtifact,
    WorkItemAdmission,
    WorkItemConflict,
    WorkItemFailure,
    active_work_items,
    add_work_item,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    finalize_run,
    heartbeat_work_item,
)
from infra.generation_runtime.repository import (
    ArtifactVerificationError,
    InvalidRunTransition,
    SourceIdentityConflict,
    SourceVerificationError,
    WorkItemNotFound,
    WorkItemUnavailable,
)

LOGGER = logging.getLogger(__name__)

_DEFAULT_SCAN_LIMIT = 20
_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (
    sqlalchemy_exc.OperationalError,
    sqlalchemy_exc.InterfaceError,
)


class _SourceChanged(RuntimeError):
    """The structural plan/cards changed after the Run was admitted."""


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is not None:
        return current.astimezone(UTC).replace(tzinfo=None)
    return current


def classify_failure(exc: BaseException) -> WorkItemFailure:
    """Closed, safe failure classification for one preparation attempt.

    Provider transport / timeout / rate-limit / model-output-invalid -> RETRY;
    validation and contract failures -> terminal REGENERATE; anything else is
    an internal programming error (never leaks provider text).
    """
    from print.generation.whole_lesson.failure_policy import classify_failure as classify

    if isinstance(
        exc, (_SourceChanged, PreparationRunError, SourceIdentityConflict, SourceVerificationError)
    ):
        return WorkItemFailure(
            error_code="preparation_source_changed",
            error_class=ErrorClass.SOURCE_CONFLICT,
            safe_summary="The lesson structure changed while its plan was being created.",
            recovery_action=RecoveryAction.REGENERATE,
        )
    if isinstance(exc, _TRANSIENT_ERRORS):
        return WorkItemFailure(
            error_code="preparation_transient_error",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="A temporary storage error interrupted the plan. Retry it.",
            recovery_action=RecoveryAction.RETRY,
        )
    from curriculum.backbone.errors import BackboneOutputInvalidError
    from curriculum.teaching_plan.semantic_review import TeachingPlanSemanticReviewError

    if isinstance(exc, BackboneOutputInvalidError):
        return WorkItemFailure(
            error_code="backbone_invalid",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary=(
                "The lesson's example scenario could not be written in a valid form. "
                "Retry it."
            ),
            recovery_action=RecoveryAction.RETRY,
        )

    if isinstance(exc, TeachingPlanSemanticReviewError):
        # The reviewer's own output was unusable (bad provider output), not a
        # verdict on the plan: retry rather than dead-ending the plan.
        return WorkItemFailure(
            error_code="preparation_reviewer_output_invalid",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="The AI plan reviewer returned unusable output. Retry it.",
            recovery_action=RecoveryAction.RETRY,
        )
    verdict = classify(exc)
    code = verdict.code
    if code in {"TRANSPORT", "TIMEOUT", "RATE_LIMIT"}:
        return WorkItemFailure(
            error_code=f"preparation_provider_{code.lower()}",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="The AI provider was unavailable or too slow. Retry it.",
            recovery_action=RecoveryAction.RETRY,
        )
    if code == "MODEL_OUTPUT_INVALID" or (code == "VALIDATION" and verdict.retryable):
        return WorkItemFailure(
            error_code="preparation_model_output_invalid",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="The AI returned output that failed validation. Retry it.",
            recovery_action=RecoveryAction.RETRY,
        )
    if code in {"VALIDATION", "CONTRACT"}:
        return WorkItemFailure(
            error_code="preparation_contract_violation",
            error_class=ErrorClass.VALIDATION,
            safe_summary=(
                "The lesson plan could not be validated: "
                f"{str(exc).strip()[:300] or type(exc).__name__}"
            ),
            recovery_action=RecoveryAction.REGENERATE,
        )
    if code == "BUDGET_EXHAUSTED":
        return WorkItemFailure(
            error_code="preparation_budget_exhausted",
            error_class=ErrorClass.BUDGET_EXHAUSTED,
            safe_summary="The AI call budget for this plan was used up. Regenerate it.",
            recovery_action=RecoveryAction.REGENERATE,
        )
    return WorkItemFailure(
        error_code="preparation_internal_error",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="An unexpected error stopped this plan. Regenerate it.",
        recovery_action=RecoveryAction.REGENERATE,
    )


def _default_item_runner() -> Callable[..., Any]:
    from curriculum.items.generator import execute_items_with_diagnostics

    return execute_items_with_diagnostics


def _default_backbone_runner() -> Callable[..., Any]:
    from curriculum.backbone.writer import generate_backbone

    return generate_backbone


def _default_teaching_runner() -> Callable[..., Any]:
    from application.unit_lesson.teaching_plan_service import run_and_persist_teaching_plan

    return run_and_persist_teaching_plan


def _default_staged_runners() -> dict[str, Callable[..., Any]]:
    from application.unit_lesson import teaching_plan_service as service

    return {
        "spine": service.run_teaching_spine_item,
        "section": service.run_teaching_section_item,
        "finish": service.finish_and_persist_staged_teaching_plan,
    }


def _draft_revision(state: dict[str, Any]) -> dict[str, Any]:
    """The pending draft revision record currently named by ``teaching_review``."""
    page = state.get("page_document_v2")
    if not isinstance(page, dict):
        raise ArtifactVerificationError("preparation has no page_document_v2 ledger")
    review = page.get("teaching_review") or {}
    try:
        revision = int(review.get("revision") or 1)
    except (TypeError, ValueError) as exc:
        raise ArtifactVerificationError("teaching review revision is invalid") from exc
    for record in page.get("teaching_revisions") or []:
        if isinstance(record, dict) and int(record.get("revision") or 0) == revision:
            return record
    raise ArtifactVerificationError("the draft Teaching Plan revision is missing")


class PreparationWorker:
    """Poll admit-teaching + execute for preparation Runs."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        worker_id: str | None = None,
        lease_seconds: int = 300,
        poll_interval_seconds: float = 0.5,
        scan_limit: int = _DEFAULT_SCAN_LIMIT,
        item_runner: Callable[..., Any] | None = None,
        teaching_runner: Callable[..., Any] | None = None,
        backbone_runner: Callable[..., Any] | None = None,
        staged_runners: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if scan_limit <= 0:
            raise ValueError("scan_limit must be positive")
        self.session_factory = session_factory
        self.worker_id = worker_id or f"preparation-{uuid.uuid4()}"
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = max(lease_seconds / 3.0, 0.05)
        self.poll_interval_seconds = poll_interval_seconds
        self.scan_limit = scan_limit
        self._item_runner = item_runner
        self._teaching_runner = teaching_runner
        self._backbone_runner = backbone_runner
        # Staged teaching planner stages: "spine", "section", "finish".
        self._staged_runners = staged_runners
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    # -------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name=self.worker_id)

    async def stop(self, *, drain_seconds: float = 5.0) -> None:
        self._stop.set()
        task = self._task
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=max(drain_seconds, 0.1))
        except TimeoutError:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            progressed = False
            try:
                async with self.session_factory() as session:
                    progressed = await self.run_one(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Preparation worker iteration failed")
            if progressed:
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)

    async def run_one(self, session: Any, *, now: datetime | None = None) -> bool:
        """One tick: admit any due ``items:*`` / ``teaching_plan`` items, then execute one."""
        current = _now(now)
        progressed = await self._admit_items_items(session)
        progressed = await self._admit_teaching_items(session) or progressed
        progressed = await self._execute_one(session, current) or progressed
        return progressed

    # -------------------------------------------------------------- items admit

    async def _admit_items_items(self, session: Any) -> bool:
        """Admit ``items:*`` for runs whose backbone is ready and have none yet."""
        backbone_ready = (
            select(GenerationWorkItemModel.id)
            .where(
                GenerationWorkItemModel.run_id == GenerationRunModel.id,
                GenerationWorkItemModel.item_key == BACKBONE_ITEM_KEY,
                GenerationWorkItemModel.status == "ready",
            )
            .exists()
        )
        has_items = (
            select(GenerationWorkItemModel.id)
            .where(
                GenerationWorkItemModel.run_id == GenerationRunModel.id,
                GenerationWorkItemModel.item_key.like(f"{ITEMS_KEY_PREFIX}%"),
            )
            .exists()
        )
        run_ids = list(
            (
                await session.scalars(
                    select(GenerationRunModel.id)
                    .where(
                        GenerationRunModel.run_type == "preparation",
                        GenerationRunModel.status == "running",
                        backbone_ready,
                        ~has_items,
                    )
                    .order_by(GenerationRunModel.created_at.asc())
                    .limit(self.scan_limit)
                )
            ).all()
        )
        progressed = False
        for run_id in run_ids:
            progressed = await self._admit_items_for(session, str(run_id)) or progressed
        return progressed

    async def _admit_items_for(self, session: Any, run_id: str) -> bool:
        """Once the backbone is ready, admit one ``items:{card_id}`` per concept card."""
        run = await session.scalar(
            select(GenerationRunModel)
            .options(selectinload(GenerationRunModel.work_items))
            .where(GenerationRunModel.id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is None or run.status not in {"queued", "running"}:
            return False
        active = active_work_items(tuple(run.work_items))
        backbone = next((i for i in active if i.item_key == BACKBONE_ITEM_KEY), None)
        if (
            backbone is None
            or backbone.status != "ready"
            or any(i.item_key.startswith(ITEMS_KEY_PREFIX) for i in active)
        ):
            return False
        digest = (backbone.output_json or {}).get("hash")
        if not digest:
            return False
        try:
            generation = await session.get(
                GenerationModel, run.source_artifact_id, populate_existing=True
            )
            if generation is None:
                return False
            await add_card_items(
                session,
                run=run,
                generation=generation,
                source=run_source(run),
                backbone_hash=str(digest),
            )
            await session.commit()
        except (WorkItemConflict, InvalidRunTransition, PreparationRunError):
            await session.rollback()
            return False
        return True

    # ---------------------------------------------------------- teaching admit

    async def _admit_teaching_items(self, session: Any) -> bool:
        has_teaching = (
            select(GenerationWorkItemModel.id)
            .where(
                GenerationWorkItemModel.run_id == GenerationRunModel.id,
                GenerationWorkItemModel.item_key == TEACHING_ITEM_KEY,
            )
            .exists()
        )
        run_ids = list(
            (
                await session.scalars(
                    select(GenerationRunModel.id)
                    .where(
                        GenerationRunModel.run_type == "preparation",
                        GenerationRunModel.status == "running",
                        ~has_teaching,
                    )
                    .order_by(GenerationRunModel.created_at.asc())
                    .limit(self.scan_limit)
                )
            ).all()
        )
        progressed = False
        for run_id in run_ids:
            progressed = await self._admit_teaching_for(session, str(run_id)) or progressed
        return progressed

    async def _admit_teaching_for(self, session: Any, run_id: str) -> bool:
        run = await session.scalar(
            select(GenerationRunModel)
            .options(selectinload(GenerationRunModel.work_items))
            .where(GenerationRunModel.id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is None or run.status not in {"queued", "running"}:
            return False
        active = active_work_items(tuple(run.work_items))
        card_items = [i for i in active if i.item_key.startswith(ITEMS_KEY_PREFIX)]
        if (
            not card_items
            or any(i.item_key == TEACHING_ITEM_KEY for i in active)
            or any(i.status != "ready" for i in card_items)
        ):
            return False
        identity: dict[str, Any] = {
            "source_hash": run.source_hash,
            "items": sorted((i.item_key, i.output_hash) for i in card_items),
        }
        backbone = next((i for i in active if i.item_key == BACKBONE_ITEM_KEY), None)
        if backbone is not None:
            if backbone.status != "ready":
                return False
            identity["backbone_hash"] = (backbone.output_json or {}).get("hash")
        # Runs admitted before the backbone stage have no backbone item: keep the
        # exact identity and definition they were admitted under.
        version = DEFINITION_VERSION if backbone is not None else LEGACY_DEFINITION_VERSION
        spine = next((i for i in active if i.item_key == TEACHING_SPINE_KEY), None)
        # Staged is the only planner. A Run created before the single planner was
        # removed may already hold a bare ``teaching_plan`` item (no spine): the
        # early return above leaves it alone and ``_run_teaching`` plans it in one
        # in-process staged pass instead.
        return await self._admit_staged_teaching(
            session,
            run=run,
            active=active,
            spine=spine,
            identity=identity,
            version=version,
        )

    async def _admit_staged_teaching(
        self,
        session: Any,
        *,
        run: Any,
        active: Any,
        spine: Any,
        identity: dict[str, Any],
        version: str,
    ) -> bool:
        """Staged planner: teaching_spine -> teaching_section:{slot} -> teaching_plan."""

        async def admit(key: str, input_identity: dict[str, Any], definition: dict[str, Any]) -> bool:
            admission = await add_work_item(
                session,
                WorkItemAdmission(
                    run_id=run.id,
                    item_key=key,
                    stage=TEACHING_ITEM_STAGE,
                    input_hash=content_hash(input_identity),
                    definition_hash=content_hash(definition),
                ),
            )
            return bool(admission.created)

        try:
            if spine is None:
                created = await admit(
                    TEACHING_SPINE_KEY,
                    {**identity, "mode": "staged"},
                    {"definition": "preparation-teaching-spine", "version": version},
                )
                await session.commit()
                return created
            if spine.status != "ready":
                return False
            spine_hash = spine.output_hash
            slot_ids = [
                str(section.get("slot_id"))
                for section in ((spine.output_json or {}).get("spine") or {}).get("sections") or []
                if isinstance(section, dict) and section.get("slot_id")
            ]
            if not slot_ids:
                return False
            created = False
            for slot_id in slot_ids:
                created = (
                    await admit(
                        f"{TEACHING_SECTION_KEY_PREFIX}{slot_id}",
                        {"spine_hash": spine_hash, "slot_id": slot_id},
                        {"definition": "preparation-teaching-section", "version": version},
                    )
                    or created
                )
            section_items = {
                i.item_key: i for i in active if i.item_key.startswith(TEACHING_SECTION_KEY_PREFIX)
            }
            wanted = [f"{TEACHING_SECTION_KEY_PREFIX}{slot_id}" for slot_id in slot_ids]
            if created or not all(
                key in section_items and section_items[key].status == "ready" for key in wanted
            ):
                await session.commit()
                return created
            created = await admit(
                TEACHING_ITEM_KEY,
                {
                    **identity,
                    "mode": "staged",
                    "spine_hash": spine_hash,
                    "sections": sorted((k, section_items[k].output_hash) for k in wanted),
                },
                {"definition": "preparation-teaching-plan", "version": version, "mode": "staged"},
            )
            await session.commit()
            return created
        except (WorkItemConflict, InvalidRunTransition):
            await session.rollback()
            return False

    # ----------------------------------------------------------------- execute

    async def _execute_one(self, session: Any, now: datetime) -> bool:
        candidates = list(
            (
                await session.execute(
                    select(GenerationWorkItemModel.id, GenerationRunModel.id)
                    .join(GenerationRunModel, GenerationRunModel.id == GenerationWorkItemModel.run_id)
                    .where(
                        GenerationRunModel.run_type == "preparation",
                        GenerationRunModel.status.in_(("queued", "running")),
                        or_(
                            GenerationWorkItemModel.item_key == BACKBONE_ITEM_KEY,
                            GenerationWorkItemModel.item_key.like(f"{ITEMS_KEY_PREFIX}%"),
                            GenerationWorkItemModel.item_key == TEACHING_ITEM_KEY,
                            GenerationWorkItemModel.item_key == TEACHING_SPINE_KEY,
                            GenerationWorkItemModel.item_key.like(
                                f"{TEACHING_SECTION_KEY_PREFIX}%"
                            ),
                        ),
                        or_(
                            GenerationWorkItemModel.status == "queued",
                            (
                                (GenerationWorkItemModel.status == "running")
                                & (GenerationWorkItemModel.lease_expires_at <= now)
                            ),
                        ),
                    )
                    .order_by(GenerationWorkItemModel.created_at.asc())
                    .limit(self.scan_limit)
                )
            ).all()
        )
        for item_id, run_id in candidates:
            run = await session.get(GenerationRunModel, run_id, populate_existing=True)
            if run is None:
                continue
            try:
                item = await claim_work_item(
                    session,
                    work_item_id=str(item_id),
                    worker_id=self.worker_id,
                    source=run_source(run),
                    lease_seconds=self.lease_seconds,
                    now=now,
                )
                await session.commit()
            except (WorkItemUnavailable, WorkItemNotFound):
                await session.rollback()
                continue
            except sqlalchemy_exc.OperationalError:
                await session.rollback()
                continue
            if item.status != "running":
                # An expired, attempt-exhausted item was reconciled by the claim.
                return True
            await self._execute_claimed(
                session,
                item_id=str(item.id),
                item_key=str(item.item_key),
                lease_token=int(item.lease_token or 0),
                run_id=str(run_id),
                now=now,
            )
            return True
        return False

    async def _execute_claimed(
        self,
        session: Any,
        *,
        item_id: str,
        item_key: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        try:
            await self._assert_source_unchanged(session, run_id)
            if item_key == TEACHING_ITEM_KEY:
                await self._run_teaching(
                    session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now
                )
            elif item_key == TEACHING_SPINE_KEY:
                await self._run_teaching_spine(
                    session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now
                )
            elif item_key.startswith(TEACHING_SECTION_KEY_PREFIX):
                await self._run_teaching_section(
                    session,
                    item_id=item_id,
                    slot_id=item_key[len(TEACHING_SECTION_KEY_PREFIX):],
                    lease_token=lease_token,
                    run_id=run_id,
                    now=now,
                )
            elif item_key == BACKBONE_ITEM_KEY:
                await self._run_backbone(
                    session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now
                )
            else:
                await self._run_items(
                    session,
                    item_id=item_id,
                    card_id=item_key[len(ITEMS_KEY_PREFIX):],
                    lease_token=lease_token,
                    run_id=run_id,
                    now=now,
                )
        except LeaseLostError:
            await session.rollback()
            LOGGER.info("Preparation lease lost work_item_id=%s", item_id)
        except asyncio.CancelledError:
            await session.rollback()
            raise
        except Exception as exc:
            await session.rollback()
            LOGGER.warning(
                "Preparation work item failed work_item_id=%s error=%s: %s",
                item_id,
                type(exc).__name__,
                str(exc)[:500],
                exc_info=not isinstance(exc, _TRANSIENT_ERRORS),
            )
            await self._record_failure(
                session, item_id=item_id, lease_token=lease_token, exc=exc, now=now
            )

    async def _assert_source_unchanged(self, session: Any, run_id: str) -> None:
        """Under the lease: the structure/cards must still be what the Run admitted."""
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        current = await load_current_source(session, generation_id=run.source_artifact_id)
        if current != run_source(run):
            raise _SourceChanged("the lesson structure changed after approval")
        await session.rollback()  # end the read transaction before the long provider call

    async def _record_failure(
        self, session: Any, *, item_id: str, lease_token: int, exc: BaseException, now: datetime
    ) -> None:
        try:
            await fail_work_item(
                session,
                work_item_id=item_id,
                worker_id=self.worker_id,
                lease_token=lease_token,
                failure=classify_failure(exc),
                now=now,
            )
            await session.commit()
        except LeaseLostError:
            await session.rollback()
        except Exception:
            LOGGER.exception("Could not persist preparation failure work_item_id=%s", item_id)
            await session.rollback()

    # ------------------------------------------------------- lease heartbeats

    async def _heartbeated(self, *, item_id: str, lease_token: int, coro: Any) -> Any:
        """Run ``coro`` while extending the work-item lease; abort if it is lost."""
        work = asyncio.ensure_future(coro)

        async def beat() -> None:
            while True:
                await asyncio.sleep(self.heartbeat_seconds)
                try:
                    async with self.session_factory() as beat_session:
                        await heartbeat_work_item(
                            beat_session,
                            work_item_id=item_id,
                            worker_id=self.worker_id,
                            lease_token=lease_token,
                            lease_seconds=self.lease_seconds,
                        )
                        await beat_session.commit()
                except LeaseLostError:
                    raise
                except Exception:  # noqa: BLE001 - a missed beat must not kill live work
                    LOGGER.warning("Preparation heartbeat failed work_item_id=%s", item_id)

        beat_task = asyncio.ensure_future(beat())
        try:
            done, _pending = await asyncio.wait(
                {work, beat_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if work in done:
                return work.result()
            work.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await work
            raise LeaseLostError("preparation work-item lease was lost during execution")
        finally:
            for task in (beat_task, work):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await task

    @asynccontextmanager
    async def _prompt_scope(
        self, owner_user_id: str, *, generation_id: str | None = None
    ) -> AsyncIterator[None]:
        from core.prompts import bind_prompt_cache, reset_prompt_cache, resolve_all_prompts

        async with self.session_factory() as prompt_session:
            texts, hashes = await resolve_all_prompts(owner_user_id, prompt_session)
        token = bind_prompt_cache(texts)
        try:
            if generation_id is not None:
                try:
                    from print.http.v3_studio.generation_writer import V3GenerationWriter

                    await V3GenerationWriter(self.session_factory).record_prompt_hashes(
                        generation_id, hashes
                    )
                except Exception:  # noqa: BLE001 - observability only
                    LOGGER.exception("Failed to stamp prompt hashes generation_id=%s", generation_id)
            yield
        finally:
            reset_prompt_cache(token)

    # ---------------------------------------------------------------- backbone

    async def _run_backbone(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        owner_id = str(run.owner_user_id)
        generation_id = str(run.source_artifact_id)
        runner = self._backbone_runner or _default_backbone_runner()

        async def fence() -> None:
            async with self.session_factory() as fence_session:
                await heartbeat_work_item(
                    fence_session,
                    work_item_id=item_id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    lease_seconds=self.lease_seconds,
                )
                await fence_session.commit()

        async with self._prompt_scope(owner_id):
            summary = await self._heartbeated(
                item_id=item_id,
                lease_token=lease_token,
                coro=generate_lesson_backbone(
                    session_factory=self.session_factory,
                    generation_id=generation_id,
                    backbone_runner=runner,
                    fence=fence,
                ),
            )
        await complete_work_item(
            session,
            work_item_id=item_id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            output_json=summary,
            output_hash=content_hash(summary),
            now=now,
        )
        await session.commit()
        await self._admit_items_for(session, run_id)

    # ------------------------------------------------------------------- items

    async def _run_items(
        self,
        session: Any,
        *,
        item_id: str,
        card_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        owner_id = str(run.owner_user_id)
        generation_id = str(run.source_artifact_id)
        runner = self._item_runner or _default_item_runner()

        async def fence() -> None:
            async with self.session_factory() as fence_session:
                await heartbeat_work_item(
                    fence_session,
                    work_item_id=item_id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    lease_seconds=self.lease_seconds,
                )
                await fence_session.commit()

        async with self._prompt_scope(owner_id):
            summary = await self._heartbeated(
                item_id=item_id,
                lease_token=lease_token,
                coro=generate_card_items(
                    session_factory=self.session_factory,
                    generation_id=generation_id,
                    card_id=card_id,
                    item_runner=runner,
                    fence=fence,
                ),
            )
        await complete_work_item(
            session,
            work_item_id=item_id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            output_json=summary,
            output_hash=content_hash(summary),
            now=now,
        )
        await session.commit()
        await self._admit_teaching_for(session, run_id)

    # ----------------------------------------------------------- staged teaching

    def _staged(self, name: str) -> Callable[..., Any]:
        return (self._staged_runners or {}).get(name) or _default_staged_runners()[name]

    async def _staged_outputs(
        self, session: Any, run_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
        """The ready spine output and ready section outputs (by slot) of a Run."""
        run = await session.scalar(
            select(GenerationRunModel)
            .options(selectinload(GenerationRunModel.work_items))
            .where(GenerationRunModel.id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        active = active_work_items(tuple(run.work_items))
        spine = next(
            (i for i in active if i.item_key == TEACHING_SPINE_KEY and i.status == "ready"), None
        )
        sections = {
            i.item_key[len(TEACHING_SECTION_KEY_PREFIX):]: dict(i.output_json or {})
            for i in active
            if i.item_key.startswith(TEACHING_SECTION_KEY_PREFIX) and i.status == "ready"
        }
        spine_output = dict(spine.output_json or {}) if spine is not None else None
        await session.rollback()  # end the read transaction before the long provider call
        return spine_output, sections

    async def _run_staged_item(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
        call: Callable[[Any, str], Any],
    ) -> None:
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        owner_id = str(run.owner_user_id)
        generation_id = str(run.source_artifact_id)

        async def work() -> dict[str, Any]:
            async with self.session_factory() as work_session:
                output = await call(work_session, generation_id)
                await work_session.commit()
                return output

        async with self._prompt_scope(owner_id, generation_id=generation_id):
            output = await self._heartbeated(item_id=item_id, lease_token=lease_token, coro=work())
        await complete_work_item(
            session,
            work_item_id=item_id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            output_json=output,
            output_hash=content_hash(output),
            now=now,
        )
        await session.commit()
        await self._admit_teaching_for(session, run_id)

    async def _run_teaching_spine(
        self, session: Any, *, item_id: str, lease_token: int, run_id: str, now: datetime
    ) -> None:
        runner = self._staged("spine")

        async def call(work_session: Any, generation_id: str) -> dict[str, Any]:
            return await runner(work_session, generation_id, require_items=True)

        await self._run_staged_item(
            session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now, call=call
        )

    async def _run_teaching_section(
        self,
        session: Any,
        *,
        item_id: str,
        slot_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        runner = self._staged("section")
        spine_json, _sections = await self._staged_outputs(session, run_id)
        if spine_json is None:
            raise _SourceChanged("the teaching spine is unavailable")

        async def call(work_session: Any, generation_id: str) -> dict[str, Any]:
            return await runner(
                work_session, generation_id, spine_json=spine_json, slot_id=slot_id
            )

        await self._run_staged_item(
            session, item_id=item_id, lease_token=lease_token, run_id=run_id, now=now, call=call
        )

    # ---------------------------------------------------------------- teaching

    async def _run_teaching(
        self,
        session: Any,
        *,
        item_id: str,
        lease_token: int,
        run_id: str,
        now: datetime,
    ) -> None:
        run = await session.get(GenerationRunModel, run_id, populate_existing=True)
        if run is None:
            raise _SourceChanged("the preparation Run is unavailable")
        owner_id = str(run.owner_user_id)
        generation_id = str(run.source_artifact_id)
        source = run_source(run)
        # No spine on this Run: it was created while the single-call planner existed
        # and holds a bare ``teaching_plan`` item. The default runner plans it in one
        # in-process staged pass (spine, parallel sections, finish), so the Run
        # completes; a failure is recorded like any other and ``regenerate`` restarts.
        runner = self._teaching_runner or _default_teaching_runner()
        spine_json, section_jsons = await self._staged_outputs(session, run_id)
        if spine_json is not None:
            # Staged Run: assemble, review and gate from the stored stage outputs.
            finish = self._staged("finish")

            async def runner(  # noqa: F811 - staged replacement for the single runner
                plan_session: Any, generation_id: str, *, require_items: bool = True
            ) -> dict[str, Any]:
                return await finish(
                    plan_session,
                    generation_id,
                    spine_json=spine_json,
                    section_jsons=section_jsons,
                )

        async def plan() -> None:
            async with self.session_factory() as plan_session:
                summary = await runner(plan_session, generation_id, require_items=True)
                teaching = (summary or {}).get("teaching_plan") or {}
                state = await load_chunked_state(generation_id, plan_session)
                await persist_chunked_state(
                    generation_id,
                    {
                        # Compatibility stamps only; the Run is the status.
                        "stage": "awaiting_teaching_approval",
                        "native_whole_lesson": True,
                        "shared_preparation": True
                        if state.get("shared_preparation") or state.get("path_prepared")
                        else state.get("shared_preparation"),
                        "teaching_plan_summary": {
                            "arc": teaching.get("arc"),
                            "section_count": len(teaching.get("sections") or []),
                        },
                    },
                    plan_session,
                )
                await plan_session.commit()

        async with self._prompt_scope(owner_id, generation_id=generation_id):
            await self._heartbeated(item_id=item_id, lease_token=lease_token, coro=plan())

        state = await load_chunked_state(generation_id, session)
        record = _draft_revision(state)
        plan_id = str(record["teaching_plan_id"])
        revision = int(record["revision"])
        item_output = {
            "teaching_plan_id": plan_id,
            "revision": revision,
            "content_hash": content_hash(record["plan"]),
        }
        await complete_work_item(
            session,
            work_item_id=item_id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            output_json=item_output,
            output_hash=content_hash(item_output),
            now=now,
        )

        async def source_verifier(verify_session: Any, requested: SourceIdentity) -> SourceIdentity:
            return await load_current_source(verify_session, generation_id=generation_id)

        async def artifact_loader(
            load_session: Any, artifact_type: str, artifact_id: str, artifact_revision: int
        ) -> VerifiedArtifact:
            if artifact_type != PLAN_ARTIFACT_TYPE:
                raise ArtifactVerificationError("unexpected preparation artifact type")
            loaded_state = await load_chunked_state(generation_id, load_session)
            page = loaded_state.get("page_document_v2")
            records = page.get("teaching_revisions") if isinstance(page, dict) else None
            match = next(
                (
                    r
                    for r in records or []
                    if isinstance(r, dict)
                    and r.get("teaching_plan_id") == artifact_id
                    and int(r.get("revision") or 0) == artifact_revision
                ),
                None,
            )
            if match is None or not isinstance(match.get("plan"), dict):
                raise ArtifactVerificationError("the draft Teaching Plan revision is unavailable")
            return VerifiedArtifact(
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                revision=artifact_revision,
                output_json=match["plan"],
                output_hash=content_hash(match["plan"]),
            )

        await finalize_run(
            session,
            run_id=run_id,
            owner_user_id=owner_id,
            finalization=RunFinalization(
                source=source,
                output_artifact_type=PLAN_ARTIFACT_TYPE,
                output_artifact_id=plan_id,
                output_revision=revision,
            ),
            source_verifier=source_verifier,
            artifact_loader=artifact_loader,
            now=now,
        )
        await session.commit()


__all__ = ["PreparationWorker", "classify_failure"]

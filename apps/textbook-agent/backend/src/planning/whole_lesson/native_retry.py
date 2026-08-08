"""Stage-aware native retry: accept-only HTTP + leased pre-worker execution."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from planning.whole_lesson.events import make_event
from planning.whole_lesson.repository import (
    PageDocumentRepository,
    _now,
    clear_generation_error_state,
    empty_execution_meta,
)
from planning.whole_lesson.states import (
    PRE_WORKER_RETRY_STATUSES,
    PRE_WORKER_WORK_KINDS,
    WORK_KIND_POST_APPROVAL,
    WORK_KIND_PRE_WORKER_ITEM,
    WORK_KIND_PRE_WORKER_TEACHING,
    ExecutionLease,
    LeaseLostError,
    assert_legal_transition,
)


class NativeRetryTarget(str, Enum):
    ITEM_GENERATION = "item_generation"
    TEACHING_PLAN = "planning_teaching"
    POST_APPROVAL_WORKER = "post_approval_worker"
    VISUALS = "visuals"
    NOT_RETRYABLE = "not_retryable"


_POST_APPROVAL_ERROR_STAGES = frozenset(
    {
        "planning_forms",
        "writing_sections",
        "writing_blocks",
        "assembling",
        "queued",
    }
)

_VISUAL_ERROR_STAGES = frozenset({"awaiting_visuals", "visual_generation"})


class NativeRetryConflict(RuntimeError):
    """Non-destructive rejection of a retry request (HTTP 409)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "NATIVE_RETRY_CONFLICT",
        status: str | None = None,
        target: NativeRetryTarget | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.target = target
        self.detail = detail or {}


def decide_native_retry_target(
    status: str,
    last_error: Mapping[str, Any] | None,
    *,
    has_failed_visuals: bool = False,
) -> NativeRetryTarget:
    """Persisted last_error.stage owns the checkpoint decision."""
    stage_status = str(status or "").strip()
    err_stage = ""
    if isinstance(last_error, Mapping):
        err_stage = str(last_error.get("stage") or "").strip()

    if stage_status == "awaiting_visuals":
        if has_failed_visuals or err_stage in _VISUAL_ERROR_STAGES:
            return NativeRetryTarget.VISUALS
        return NativeRetryTarget.NOT_RETRYABLE

    if stage_status == "failed_terminal":
        return NativeRetryTarget.NOT_RETRYABLE

    if stage_status != "failed_recoverable":
        return NativeRetryTarget.NOT_RETRYABLE

    if err_stage == "item_generation":
        return NativeRetryTarget.ITEM_GENERATION
    if err_stage == "planning_teaching":
        return NativeRetryTarget.TEACHING_PLAN
    if err_stage in _VISUAL_ERROR_STAGES:
        return NativeRetryTarget.VISUALS
    if err_stage in _POST_APPROVAL_ERROR_STAGES or not err_stage:
        return NativeRetryTarget.POST_APPROVAL_WORKER
    return NativeRetryTarget.NOT_RETRYABLE


def next_action_for_retry_target(target: NativeRetryTarget) -> str:
    if target == NativeRetryTarget.ITEM_GENERATION:
        return "retry_items"
    if target == NativeRetryTarget.TEACHING_PLAN:
        return "retry_teaching"
    if target == NativeRetryTarget.POST_APPROVAL_WORKER:
        return "retry_native"
    if target == NativeRetryTarget.VISUALS:
        return "retry_visuals"
    return "inspect_error"


def _work_kind_for_target(target: NativeRetryTarget) -> str:
    if target == NativeRetryTarget.ITEM_GENERATION:
        return WORK_KIND_PRE_WORKER_ITEM
    if target == NativeRetryTarget.TEACHING_PLAN:
        return WORK_KIND_PRE_WORKER_TEACHING
    return WORK_KIND_POST_APPROVAL


async def accept_native_retry(
    generation_id: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Accept-only: persist durable checkpoint and return. Do not await LLM work."""
    _ = user_id
    async with async_session_factory() as session:
        target, claim = await _accept_native_retry_locked(session, generation_id)

    if target == NativeRetryTarget.POST_APPROVAL_WORKER:
        return {
            "generation_id": generation_id,
            "status": "queued",
            "retry_target": target.value,
            "next_action": "wait",
            "accepted": True,
        }

    return {
        "generation_id": generation_id,
        "status": claim["status"],
        "retry_target": target.value,
        "next_action": "wait",
        "accepted": True,
        "work_kind": claim.get("work_kind"),
    }


async def _accept_native_retry_locked(
    session: AsyncSession,
    generation_id: str,
) -> tuple[NativeRetryTarget, dict[str, Any]]:
    repo = PageDocumentRepository(session, generation_id)
    box: list[tuple[NativeRetryTarget, dict[str, Any]]] = []

    def _mut(generation: GenerationModel, state: dict[str, Any]) -> None:
        current = str(generation.status or "")
        execution = dict(state.get("execution") or empty_execution_meta())
        last_error = execution.get("last_error")
        last_map = last_error if isinstance(last_error, dict) else None
        work_kind = execution.get("work_kind")
        stamp = _now()

        if (
            current in PRE_WORKER_RETRY_STATUSES
            and (
                work_kind in PRE_WORKER_WORK_KINDS
                or bool(execution.get("pre_worker_retry_active"))
            )
        ):
            raise NativeRetryConflict(
                "a pre-worker native retry is already active",
                code="RETRY_IN_PROGRESS",
                status=current,
                target=NativeRetryTarget.ITEM_GENERATION
                if current == "item_generation"
                else NativeRetryTarget.TEACHING_PLAN,
            )

        target = decide_native_retry_target(current, last_map)
        if target == NativeRetryTarget.VISUALS:
            raise NativeRetryConflict(
                "visual failures must use POST .../visuals/retry",
                code="USE_VISUALS_RETRY",
                status=current,
                target=target,
            )
        if current != "failed_recoverable":
            raise NativeRetryConflict(
                f"retry-native requires failed_recoverable, got {current!r}",
                code="INVALID_STATUS",
                status=current,
                target=target,
            )
        if target == NativeRetryTarget.NOT_RETRYABLE:
            raise NativeRetryConflict(
                "generation is not retryable via retry-native",
                code="NOT_RETRYABLE",
                status=current,
                target=target,
            )

        execution["heartbeat_at"] = stamp
        execution["attempt"] = int(execution.get("attempt") or 0) + 1
        execution["worker_id"] = None
        execution["claimed_at"] = None

        if target == NativeRetryTarget.POST_APPROVAL_WORKER:
            assert_legal_transition(current, "queued")
            generation.status = "queued"
            clear_generation_error_state(generation, state)
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = stamp
            execution["attempt"] = int(execution.get("attempt") or 0) + 1
            execution["pre_worker_retry_active"] = False
            execution["work_kind"] = WORK_KIND_POST_APPROVAL
            execution["worker_id"] = None
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "native_retry_accepted",
                        generation_id=generation_id,
                        status="queued",
                    ),
                    "at": stamp,
                    "retry_target": target.value,
                    "work_kind": WORK_KIND_POST_APPROVAL,
                }
            )
            state["events"] = events[-500:]
            box.append(
                (
                    target,
                    {
                        "status": "queued",
                        "retry_target": target.value,
                        "work_kind": WORK_KIND_POST_APPROVAL,
                    },
                )
            )
            return

        checkpoint = (
            "item_generation"
            if target == NativeRetryTarget.ITEM_GENERATION
            else "planning_teaching"
        )
        kind = _work_kind_for_target(target)
        assert_legal_transition(current, checkpoint)
        generation.status = checkpoint
        execution["pre_worker_retry_active"] = True
        execution["work_kind"] = kind
        state["execution"] = execution
        events = list(state.get("events") or [])
        events.append(
            {
                **make_event(
                    "native_retry_accepted",
                    generation_id=generation_id,
                    status=checkpoint,
                ),
                "at": stamp,
                "retry_target": target.value,
                "work_kind": kind,
                "error_stage": str((last_map or {}).get("stage") or ""),
            }
        )
        state["events"] = events[-500:]
        box.append(
            (
                target,
                {
                    "status": checkpoint,
                    "retry_target": target.value,
                    "work_kind": kind,
                },
            )
        )

    await repo.mutate_state(mutation=_mut)
    if not box:
        raise NativeRetryConflict(
            "retry accept produced no result",
            code="RETRY_ACCEPT_EMPTY",
        )
    return box[0]


async def _run_items_under_lease(
    generation_id: str,
    lease: ExecutionLease,
) -> dict[str, Any]:
    from generation.v3_studio.router import (
        _decode_chunked_context,
        _generate_shared_pack_items,
    )
    from v3_blueprint.planning.models import VariantSpec, adapt_legacy_structural_plan
    from v3_blueprint.planning.persistence import (
        load_chunked_state,
        merge_item_generation_summary,
    )

    state = await load_chunked_state(generation_id)
    plan_raw = state.get("structural_plan")
    if not isinstance(plan_raw, dict):
        raise RuntimeError("No structural plan available for item retry")
    plan = adapt_legacy_structural_plan(
        plan_raw,
        source=f"generation:{generation_id}",
    )
    variant_raw = state.get("variant_spec")
    if isinstance(variant_raw, dict):
        plan = plan.with_variant(VariantSpec.model_validate(variant_raw))
    _signals, form, _resource_spec = _decode_chunked_context(state)

    item_summary = await _generate_shared_pack_items(
        generation_id=generation_id,
        form=form,
        plan=plan,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
    )

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)

        def _checkpoint(generation: GenerationModel, state: dict[str, Any]) -> None:
            current_status = str(generation.status or "")
            assert_legal_transition(current_status, "planning_teaching")
            chunked = dict(generation.chunked_state_json or {})
            if not isinstance(chunked, dict):
                chunked = {}
            item_gen = merge_item_generation_summary(
                dict(chunked.get("item_generation") or {}),
                item_summary,
            )
            chunked["item_generation"] = item_gen
            generation.chunked_state_json = chunked
            generation.status = "planning_teaching"
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["work_kind"] = WORK_KIND_PRE_WORKER_TEACHING
            execution["pre_worker_retry_active"] = True
            execution["heartbeat_at"] = _now()
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "native_retry_items_complete",
                        generation_id=generation_id,
                        status="planning_teaching",
                        worker_id=lease.worker_id,
                        lease_token=lease.lease_token,
                    ),
                    "at": _now(),
                    "work_kind": WORK_KIND_PRE_WORKER_TEACHING,
                }
            )
            state["events"] = events[-500:]

        await repo.mutate_state(
            expected_statuses={"item_generation"},
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            mutation=_checkpoint,
        )

    return item_summary


async def _run_teaching_under_lease(
    generation_id: str,
    lease: ExecutionLease,
    *,
    skip_item_generation: bool,
) -> dict[str, Any]:
    from planning.whole_lesson.service import run_and_persist_teaching_plan

    async with async_session_factory() as session:
        teaching = await run_and_persist_teaching_plan(
            session,
            generation_id,
            require_items=True,
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
        )

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)

        def _release(generation: GenerationModel, state: dict[str, Any]) -> None:
            chunked = dict(generation.chunked_state_json or {})
            if not isinstance(chunked, dict):
                chunked = {}
            chunked["stage"] = "awaiting_teaching_approval"
            chunked["native_whole_lesson"] = True
            chunked["skip_item_generation"] = skip_item_generation
            generation.chunked_state_json = chunked
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["work_kind"] = None
            execution["pre_worker_retry_active"] = False
            execution["worker_id"] = None
            execution["claimed_at"] = None
            execution["heartbeat_at"] = _now()
            state["execution"] = execution

        await repo.mutate_state(
            expected_statuses={"awaiting_teaching_approval"},
            worker_id=lease.worker_id,
            lease_token=lease.lease_token,
            mutation=_release,
        )

    return teaching


async def run_pre_worker_retry(
    *,
    lease: ExecutionLease,
) -> dict[str, Any]:
    """Lease-fenced item and/or teaching recovery owned by the native worker."""
    generation_id = lease.generation_id
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        state = await repo.load_page_generation_state()
        execution = dict(state.get("execution") or empty_execution_meta())
        work_kind = execution.get("work_kind")
        await repo.assert_lease(
            worker_id=lease.worker_id, lease_token=lease.lease_token
        )

    if work_kind not in PRE_WORKER_WORK_KINDS:
        raise RuntimeError(
            f"run_pre_worker_retry requires pre-worker work_kind, got {work_kind!r}"
        )

    failure_stage = (
        "item_generation"
        if work_kind == WORK_KIND_PRE_WORKER_ITEM
        else "planning_teaching"
    )
    try:
        item_summary: dict[str, Any] | None = None
        if work_kind == WORK_KIND_PRE_WORKER_ITEM:
            item_summary = await _run_items_under_lease(generation_id, lease)
            # Lease stage may still say item_generation; refresh after checkpoint.
            lease = ExecutionLease(
                generation_id=lease.generation_id,
                worker_id=lease.worker_id,
                lease_token=lease.lease_token,
                stage="planning_teaching",
            )
            teaching = await _run_teaching_under_lease(
                generation_id, lease, skip_item_generation=False
            )
            return {
                "generation_id": generation_id,
                "status": "awaiting_teaching_approval",
                "retry_target": NativeRetryTarget.ITEM_GENERATION.value,
                "item_generation": item_summary,
                "teaching": teaching,
                "next_action": "approve_teaching",
            }

        teaching = await _run_teaching_under_lease(
            generation_id, lease, skip_item_generation=True
        )
        return {
            "generation_id": generation_id,
            "status": "awaiting_teaching_approval",
            "retry_target": NativeRetryTarget.TEACHING_PLAN.value,
            "teaching": teaching,
            "next_action": "approve_teaching",
        }
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001
        from planning.whole_lesson.repository import persist_native_failure_for_generation

        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, generation_id)
            current = str(generation.status or "") if generation else failure_stage
        stage = (
            current
            if current in {"item_generation", "planning_teaching"}
            else failure_stage
        )
        try:
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                await repo.persist_native_failure(
                    exc=exc,
                    stage=stage,
                    event="native_retry_failure",
                    worker_id=lease.worker_id,
                    lease_token=lease.lease_token,
                    expected={stage, "item_generation", "planning_teaching"},
                )
        except LeaseLostError:
            raise
        except Exception:  # noqa: BLE001
            await persist_native_failure_for_generation(
                generation_id,
                exc=exc,
                stage=stage,
                event="native_retry_failure",
            )
        raise


# Backward-compatible alias used by older call sites/tests.
async def execute_native_retry(
    generation_id: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Accept retry then run pre-worker work if this generation can be claimed.

    Prefer accept_native_retry (HTTP) + worker-owned run_pre_worker_retry in production.
    """
    accepted = await accept_native_retry(generation_id, user_id=user_id)
    if accepted.get("status") == "queued":
        return accepted

    worker_id = f"sync-retry-{generation_id[:8]}"
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        lease = await repo.claim_pre_worker_retry(worker_id=worker_id, lease_seconds=90)
    if lease is None:
        return accepted
    return await run_pre_worker_retry(lease=lease)


__all__ = [
    "NativeRetryConflict",
    "NativeRetryTarget",
    "accept_native_retry",
    "decide_native_retry_target",
    "execute_native_retry",
    "next_action_for_retry_target",
    "run_pre_worker_retry",
]

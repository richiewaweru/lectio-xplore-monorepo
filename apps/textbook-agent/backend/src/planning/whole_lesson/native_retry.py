"""Stage-aware native retry: pre-worker item/teaching vs post-approval worker."""

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
from planning.whole_lesson.states import assert_legal_transition


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


async def _claim_native_retry(
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
        target = decide_native_retry_target(current, last_map)
        stamp = _now()

        if current in {"item_generation", "planning_teaching"} and bool(
            execution.get("pre_worker_retry_active")
        ):
            raise NativeRetryConflict(
                "a pre-worker native retry is already active",
                code="RETRY_IN_PROGRESS",
                status=current,
                target=decide_native_retry_target(
                    "failed_recoverable",
                    last_map,
                ),
            )
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
        if bool(execution.get("pre_worker_retry_active")) and target in {
            NativeRetryTarget.ITEM_GENERATION,
            NativeRetryTarget.TEACHING_PLAN,
        }:
            raise NativeRetryConflict(
                "a pre-worker native retry is already active",
                code="RETRY_IN_PROGRESS",
                status=current,
                target=target,
            )

        execution["heartbeat_at"] = stamp
        execution["attempt"] = int(execution.get("attempt") or 0) + 1

        if target == NativeRetryTarget.POST_APPROVAL_WORKER:
            assert_legal_transition(current, "queued")
            generation.status = "queued"
            clear_generation_error_state(generation, state)
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["heartbeat_at"] = stamp
            execution["pre_worker_retry_active"] = False
            state["execution"] = execution
            events = list(state.get("events") or [])
            events.append(
                {
                    **make_event(
                        "native_retry_requeued",
                        generation_id=generation_id,
                        status="queued",
                    ),
                    "at": stamp,
                    "retry_target": target.value,
                }
            )
            state["events"] = events[-500:]
            box.append((target, {"status": "queued", "retry_target": target.value}))
            return

        checkpoint = (
            "item_generation"
            if target == NativeRetryTarget.ITEM_GENERATION
            else "planning_teaching"
        )
        assert_legal_transition(current, checkpoint)
        generation.status = checkpoint
        execution["pre_worker_retry_active"] = True
        state["execution"] = execution
        events = list(state.get("events") or [])
        events.append(
            {
                **make_event(
                    "native_retry_started",
                    generation_id=generation_id,
                    status=checkpoint,
                ),
                "at": stamp,
                "retry_target": target.value,
                "error_stage": str((last_map or {}).get("stage") or ""),
            }
        )
        state["events"] = events[-500:]
        box.append((target, {"status": checkpoint, "retry_target": target.value}))

    await repo.mutate_state(mutation=_mut)
    if not box:
        raise NativeRetryConflict(
            "retry claim produced no result",
            code="RETRY_CLAIM_EMPTY",
        )
    return box[0]


async def _clear_pre_worker_retry_flag(generation_id: str) -> None:
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)

        def _mut(_generation: GenerationModel, state: dict[str, Any]) -> None:
            execution = dict(state.get("execution") or empty_execution_meta())
            execution["pre_worker_retry_active"] = False
            state["execution"] = execution

        try:
            await repo.mutate_state(mutation=_mut)
        except Exception:  # noqa: BLE001
            pass


async def _run_items_then_teaching(generation_id: str, *, user_id: str) -> dict[str, Any]:
    _ = user_id
    from generation.v3_studio.router import (
        _decode_chunked_context,
        _generate_shared_pack_items,
    )
    from planning.whole_lesson.service import run_and_persist_teaching_plan
    from v3_blueprint.planning.models import VariantSpec, adapt_legacy_structural_plan
    from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state

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
    )
    # Preserve append-only attempt journals already flushed during generation.
    current = await load_chunked_state(generation_id)
    item_gen = dict(current.get("item_generation") or {})
    attempts = list(item_gen.get("attempts") or item_summary.get("attempts") or [])
    item_gen.update(item_summary)
    item_gen["attempts"] = attempts
    await persist_chunked_state(
        generation_id,
        {"item_generation": item_gen, "stage": "item_generation"},
    )

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        await repo.transition(
            expected={"item_generation"},
            target="planning_teaching",
            event="native_retry_items_complete",
        )

    async with async_session_factory() as session:
        teaching = await run_and_persist_teaching_plan(
            session, generation_id, require_items=True
        )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "awaiting_teaching_approval",
            "native_whole_lesson": True,
            "skip_item_generation": False,
        },
    )
    return {
        "status": "awaiting_teaching_approval",
        "retry_target": NativeRetryTarget.ITEM_GENERATION.value,
        "item_generation": item_summary,
        "teaching": teaching,
    }


async def _run_teaching_only(generation_id: str) -> dict[str, Any]:
    from planning.whole_lesson.service import run_and_persist_teaching_plan
    from v3_blueprint.planning.persistence import persist_chunked_state

    async with async_session_factory() as session:
        teaching = await run_and_persist_teaching_plan(
            session, generation_id, require_items=True
        )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "awaiting_teaching_approval",
            "native_whole_lesson": True,
            "skip_item_generation": True,
        },
    )
    return {
        "status": "awaiting_teaching_approval",
        "retry_target": NativeRetryTarget.TEACHING_PLAN.value,
        "teaching": teaching,
    }


async def execute_native_retry(
    generation_id: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Claim retry target under lock, then run the matching checkpoint."""
    async with async_session_factory() as session:
        target, _claim = await _claim_native_retry(session, generation_id)

    if target == NativeRetryTarget.POST_APPROVAL_WORKER:
        return {
            "generation_id": generation_id,
            "status": "queued",
            "retry_target": target.value,
            "next_action": "wait",
        }

    failure_stage = (
        "item_generation"
        if target == NativeRetryTarget.ITEM_GENERATION
        else "planning_teaching"
    )
    try:
        if target == NativeRetryTarget.ITEM_GENERATION:
            result = await _run_items_then_teaching(
                generation_id, user_id=user_id or "system"
            )
        else:
            result = await _run_teaching_only(generation_id)
        await _clear_pre_worker_retry_flag(generation_id)
        return {
            "generation_id": generation_id,
            "next_action": "approve_teaching",
            **result,
        }
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
        await persist_native_failure_for_generation(
            generation_id,
            exc=exc,
            stage=stage,
            event="native_retry_failure",
        )
        await _clear_pre_worker_retry_flag(generation_id)
        raise


__all__ = [
    "NativeRetryConflict",
    "NativeRetryTarget",
    "decide_native_retry_target",
    "execute_native_retry",
    "next_action_for_retry_target",
]

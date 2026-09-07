"""Production Component Lectio execution (real executors + DB checkpoints).

Do not route live traffic through ``run_mocked_component_lectio_pipeline``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from builder.service import get_or_create_component_lectio_builder_lesson
from contracts.lesson_document import assert_valid_lesson_document
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.component_lectio.errors import AnswerKeyMappingError, WorkOrderIdentityError
from generation.component_lectio.lane_dispatch import (
    adapt_answer_key_order,
    adapt_content_order,
    adapt_items_order,
    adapt_visual_order,
    assemble_answer_key_from_refs,
    payload_from_component_block,
    payload_from_questions,
    payload_from_visuals,
    question_refs_from_payload,
    questions_from_item_payload,
    resolve_exact_order,
    stamp_component_block,
)
from generation.component_lectio.payload_validation import (
    ExactPayloadValidationError,
    validate_exact_payload,
)
from generation.contracts import GenerationInputForm as V3InputForm
from generation.contracts import GenerationSignalSummary as V3SignalSummary
from v3_blueprint.planning.canonical_plan import (
    SelectorFn,
    build_canonical_execution_plan,
    build_canonical_execution_plan_async,
    heuristic_select_components,
)
from v3_blueprint.planning.component_selector import (
    lesson_context_from_inputs,
    run_lectio_semantic_selector,
)
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.persistence import (
    insert_step,
    load_steps,
    persist_chunked_state,
    persist_structural_plan,
)
from v3_blueprint.planning.work_orders import (
    ExactWorkOrder,
    assert_writer_cannot_change_component,
    compile_exact_work_orders,
)
from v3_execution.executors.answer_key_generator import execute_answer_key
from v3_execution.executors.question_writer import execute_questions
from v3_execution.executors.section_writer import execute_section
from v3_execution.executors.visual_executor import execute_visual
from v3_execution.models import (
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    SectionWriterWorkOrder,
    WriterQuestion,
)
from v3_execution.runtime.failure_policy import (
    BudgetLedger,
    FailureClass,
    ClassifiedFailure,
    classify_failure,
    recovery_for,
)
from v3_execution.runtime.lesson_document import assemble_lesson_document, lesson_is_partial
from v3_execution.runtime.checkpoints import (
    BlockCheckpoint,
    CheckpointStore,
    GenerationControlState,
)

log = logging.getLogger(__name__)

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]
SectionExecutorFn = Callable[..., Awaitable[list[GeneratedComponentBlock]]]
QuestionExecutorFn = Callable[..., Awaitable[list[GeneratedQuestionBlock]]]
VisualExecutorFn = Callable[..., Awaitable[list[GeneratedVisualBlock]]]
AnswerKeyExecutorFn = Callable[..., Awaitable[GeneratedAnswerKeyBlock | None]]

READY_STEP = "block_ready"
FAILED_STEP = "block_failed"

DEFAULT_PRODUCTION_SELECTOR = run_lectio_semantic_selector


async def _silent_emit(_event: str, _payload: dict[str, Any]) -> None:
    return None


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def persist_component_lectio_start(
    generation_id: str,
    *,
    display_title: str | None = None,
) -> None:
    """Atomically mark Component Lectio running and clear prior terminal output."""
    now = _utc_now_naive()
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        state = dict(model.chunked_state_json or {})
        state.pop("lesson_document", None)
        control_meta = dict(state.get("control_meta") or {})
        control_meta["pipeline"] = "component_lectio"
        state.update(
            {
                "stage": "component_lectio_running",
                "execution_started": True,
                "error": None,
                "error_type": None,
                "error_code": None,
                "control_meta": control_meta,
            }
        )
        if display_title:
            state["display_title"] = display_title
        model.chunked_state_json = state
        model.status = "running"
        model.document_json = None
        model.quality_passed = None
        model.error = None
        model.error_type = None
        model.error_code = None
        model.completed_at = None
        model.last_heartbeat = now
        await session.commit()


async def persist_component_lectio_failure(
    generation_id: str,
    exc: BaseException,
) -> None:
    """Atomically persist matching scalar and chunked terminal failure state."""
    now = _utc_now_naive()
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        state = dict(model.chunked_state_json or {})
        state.pop("lesson_document", None)
        message = str(state.get("error") or str(exc) or type(exc).__name__)[:400]
        error_type = str(state.get("error_type") or type(exc).__name__)
        error_code = str(state.get("error_code") or "component_lectio_failed")
        control_meta = dict(state.get("control_meta") or {})
        control_meta["pipeline"] = "component_lectio"
        state.update(
            {
                "stage": "assembly_blocked",
                "execution_started": True,
                "error": message,
                "error_type": error_type,
                "error_code": error_code,
                "control_meta": control_meta,
            }
        )
        model.chunked_state_json = state
        model.status = "failed"
        model.document_json = None
        model.quality_passed = False
        model.error = message
        model.error_type = error_type
        model.error_code = error_code
        model.last_heartbeat = now
        model.completed_at = now
        await session.commit()


async def _persist_component_lectio_success(
    generation_id: str,
    *,
    document: dict[str, Any],
    plan_revision: int,
    plan_hash: str,
) -> str:
    """Atomically persist the final document and matching terminal state."""
    now = _utc_now_naive()
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        state = dict(model.chunked_state_json or {})
        state.update(
            {
                "stage": "complete",
                "execution_started": True,
                "lesson_document": document,
                "error": None,
                "error_type": None,
                "error_code": None,
                "control_meta": {
                    "plan_hash": plan_hash,
                    "plan_revision": plan_revision,
                    "pipeline": "component_lectio",
                    "partial": False,
                },
            }
        )
        model.chunked_state_json = state
        model.status = "completed"
        model.document_json = document
        model.quality_passed = True
        model.error = None
        model.error_type = None
        model.error_code = None
        model.last_heartbeat = now
        model.completed_at = now
        builder = await get_or_create_component_lectio_builder_lesson(
            session, generation=model, user_id=model.user_id
        )
        state["builder_id"] = builder.id
        # Assign a fresh mapping so SQLAlchemy's JSON change tracking persists
        # the linkage added after the terminal-state assignment above.
        model.chunked_state_json = {**state}
        await session.execute(
            update(GenerationModel)
            .where(GenerationModel.id == model.id)
            .values(chunked_state_json={**state})
        )
        await session.commit()
        return builder.id


def adapt_exact_orders_to_section_work_orders(
    orders: list[ExactWorkOrder],
    *,
    plan: StructuralPlan,
    template_id: str,
) -> list[SectionWriterWorkOrder]:
    """Adapt ExactWorkOrders into per-block SectionWriterWorkOrders (content lane)."""
    return [
        adapt_content_order(order, plan=plan, template_id=template_id)
        for order in orders
        if order.lane == "content"
    ]


def _blocks_from_executor(
    generated: list[GeneratedComponentBlock],
    *,
    scoped_orders: list[ExactWorkOrder],
) -> list[tuple[ExactWorkOrder, dict[str, Any]]]:
    results: list[tuple[ExactWorkOrder, dict[str, Any]]] = []
    for block in generated:
        order = resolve_exact_order(block, scoped_orders=scoped_orders)
        stamped = stamp_component_block(block, order)
        assert_writer_cannot_change_component(order, stamped.component_id)
        results.append((order, payload_from_component_block(stamped, order)))
    return results


async def _persist_ready_block(
    generation_id: str,
    *,
    block_id: str,
    payload: dict[str, Any],
    plan_revision: int,
    plan_hash: str,
    attempt: int,
    recovery: str | None = None,
) -> None:
    await insert_step(
        generation_id,
        part_id=block_id,
        step=READY_STEP,
        payload={
            "block_id": block_id,
            "plan_revision": plan_revision,
            "plan_hash": plan_hash,
            "attempt": attempt,
            "recovery": recovery,
            "payload": payload,
        },
    )


async def _persist_failed_block(
    generation_id: str,
    *,
    order: ExactWorkOrder,
    error: dict[str, Any],
) -> None:
    await insert_step(
        generation_id,
        part_id=order.block_id,
        step=FAILED_STEP,
        payload={
            "attempt": error.get("attempt"),
            "recovery": "exhausted",
            "error": error,
        },
    )


async def load_ready_block_ids(generation_id: str) -> set[str]:
    rows = await load_steps(generation_id)
    ready: set[str] = set()
    for row in rows:
        if row.step == READY_STEP:
            ready.add(row.part_id)
        elif row.step == FAILED_STEP:
            ready.discard(row.part_id)
    return ready


async def reconstruct_checkpoint_store(
    generation_id: str,
    *,
    plan_revision: int,
    plan_hash: str,
    desired_work: list[str],
) -> CheckpointStore:
    """Rebuild CheckpointStore view from DB generation_steps (durable)."""
    store = CheckpointStore(
        control=GenerationControlState(
            generation_id=generation_id,
            state="running",
            plan_revision=plan_revision,
            plan_hash=plan_hash,
            desired_work=desired_work,
        )
    )
    rows = await load_steps(generation_id)
    for row in rows:
        if row.step == READY_STEP:
            payload = row.payload if isinstance(row.payload, dict) else {}
            inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
            store.blocks[row.part_id] = BlockCheckpoint(
                block_id=row.part_id,
                plan_revision=int(payload.get("plan_revision") or plan_revision),
                plan_hash=str(payload.get("plan_hash") or plan_hash),
                state="ready",
                payload=inner if isinstance(inner, dict) else {},
            )
        elif row.step == FAILED_STEP:
            payload = row.payload if isinstance(row.payload, dict) else {}
            store.blocks[row.part_id] = BlockCheckpoint(
                block_id=row.part_id,
                plan_revision=plan_revision,
                plan_hash=plan_hash,
                state="failed",
                last_error=payload.get("error")
                if isinstance(payload.get("error"), dict)
                else {"message": str(payload)},
            )
    return store


def _structured_error(
    *,
    generation_id: str,
    order: ExactWorkOrder,
    exc: BaseException,
    failure_class: str,
    attempt: int,
) -> dict[str, Any]:
    validation_errors: list[str]
    if isinstance(exc, ExactPayloadValidationError):
        validation_errors = list(exc.errors) or [str(exc)[:400]]
        failure_class = "lectio_contract_validation"
    else:
        validation_errors = [str(exc)[:400]]
    return {
        "generation_id": generation_id,
        "section_id": order.section_id,
        "block_id": order.block_id,
        "component_id": order.locked_component_id,
        "section_field": order.section_field,
        "lane": order.lane,
        "class": failure_class,
        "message": str(exc)[:400],
        "validation_errors": validation_errors,
        "attempt": attempt,
    }


def _classify_block_failure(
    exc: BaseException,
    *,
    order: ExactWorkOrder,
) -> ClassifiedFailure:
    if isinstance(exc, AnswerKeyMappingError):
        return ClassifiedFailure(
            FailureClass.TERMINAL_CODE_ERROR,
            str(exc),
            block_id=order.block_id,
            terminal=True,
        )
    if isinstance(exc, ExactPayloadValidationError):
        if order.lane == "answer_key":
            return ClassifiedFailure(
                FailureClass.TERMINAL_CODE_ERROR,
                str(exc),
                block_id=order.block_id,
                terminal=True,
            )
        return ClassifiedFailure(
            FailureClass.COMPONENT_REPAIRABLE,
            str(exc),
            block_id=order.block_id,
            repairable=True,
        )
    if isinstance(exc, WorkOrderIdentityError):
        return ClassifiedFailure(
            FailureClass.TERMINAL_CODE_ERROR,
            str(exc),
            block_id=order.block_id,
            terminal=True,
        )
    return classify_failure(
        exc,
        block_id=order.block_id,
        kind_hint=order.lane if order.lane == "visual" else None,
    )


async def _execute_component_lectio_execution(
    *,
    generation_id: str,
    plan: StructuralPlan,
    signals: V3SignalSummary | None = None,
    form: V3InputForm | None = None,
    resource_spec: dict[str, Any] | None = None,
    emit_event: EmitFn | None = None,
    title: str | None = None,
    template_id: str = "guided-concept-path",
    section_executor: SectionExecutorFn | None = None,
    question_executor: QuestionExecutorFn | None = None,
    visual_executor: VisualExecutorFn | None = None,
    answer_key_executor: AnswerKeyExecutorFn | None = None,
    selector: SelectorFn | None = None,
) -> dict[str, Any]:
    """Production entrypoint: semantic selection → lanes → real executors → DB checkpoints."""
    del resource_spec
    execute_content = section_executor or execute_section
    execute_item = question_executor or execute_questions
    execute_vis = visual_executor or execute_visual
    execute_answers = answer_key_executor or execute_answer_key
    emit: EmitFn = emit_event or _silent_emit
    select = selector if selector is not None else DEFAULT_PRODUCTION_SELECTOR
    lesson_context = lesson_context_from_inputs(form=form, signals=signals)

    canonical, filled = await build_canonical_execution_plan_async(
        plan,
        generation_id=generation_id,
        lesson_id=title,
        template_id=template_id,
        selector=select,
        lesson_context=lesson_context,
    )
    await persist_structural_plan(generation_id, filled, form=form)
    await persist_chunked_state(
        generation_id,
        {
            "canonical_plan": canonical.model_dump(mode="json"),
            "selection_trace": canonical.selection_trace,
            "structural_plan": filled.model_dump(mode="json"),
            "stage": "component_lectio_running",
            "control_meta": {
                "plan_hash": canonical.plan_hash,
                "plan_revision": canonical.plan_revision,
                "pipeline": "component_lectio",
            },
        },
    )

    orders = compile_exact_work_orders(canonical, include_visual=True)
    desired = [order.block_id for order in orders]
    ready = await load_ready_block_ids(generation_id)
    pending_orders = [order for order in orders if order.block_id not in ready]
    ledgers: dict[str, BudgetLedger] = {}
    item_questions: dict[str, list[WriterQuestion]] = {}
    item_refs: dict[str, list[dict[str, Any]]] = {}
    last_error: str | None = None

    await emit(
        "component_lectio_execution_started",
        {
            "generation_id": generation_id,
            "pending_blocks": [o.block_id for o in pending_orders],
            "ready_blocks": sorted(ready),
        },
    )

    async def _collect_question_refs(section_id: str) -> list[dict[str, Any]]:
        refs = list(item_refs.get(section_id) or [])
        if refs:
            return refs
        questions = list(item_questions.get(section_id) or [])
        if questions:
            return [
                {
                    "id": q.id,
                    "question": q.purpose or q.id,
                    "expected_answer": q.expected_answer,
                    "difficulty": q.difficulty,
                }
                for q in questions
            ]
        store = await reconstruct_checkpoint_store(
            generation_id,
            plan_revision=canonical.plan_revision,
            plan_hash=canonical.plan_hash,
            desired_work=desired,
        )
        collected: list[dict[str, Any]] = []
        for sibling in orders:
            if sibling.lane == "items" and sibling.section_id == section_id:
                ckpt = store.blocks.get(sibling.block_id)
                if ckpt and ckpt.state == "ready":
                    collected.extend(question_refs_from_payload(ckpt.payload))
                    if not collected:
                        for q in questions_from_item_payload(ckpt.payload):
                            collected.append(
                                {
                                    "id": q.id,
                                    "question": q.purpose or q.id,
                                    "expected_answer": q.expected_answer,
                                    "difficulty": q.difficulty,
                                }
                            )
        return collected

    async def dispatch(
        order: ExactWorkOrder,
        *,
        repair_errors: list[str] | None = None,
    ) -> dict[str, Any]:
        if order.lane == "content":
            section_order = adapt_content_order(
                order,
                plan=filled,
                template_id=template_id,
                prior_errors=repair_errors,
            )
            generated = await execute_content(
                section_order,
                emit,
                trace_id=generation_id,
                generation_id=generation_id,
            )
            mapped = _blocks_from_executor(generated, scoped_orders=[order])
            if not mapped:
                raise WorkOrderIdentityError(
                    f"Content executor returned no matching block for {order.block_id}"
                )
            mapped_order, payload = mapped[0]
            if mapped_order.block_id != order.block_id:
                raise WorkOrderIdentityError(
                    f"Content output claimed {mapped_order.block_id}, expected {order.block_id}"
                )
            return validate_exact_payload(order, payload)
        if order.lane == "items":
            q_order = adapt_items_order(order, plan=filled, prior_errors=repair_errors)
            generated_q = await execute_item(
                q_order,
                emit,
                trace_id=generation_id,
                generation_id=generation_id,
            )
            payload = payload_from_questions(generated_q, order)
            validated = validate_exact_payload(order, payload)
            item_questions[order.section_id] = questions_from_item_payload(validated)
            item_refs[order.section_id] = question_refs_from_payload(validated)
            return validated
        if order.lane == "visual":
            v_order = adapt_visual_order(order, plan=filled, prior_errors=repair_errors)
            generated_v = await execute_vis(
                v_order,
                emit,
                trace_id=generation_id,
                generation_id=generation_id,
            )
            if not generated_v:
                raise RuntimeError("visual executor returned no blocks")
            # Prefer join by first frame; series/compare keep all frames.
            resolved = resolve_exact_order(generated_v[0], scoped_orders=[order])
            if resolved.block_id != order.block_id:
                raise WorkOrderIdentityError(
                    f"Visual output claimed {resolved.block_id}, expected {order.block_id}"
                )
            payload = payload_from_visuals(generated_v, order)
            return validate_exact_payload(order, payload)
        if order.lane == "answer_key":
            refs = await _collect_question_refs(order.section_id)
            # Deterministic Lectio mapping is the portable source of truth.
            # Injected answer_key_executor remains available for Studio/legacy callers
            # but Component Lectio checkpoints must not persist generator-native shapes.
            if execute_answers is not execute_answer_key:
                _ = await execute_answers(
                    adapt_answer_key_order(
                        order,
                        questions=questions_from_item_payload(
                            {"question_refs": refs, "content": {}}
                        ),
                    ),
                    emit,
                    trace_id=generation_id,
                    generation_id=generation_id,
                )
            payload = assemble_answer_key_from_refs(order, question_refs=refs)
            return validate_exact_payload(order, payload)
        raise RuntimeError(f"Unknown work-order lane: {order.lane}")

    async def execute_one(order: ExactWorkOrder) -> None:
        nonlocal last_error
        if order.block_id in ready:
            return
        ledger = ledgers.setdefault(order.block_id, BudgetLedger())
        attempt = 1
        repair_errors: list[str] | None = None
        try:
            payload = await dispatch(order)
            await _persist_ready_block(
                generation_id,
                block_id=order.block_id,
                payload=payload,
                plan_revision=canonical.plan_revision,
                plan_hash=canonical.plan_hash,
                attempt=attempt,
            )
            ready.add(order.block_id)
            await emit("block_ready", {"generation_id": generation_id, "block_id": order.block_id})
            return
        except Exception as exc:  # noqa: BLE001
            failure = _classify_block_failure(exc, order=order)
            action = recovery_for(failure, ledger, sibling_block_ids=sorted(ready))
            log.warning(
                "component_lectio_block_failure generation_id=%s block=%s class=%s action=%s",
                generation_id,
                order.block_id,
                failure.failure_class.value,
                action.action,
            )
            if action.action in {"retry", "repair"}:
                attempt = 2
                if isinstance(exc, ExactPayloadValidationError):
                    repair_errors = list(exc.errors)
                else:
                    repair_errors = [str(exc)[:400]]
                try:
                    payload = await dispatch(order, repair_errors=repair_errors)
                    await _persist_ready_block(
                        generation_id,
                        block_id=order.block_id,
                        payload=payload,
                        plan_revision=canonical.plan_revision,
                        plan_hash=canonical.plan_hash,
                        attempt=attempt,
                        recovery=action.action,
                    )
                    ready.add(order.block_id)
                    await emit(
                        "block_ready",
                        {"generation_id": generation_id, "block_id": order.block_id},
                    )
                    return
                except Exception as retry_exc:  # noqa: BLE001
                    exc = retry_exc
                    failure = _classify_block_failure(retry_exc, order=order)
            error = _structured_error(
                generation_id=generation_id,
                order=order,
                exc=exc,
                failure_class=(
                    "lectio_contract_validation"
                    if isinstance(exc, ExactPayloadValidationError)
                    else failure.failure_class.value
                ),
                attempt=attempt,
            )
            await _persist_failed_block(generation_id, order=order, error=error)
            last_error = error["message"]

    ordered = [order for order in pending_orders if order.lane != "answer_key"] + [
        order for order in pending_orders if order.lane == "answer_key"
    ]
    for order in ordered:
        await execute_one(order)

    store = await reconstruct_checkpoint_store(
        generation_id,
        plan_revision=canonical.plan_revision,
        plan_hash=canonical.plan_hash,
        desired_work=desired,
    )
    partial = lesson_is_partial(canonical, store)
    document = assemble_lesson_document(
        canonical,
        store,
        title=title or (form.topic if form else "Lesson"),
        subject=form.subject if form else "General",
        template_id=template_id,
        preset_id="blue-classroom",
    )

    if partial:
        store.mark_terminal("failed")
        await persist_chunked_state(
            generation_id,
            {
                "stage": "assembly_blocked",
                "error": last_error or "Required work remains incomplete",
                "error_type": "ComponentLectioIncomplete",
                "control_meta": {
                    "plan_hash": canonical.plan_hash,
                    "plan_revision": canonical.plan_revision,
                    "pipeline": "component_lectio",
                    "partial": True,
                },
            },
        )
        raise RuntimeError(last_error or "Required Component Lectio work remains incomplete")

    assert_valid_lesson_document(document)
    store.mark_terminal("complete")

    await _persist_component_lectio_success(
        generation_id,
        document=document,
        plan_revision=canonical.plan_revision,
        plan_hash=canonical.plan_hash,
    )
    await emit(
        "component_lectio_complete",
        {"generation_id": generation_id, "pipeline": "component_lectio"},
    )
    return document


async def run_component_lectio_execution(
    *,
    generation_id: str,
    plan: StructuralPlan,
    signals: V3SignalSummary | None = None,
    form: V3InputForm | None = None,
    resource_spec: dict[str, Any] | None = None,
    emit_event: EmitFn | None = None,
    title: str | None = None,
    template_id: str = "guided-concept-path",
    section_executor: SectionExecutorFn | None = None,
    question_executor: QuestionExecutorFn | None = None,
    visual_executor: VisualExecutorFn | None = None,
    answer_key_executor: AnswerKeyExecutorFn | None = None,
    selector: SelectorFn | None = None,
) -> dict[str, Any]:
    """Run Component Lectio with truthful scalar and chunked lifecycle state."""
    await persist_component_lectio_start(generation_id)
    try:
        return await _execute_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            signals=signals,
            form=form,
            resource_spec=resource_spec,
            emit_event=emit_event,
            title=title,
            template_id=template_id,
            section_executor=section_executor,
            question_executor=question_executor,
            visual_executor=visual_executor,
            answer_key_executor=answer_key_executor,
            selector=selector,
        )
    except Exception as exc:
        await persist_component_lectio_failure(generation_id, exc)
        raise


async def fill_plan_components_for_legacy_studio(
    plan: StructuralPlan,
    *,
    generation_id: str | None = None,
) -> StructuralPlan:
    """Studio rollback bridge: fill empty Stage-1 components via constrained selection."""
    _canonical, filled = build_canonical_execution_plan(
        plan,
        generation_id=generation_id,
        selector=heuristic_select_components,
    )
    return filled

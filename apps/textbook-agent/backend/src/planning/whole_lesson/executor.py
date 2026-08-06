"""Native whole-lesson executor: form plan → writers → LectioDocumentV2."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from contracts.lectio_page import get_intent_catalogue
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.page_objects import WriterContext, WriterResult, dispatch_writer_async
from generation.page_objects.document_assembly import (
    assemble_document_v2,
    assemble_section,
    persist_document_json,
    reload_document,
)
from planning.approved_items import ApprovedItemRecord, approved_items_as_writer_records
from planning.whole_lesson.events import make_event
from planning.whole_lesson.failure_injection import get_failure_injection
from planning.whole_lesson.figure_ids import stable_figure_request_id
from planning.whole_lesson.form_agent import run_form_planner
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.repository import PageDocumentRepository
from planning.whole_lesson.states import (
    DEFAULT_VARIANT_ID,
    MAX_WRITER_CONCURRENCY,
    execution_key,
)
from planning.whole_lesson.teaching_plan import TeachingPlan
from v3_blueprint.planning.models import PlannedBlock, SectionBlockPlan


class AssemblyError(RuntimeError):
    pass


def form_plan_to_section_plans(form_plan: FormPlan) -> dict[str, SectionBlockPlan]:
    plans: dict[str, SectionBlockPlan] = {}
    for section in form_plan.sections:
        blocks = [
            PlannedBlock(
                id=block.id,
                position=block.position,
                intent=block.intent,
                object=block.object,  # type: ignore[arg-type]
                evidence=block.evidence or "Form-assigned block.",
                brief=block.brief,
                placement=block.placement,
                source_question_ids=list(block.source_question_ids),
            )
            for block in section.blocks
        ]
        plans[section.slot_id] = SectionBlockPlan(blocks=blocks)
    return plans


def _packet_item_records(packet: ImmutableLessonPacket) -> tuple[dict[str, Any], ...]:
    records = tuple(
        ApprovedItemRecord(
            id=item.id,
            card_id=item.card_id,
            stem=item.stem,
            options=tuple(dict(option) for option in item.options),
            correct_key=item.correct_key,
            diagnoses=dict(item.diagnoses),
        )
        for item in packet.approved_items
    )
    return approved_items_as_writer_records(records)


def _structured_error(
    *,
    exc: BaseException,
    stage: str,
    section_id: str = "",
    block_id: str = "",
    key: str = "",
    attempt: int = 1,
    retryable: bool = True,
) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "code": "PROVIDER_CONNECTION"
        if "connection" in str(exc).lower() or "timeout" in str(exc).lower()
        else "WRITER_FAILURE",
        "message": str(exc)[:500] or type(exc).__name__,
        "stage": stage,
        "section_id": section_id,
        "block_id": block_id,
        "execution_key": key,
        "attempt": attempt,
        "retryable": retryable,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _should_skip_outcome(outcome: dict[str, Any] | None) -> bool:
    if not outcome:
        return False
    return str(outcome.get("status") or "") in {"ready", "visual_pending"}


def _should_retry_outcome(outcome: dict[str, Any] | None) -> bool:
    if not outcome:
        return True
    status = str(outcome.get("status") or "")
    if status in {"ready", "visual_pending"}:
        return False
    if status == "failed_terminal":
        return False
    if status in {"failed", "failed_recoverable", "started"}:
        return True
    return True


async def _write_one_block(
    *,
    generation_id: str,
    slot_id: str,
    block: Any,
    index: int,
    flat_blocks: list[tuple[str, Any]],
    packet: ImmutableLessonPacket,
    intents: dict[str, Any],
    item_records: tuple[dict[str, Any], ...],
    variant_id: str,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    key = execution_key(slot_id, block.id, variant_id)
    attempt = int((prior or {}).get("attempts") or 0) + 1
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        await repo.save_block_outcome(
            key,
            {
                "status": "started",
                "attempts": attempt,
                "section_id": slot_id,
                "block_id": block.id,
                "variant_id": variant_id,
                "object": block.object,
                "intent": block.intent,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )
        await repo.append_event(
            make_event(
                "block_started",
                generation_id=generation_id,
                section_id=slot_id,
                block_id=block.id,
                position=block.position,
                object_id=block.object,
                status="started",
            )
        )

    injection = get_failure_injection()
    if injection.should_fail(generation_id=generation_id, block_index=index):
        exc = RuntimeError("injected writer failure for Phase 02 proof")
        error = _structured_error(
            exc=exc,
            stage="writing_blocks",
            section_id=slot_id,
            block_id=block.id,
            key=key,
            attempt=attempt,
            retryable=True,
        )
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, generation_id)
            await repo.save_block_outcome(
                key,
                {
                    "status": "failed_recoverable",
                    "attempts": attempt,
                    "error": error,
                    "section_id": slot_id,
                    "block_id": block.id,
                    "variant_id": variant_id,
                    "object": block.object,
                    "intent": block.intent,
                },
            )
            await repo.append_event(
                make_event(
                    "block_failed",
                    generation_id=generation_id,
                    section_id=slot_id,
                    block_id=block.id,
                    status="failed",
                    error=error["message"],
                )
            )
        return {"execution_key": key, "status": "failed_recoverable", "error": error}

    prev_brief = flat_blocks[index - 1][1].brief if index > 0 else ""
    next_brief = flat_blocks[index + 1][1].brief if index + 1 < len(flat_blocks) else ""
    intent_guidance = ""
    intent_rec = intents.get(block.intent)
    if isinstance(intent_rec, dict):
        intent_guidance = str(intent_rec.get("generation_guidance") or "")
    planned = PlannedBlock(
        id=block.id,
        position=block.position,
        intent=block.intent,
        object=block.object,  # type: ignore[arg-type]
        evidence=block.evidence or "Form-assigned block.",
        brief=block.brief,
        placement=block.placement,
        source_question_ids=list(block.source_question_ids),
    )
    ctx = WriterContext(
        planned=planned,
        terminology=tuple(packet.scope.terminology),
        neighbour_summaries=(prev_brief, next_brief, intent_guidance),
        item_records=item_records,
        lesson_context={
            "objective": packet.lesson.objective,
            "grade_level": packet.lesson.grade_level,
            "subject": packet.lesson.subject,
            "anchor": packet.anchor.model_dump(mode="json"),
            "must_not_introduce": [
                entry.statement for entry in packet.scope.must_not_introduce
            ],
        },
        generation_id=generation_id,
        use_llm=True,
    )

    last_error: dict[str, Any] | None = None
    max_attempts = 3
    for transport_attempt in range(1, max_attempts + 1):
        try:
            result = await dispatch_writer_async(ctx)
            if result.object == "figure":
                rid = stable_figure_request_id(
                    generation_id=generation_id, block_id=block.id
                )
                content = dict(result.content)
                asset = dict(content.get("asset") or {})
                asset["request_id"] = rid
                content["asset"] = asset
                result.request_id = rid
                result.content = content
            status = result.status if result.status in {"ready", "visual_pending"} else "ready"
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                await repo.save_block_outcome(
                    key,
                    {
                        "status": status,
                        "attempts": attempt,
                        "section_id": slot_id,
                        "block_id": block.id,
                        "variant_id": variant_id,
                        "object": result.object,
                        "intent": result.intent,
                        "content": result.content,
                        "request_id": result.request_id,
                        "error": None,
                    },
                )
                await repo.append_event(
                    make_event(
                        "block_ready" if status == "ready" else "visual_pending",
                        generation_id=generation_id,
                        section_id=slot_id,
                        block_id=block.id,
                        status=status,
                    )
                )
            return {
                "execution_key": key,
                "status": status,
                "result": result,
            }
        except Exception as exc:  # noqa: BLE001
            retryable = transport_attempt < max_attempts
            last_error = _structured_error(
                exc=exc,
                stage="writing_blocks",
                section_id=slot_id,
                block_id=block.id,
                key=key,
                attempt=attempt,
                retryable=retryable,
            )
            if retryable:
                delay = min(8.0, (2 ** (transport_attempt - 1)) + random.random())
                await asyncio.sleep(delay)
                continue
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                await repo.save_block_outcome(
                    key,
                    {
                        "status": "failed_terminal",
                        "attempts": attempt,
                        "error": last_error,
                        "section_id": slot_id,
                        "block_id": block.id,
                        "variant_id": variant_id,
                        "object": block.object,
                        "intent": block.intent,
                    },
                )
                await repo.append_event(
                    make_event(
                        "block_failed",
                        generation_id=generation_id,
                        section_id=slot_id,
                        block_id=block.id,
                        status="failed",
                        error=last_error["message"],
                    )
                )
            return {
                "execution_key": key,
                "status": "failed_terminal",
                "error": last_error,
            }
    return {"execution_key": key, "status": "failed_terminal", "error": last_error}


async def write_form_blocks(
    *,
    generation_id: str,
    form_plan: FormPlan,
    packet: ImmutableLessonPacket,
    variant_id: str = DEFAULT_VARIANT_ID,
) -> list[dict[str, Any]]:
    """Write pending form blocks with bounded concurrency and failure isolation."""
    intents = get_intent_catalogue().get("intents") or {}
    item_records = _packet_item_records(packet)
    flat_blocks = [
        (section.slot_id, block)
        for section in form_plan.sections
        for block in section.blocks
    ]
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        stored = await repo.load_block_results()

    pending: list[tuple[int, str, Any]] = []
    for index, (slot_id, block) in enumerate(flat_blocks):
        key = execution_key(slot_id, block.id, variant_id)
        prior = stored.get(key)
        if _should_skip_outcome(prior):
            continue
        if not _should_retry_outcome(prior):
            continue
        pending.append((index, slot_id, block))

    semaphore = asyncio.Semaphore(MAX_WRITER_CONCURRENCY)
    outcomes: list[dict[str, Any]] = []

    async def _run(item: tuple[int, str, Any]) -> dict[str, Any]:
        index, slot_id, block = item
        key = execution_key(slot_id, block.id, variant_id)
        async with semaphore:
            return await _write_one_block(
                generation_id=generation_id,
                slot_id=slot_id,
                block=block,
                index=index,
                flat_blocks=flat_blocks,
                packet=packet,
                intents=intents,
                item_records=item_records,
                variant_id=variant_id,
                prior=stored.get(key),
            )

    if pending:
        outcomes = list(await asyncio.gather(*[_run(item) for item in pending]))
    return outcomes


def _writer_result_from_outcome(outcome: dict[str, Any]) -> WriterResult:
    return WriterResult(
        block_id=str(outcome.get("block_id") or ""),
        object=str(outcome.get("object") or "prose"),
        intent=str(outcome.get("intent") or ""),
        status=str(outcome.get("status") or "ready"),
        content=dict(outcome.get("content") or {}),
        request_id=outcome.get("request_id"),
    )


async def assemble_from_db(
    *,
    session: AsyncSession,
    generation_id: str,
    packet: ImmutableLessonPacket,
    form_plan: FormPlan,
    variant_id: str = DEFAULT_VARIANT_ID,
) -> dict[str, Any]:
    repo = PageDocumentRepository(session, generation_id)
    expected = await repo.load_expected_writer_results(
        form_plan=form_plan.model_dump(mode="json"),
        variant_id=variant_id,
    )
    failures: list[str] = []
    for key, outcome in expected.items():
        if not outcome:
            failures.append(f"missing:{key}")
            continue
        status = str(outcome.get("status") or "")
        if status in {"failed", "failed_recoverable", "failed_terminal", "started"}:
            failures.append(f"{status}:{key}")
            continue
        if status not in {"ready", "visual_pending"}:
            failures.append(f"bad_status:{key}:{status}")
    if failures:
        raise AssemblyError(f"cannot assemble: {failures}")

    section_plans = form_plan_to_section_plans(form_plan)
    sections_out = []
    for section in form_plan.sections:
        ordered: list[WriterResult] = []
        for block in section.blocks:
            key = execution_key(section.slot_id, block.id, variant_id)
            outcome = expected[key]
            if str(outcome.get("object") or "") != block.object:
                raise AssemblyError(f"object mismatch for {key}")
            if str(outcome.get("intent") or "") != block.intent:
                raise AssemblyError(f"intent mismatch for {key}")
            ordered.append(_writer_result_from_outcome({**outcome, "block_id": block.id}))
        sections_out.append(
            assemble_section(
                section_id=section.slot_id,
                title=section.slot_id.title(),
                plan=section_plans[section.slot_id],
                writer_results=ordered,
            )
        )
    document = assemble_document_v2(
        title=packet.lesson.objective[:80],
        sections=sections_out,
        metadata={
            "catalogue_version": "1.1.0",
            "resource_type": "lesson",
            "objective": packet.lesson.objective,
            "subject": packet.lesson.subject,
            "grade_level": packet.lesson.grade_level,
            "knowledge_type": packet.lesson.knowledge_type,
            "lesson_mode": packet.lesson.lesson_mode,
            "native_whole_lesson": True,
        },
    )
    generation = await session.get(GenerationModel, generation_id)
    if generation is None:
        raise KeyError(generation_id)
    generation.document_json = persist_document_json(generation.document_json, document)
    await session.commit()

    # Fresh-session reload proof.
    async with async_session_factory() as fresh:
        gen2 = await fresh.get(GenerationModel, generation_id)
        if gen2 is None:
            raise KeyError(generation_id)
        reloaded = reload_document(gen2.document_json)
        if not isinstance(reloaded, dict):
            raise AssemblyError("fresh-session reload failed")

    pending_visuals = any(
        str((expected[key] or {}).get("status") or "") == "visual_pending" for key in expected
    )
    repo = PageDocumentRepository(session, generation_id)
    await repo.bump_document_revision()
    if pending_visuals:
        await repo.transition(
            expected={"assembling", "writing_blocks"},
            target="awaiting_visuals",
            event="document_awaiting_visuals",
        )
        terminal = "awaiting_visuals"
    else:
        await repo.transition(
            expected={"assembling", "writing_blocks", "awaiting_visuals"},
            target="ready",
            event="document_ready",
        )
        terminal = "ready"
    return {
        "document": document,
        "terminal": terminal,
        "writer_count": len(expected),
    }


async def execute_after_teaching_approval(
    *,
    session: AsyncSession,
    generation_id: str,
    packet: ImmutableLessonPacket | None = None,
    teaching_plan: TeachingPlan | None = None,
    worker_id: str | None = None,
) -> dict[str, Any]:
    """Resume-safe form plan → write blocks → assemble from DB."""
    repo = PageDocumentRepository(session, generation_id)
    state = await repo.load_page_generation_state()
    if packet is None:
        packet = ImmutableLessonPacket.model_validate(state["lesson_packet"])
    if teaching_plan is None and state.get("teaching_plan"):
        try:
            teaching_plan = TeachingPlan.model_validate(state["teaching_plan"])
        except Exception:  # noqa: BLE001
            teaching_plan = None

    generation = await session.get(GenerationModel, generation_id)
    current = str(generation.status if generation else "")
    if current == "queued":
        await repo.transition(
            expected={"queued"},
            target="planning_forms",
            event="form_plan_started",
        )
    elif current not in {"planning_forms", "writing_blocks", "assembling"}:
        # Claim path already moved queued → planning_forms.
        pass

    form_plan_raw = state.get("form_plan")
    form_validation = state.get("form_validation") or {}
    if isinstance(form_plan_raw, dict) and form_validation.get("ok") is True:
        form_plan = FormPlan.model_validate(form_plan_raw)
        await repo.append_event(
            make_event("form_plan_reused", generation_id=generation_id, status="ready")
        )
    else:
        await repo.append_event(
            make_event("form_plan_started", generation_id=generation_id, status="started")
        )
        form_result = await run_form_planner(
            packet, teaching_plan, generation_id=generation_id
        )
        if not form_result.validation.ok:
            error = {
                "type": "ValidationError",
                "code": "FORM_PLAN_INVALID",
                "message": "form plan validation failed",
                "stage": "planning_forms",
                "retryable": True,
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            await repo.transition(
                expected={"planning_forms"},
                target="failed_recoverable",
                event="form_plan_failed",
                error=error,
            )
            if worker_id:
                await repo.release_execution(worker_id=worker_id)
            return {"status": "failed_recoverable", "error": error}
        await repo.save_form_plan(
            plan=form_result.plan.model_dump(mode="json"),
            validation=form_result.validation.to_dict(),
            qc=form_result.qc,
            prompt=form_result.prompt,
            raw=form_result.raw_response,
        )
        form_plan = form_result.plan
        await repo.append_event(
            make_event("form_plan_ready", generation_id=generation_id, status="ready")
        )

    generation = await session.get(GenerationModel, generation_id)
    if generation and generation.status == "planning_forms":
        await repo.transition(
            expected={"planning_forms"},
            target="writing_blocks",
            event="writing_blocks_started",
        )

    await write_form_blocks(
        generation_id=generation_id,
        form_plan=form_plan,
        packet=packet,
    )

    # Re-load outcomes after concurrent writers.
    async with async_session_factory() as check_session:
        check_repo = PageDocumentRepository(check_session, generation_id)
        expected = await check_repo.load_expected_writer_results(
            form_plan=form_plan.model_dump(mode="json")
        )
    retryable = [
        key
        for key, outcome in expected.items()
        if str((outcome or {}).get("status") or "") in {"failed_recoverable", "failed", "started", ""}
    ]
    terminal_failed = [
        key
        for key, outcome in expected.items()
        if str((outcome or {}).get("status") or "") == "failed_terminal"
    ]
    if terminal_failed:
        async with async_session_factory() as s:
            r = PageDocumentRepository(s, generation_id)
            await r.transition(
                expected={"writing_blocks", "assembling"},
                target="failed_terminal",
                event="writing_failed_terminal",
                error={
                    "type": "WriterError",
                    "code": "TERMINAL_BLOCK_FAILURE",
                    "message": f"terminal failures: {terminal_failed}",
                    "stage": "writing_blocks",
                    "retryable": False,
                    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            if worker_id:
                await r.release_execution(worker_id=worker_id)
        return {"status": "failed_terminal", "failed": terminal_failed}
    if retryable:
        async with async_session_factory() as s:
            r = PageDocumentRepository(s, generation_id)
            await r.transition(
                expected={"writing_blocks", "assembling"},
                target="failed_recoverable",
                event="writing_failed_recoverable",
                error={
                    "type": "WriterError",
                    "code": "RETRYABLE_BLOCK_FAILURE",
                    "message": f"retryable failures: {retryable}",
                    "stage": "writing_blocks",
                    "retryable": True,
                    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            if worker_id:
                await r.release_execution(worker_id=worker_id)
        return {"status": "failed_recoverable", "failed": retryable}

    async with async_session_factory() as s:
        r = PageDocumentRepository(s, generation_id)
        generation = await s.get(GenerationModel, generation_id)
        if generation and generation.status == "writing_blocks":
            await r.transition(
                expected={"writing_blocks"},
                target="assembling",
                event="document_assembling",
            )
        assembled = await assemble_from_db(
            session=s,
            generation_id=generation_id,
            packet=packet,
            form_plan=form_plan,
        )
        if worker_id:
            await r.release_execution(worker_id=worker_id)
        return {
            "status": assembled["terminal"],
            "form_plan": form_plan.model_dump(mode="json"),
            "document": assembled["document"],
            "writer_count": assembled["writer_count"],
        }

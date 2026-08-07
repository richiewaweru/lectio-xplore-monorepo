"""Native whole-lesson executor: form plan → writers → LectioDocumentV2."""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from contracts.lectio_page import get_intent_catalogue, validate_document
from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.page_objects import WriterContext, WriterError, WriterOutcome, dispatch_writer_async
from generation.page_objects.document_assembly import (
    assemble_document_v2,
    assemble_section,
    canonical_document_sha256,
    reload_document,
)
from planning.approved_items import ApprovedItemRecord, approved_items_as_writer_records
from planning.whole_lesson.events import make_event
from planning.whole_lesson.failure_injection import get_failure_injection
from planning.whole_lesson.failure_policy import (
    classify_failure,
    structured_error_from_exc,
)
from planning.whole_lesson.figure_ids import stable_figure_request_id
from planning.whole_lesson.form_agent import NoLegalFormCandidatesError, run_form_planner
from planning.whole_lesson.form_plan import FormPlan, coerce_form_plan
from planning.whole_lesson.legality import LessonLegalityError, LessonLegalitySnapshot
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.catalogue_projections import build_form_candidate_map, project_form_guidance
from planning.whole_lesson.repository import PageDocumentRepository
from planning.whole_lesson.resolved_block_plan import (
    ResolvedBlockPlan,
    resolve_block_plans,
)
from planning.whole_lesson.validation import validate_form_plan
from planning.whole_lesson.states import (
    DEFAULT_VARIANT_ID,
    MAX_SECTION_CONCURRENCY,
    MAX_WRITER_CONCURRENCY,
    WRITING_STATUSES,
    ExecutionLease,
    LeaseLostError,
    ResumeDecision,
    decide_resume,
    execution_key,
)
from planning.whole_lesson.teaching_plan import TeachingPlan
from v3_blueprint.planning.models import SectionBlockPlan


class AssemblyError(RuntimeError):
    pass


def normalize_writer_status(
    *,
    object_id: str,
    writer_status: str,
    content: dict[str, Any],
) -> str:
    """Canonicalize block execution status. Never default unknown to ready."""
    status = str(writer_status or "").strip()
    asset = dict((content or {}).get("asset") or {})
    asset_status = str(asset.get("status") or "").strip()
    if object_id == "figure":
        if asset_status and asset_status != "ready":
            return "visual_pending"
        if status in {"pending", "visual_pending"}:
            return "visual_pending"
        if status == "ready" and (not asset_status or asset_status == "ready"):
            return "ready"
        if status == "ready":
            return "visual_pending"
        raise WriterError(
            f"invalid figure writer status {status!r} asset={asset_status!r}"
        )
    if status == "ready":
        return "ready"
    if status == "visual_pending":
        return "visual_pending"
    if status == "pending" and object_id == "figure":
        return "visual_pending"
    raise WriterError(f"invalid writer status {status!r} for object {object_id!r}")


def form_plan_to_section_plans(
    form_plan: FormPlan,
    *,
    teaching_plan: TeachingPlan,
) -> dict[str, SectionBlockPlan]:
    """Join teaching + form into writer SectionBlockPlan views."""
    return resolve_block_plans(teaching_plan, form_plan).to_section_block_plans()


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


def expected_execution_keys(
    form_plan: FormPlan, *, variant_id: str = DEFAULT_VARIANT_ID
) -> set[str]:
    return {
        execution_key(section.slot_id, decision.block_id, variant_id)
        for section in form_plan.sections
        for decision in section.forms
    }


async def _write_one_block(
    *,
    generation_id: str,
    slot_id: str,
    block: ResolvedBlockPlan,
    index: int,
    absolute_index: int,
    section_blocks: list[ResolvedBlockPlan],
    packet: ImmutableLessonPacket,
    intents: dict[str, Any],
    item_records: tuple[dict[str, Any], ...],
    variant_id: str,
    prior: dict[str, Any] | None,
    lease: ExecutionLease | None,
) -> dict[str, Any]:
    key = execution_key(slot_id, block.id, variant_id)
    attempt = int((prior or {}).get("attempts") or 0) + 1
    worker_id = lease.worker_id if lease else None
    lease_token = lease.lease_token if lease else None

    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        try:
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
                worker_id=worker_id,
                lease_token=lease_token,
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
                ),
                worker_id=worker_id,
                lease_token=lease_token,
            )
        except LeaseLostError as exc:
            return {"execution_key": key, "status": "lease_lost", "error": str(exc)}

    injection = get_failure_injection()
    if injection.should_fail(generation_id=generation_id, block_index=absolute_index):
        exc = RuntimeError("injected writer failure for Phase 02 proof")
        error = structured_error_from_exc(
            exc=exc,
            stage="writing_sections",
            section_id=slot_id,
            block_id=block.id,
            key=key,
            attempt=attempt,
        )
        error["retryable"] = True
        error["code"] = "TRANSPORT"
        async with async_session_factory() as session:
            repo = PageDocumentRepository(session, generation_id)
            try:
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
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
                await repo.append_event(
                    make_event(
                        "block_failed",
                        generation_id=generation_id,
                        section_id=slot_id,
                        block_id=block.id,
                        status="failed",
                        error=error["message"],
                    ),
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
            except LeaseLostError as lost:
                return {"execution_key": key, "status": "lease_lost", "error": str(lost)}
        return {"execution_key": key, "status": "failed_recoverable", "error": error}

    prev_brief = section_blocks[index - 1].brief if index > 0 else ""
    next_brief = (
        section_blocks[index + 1].brief if index + 1 < len(section_blocks) else ""
    )
    intent_guidance = ""
    intent_rec = intents.get(block.intent)
    if isinstance(intent_rec, dict):
        intent_guidance = str(intent_rec.get("generation_guidance") or "")
    planned = block.to_planned_block()
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
        section_id=slot_id,
    )

    last_error: dict[str, Any] | None = None
    transport_attempts = 0
    max_transport = 3
    while True:
        try:
            result = await dispatch_writer_async(ctx)
            if block.object == "figure":
                rid = stable_figure_request_id(
                    generation_id=generation_id, block_id=block.id
                )
                content = dict(result.content)
                asset = dict(content.get("asset") or {})
                asset["request_id"] = rid
                content["asset"] = asset
                result.request_id = rid
                result.content = content
            status = normalize_writer_status(
                object_id=block.object,
                writer_status=result.status,
                content=dict(result.content or {}),
            )
            answer_entries = [dict(entry) for entry in (result.answer_entries or ())]
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
                        # DENORMALIZED CACHE ONLY.
                        # Canonical object/intent come from ResolvedBlockPlan.
                        "object": block.object,
                        "intent": block.intent,
                        "content": result.content,
                        "request_id": result.request_id,
                        "answer_entries": answer_entries,
                        "error": None,
                    },
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
                await repo.append_event(
                    make_event(
                        "block_ready" if status == "ready" else "visual_pending",
                        generation_id=generation_id,
                        section_id=slot_id,
                        block_id=block.id,
                        status=status,
                    ),
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
            return {
                "execution_key": key,
                "status": status,
                "result": result,
                "answer_entries": answer_entries,
            }
        except LeaseLostError as exc:
            return {"execution_key": key, "status": "lease_lost", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            classification = classify_failure(exc)
            last_error = structured_error_from_exc(
                exc=exc,
                stage="writing_sections",
                section_id=slot_id,
                block_id=block.id,
                key=key,
                attempt=attempt,
            )
            if classification.code == "LEASE_LOST":
                return {"execution_key": key, "status": "lease_lost", "error": last_error}
            if classification.code in {"TRANSPORT", "TIMEOUT", "RATE_LIMIT"}:
                transport_attempts += 1
                if transport_attempts < max_transport:
                    delay = min(8.0, (2 ** (transport_attempts - 1)) + random.random())
                    await asyncio.sleep(delay)
                    continue
                terminal_status = "failed_terminal"
            elif classification.code in {"VALIDATION", "CONTRACT"}:
                # Informed repair already ran inside dispatch_writer_async.
                terminal_status = (
                    "failed_recoverable" if classification.retryable else "failed_terminal"
                )
            elif classification.code == "PROGRAMMING":
                terminal_status = "failed_terminal"
            elif classification.retryable:
                transport_attempts += 1
                if transport_attempts < max_transport:
                    continue
                terminal_status = "failed_terminal"
            else:
                terminal_status = "failed_terminal"
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                try:
                    await repo.save_block_outcome(
                        key,
                        {
                            "status": terminal_status,
                            "attempts": attempt,
                            "error": last_error,
                            "section_id": slot_id,
                            "block_id": block.id,
                            "variant_id": variant_id,
                            "object": block.object,
                            "intent": block.intent,
                        },
                        worker_id=worker_id,
                        lease_token=lease_token,
                    )
                    await repo.append_event(
                        make_event(
                            "block_failed",
                            generation_id=generation_id,
                            section_id=slot_id,
                            block_id=block.id,
                            status="failed",
                            error=last_error["message"],
                        ),
                        worker_id=worker_id,
                        lease_token=lease_token,
                    )
                except LeaseLostError as lost:
                    return {"execution_key": key, "status": "lease_lost", "error": str(lost)}
            return {
                "execution_key": key,
                "status": terminal_status,
                "error": last_error,
            }


async def write_form_blocks(
    *,
    generation_id: str,
    form_plan: FormPlan,
    packet: ImmutableLessonPacket,
    teaching_plan: TeachingPlan,
    variant_id: str = DEFAULT_VARIANT_ID,
    lease: ExecutionLease | None = None,
) -> list[dict[str, Any]]:
    """Write pending form blocks section-by-section with bounded concurrency."""
    resolved = resolve_block_plans(teaching_plan, form_plan)
    intents = get_intent_catalogue().get("intents") or {}
    item_records = _packet_item_records(packet)
    async with async_session_factory() as session:
        repo = PageDocumentRepository(session, generation_id)
        stored = await repo.load_block_results()
        current_token = lease.lease_token if lease else None
        if current_token is None:
            state = await repo.load_page_generation_state()
            current_token = int((state.get("execution") or {}).get("lease_token") or 0)

    section_semaphore = asyncio.Semaphore(MAX_SECTION_CONCURRENCY)
    outcomes: list[dict[str, Any]] = []
    absolute_offsets: dict[str, int] = {}
    running = 0
    for section in resolved.sections:
        absolute_offsets[section.slot_id] = running
        running += len(section.blocks)

    async def _write_section(section: Any) -> list[dict[str, Any]]:
        slot_id = section.slot_id
        section_blocks = list(section.blocks)
        section_offset = absolute_offsets[slot_id]
        pending: list[tuple[int, ResolvedBlockPlan]] = []
        for index, block in enumerate(section_blocks):
            key = execution_key(slot_id, block.id, variant_id)
            prior = stored.get(key)
            decision = decide_resume(prior, current_lease_token=current_token)
            async with async_session_factory() as session:
                repo = PageDocumentRepository(session, generation_id)
                try:
                    await repo.append_event(
                        make_event(
                            "resume_decision",
                            generation_id=generation_id,
                            section_id=slot_id,
                            block_id=block.id,
                            status=decision.value,
                            execution_key=key,
                        ),
                        worker_id=lease.worker_id if lease else None,
                        lease_token=lease.lease_token if lease else None,
                    )
                except LeaseLostError:
                    return [{"execution_key": key, "status": "lease_lost"}]
            if decision in {
                ResumeDecision.SKIP_READY,
                ResumeDecision.SKIP_IN_FLIGHT,
                ResumeDecision.BLOCK_TERMINAL,
            }:
                continue
            pending.append((index, block))

        if not pending:
            return []

        block_semaphore = asyncio.Semaphore(MAX_WRITER_CONCURRENCY)

        async def _run(item: tuple[int, ResolvedBlockPlan]) -> dict[str, Any]:
            index, block = item
            key = execution_key(slot_id, block.id, variant_id)
            async with block_semaphore:
                return await _write_one_block(
                    generation_id=generation_id,
                    slot_id=slot_id,
                    block=block,
                    index=index,
                    absolute_index=section_offset + index,
                    section_blocks=section_blocks,
                    packet=packet,
                    intents=intents,
                    item_records=item_records,
                    variant_id=variant_id,
                    prior=stored.get(key),
                    lease=lease,
                )

        async with section_semaphore:
            return list(await asyncio.gather(*[_run(item) for item in pending]))

    section_results = await asyncio.gather(
        *[_write_section(section) for section in resolved.sections]
    )
    for batch in section_results:
        outcomes.extend(batch)
    return outcomes


def _writer_result_from_outcome(outcome: dict[str, Any]) -> WriterOutcome:
    raw_answers = outcome.get("answer_entries") or ()
    answer_entries = tuple(
        dict(entry) for entry in raw_answers if isinstance(entry, dict)
    )
    return WriterOutcome(
        block_id=str(outcome.get("block_id") or ""),
        status=str(outcome.get("status") or "ready"),
        content=dict(outcome.get("content") or {}),
        request_id=outcome.get("request_id"),
        answer_entries=answer_entries,
    )


def _section_title(
    section: Any,
    *,
    teaching_plan: TeachingPlan | None = None,
) -> str:
    purpose = str(getattr(section, "specific_purpose", "") or "").strip()
    if purpose:
        return purpose
    title = str(getattr(section, "title", "") or "").strip()
    if title:
        return title
    if teaching_plan is not None:
        for teaching_section in teaching_plan.sections:
            if teaching_section.slot_id == section.slot_id:
                purpose = str(teaching_section.specific_purpose or "").strip()
                if purpose:
                    return purpose
                break
    return section.slot_id.replace("_", " ").title()


async def assemble_from_db(
    *,
    session: AsyncSession,
    generation_id: str,
    packet: ImmutableLessonPacket,
    form_plan: FormPlan,
    teaching_plan: TeachingPlan,
    variant_id: str = DEFAULT_VARIANT_ID,
    lease: ExecutionLease | None = None,
) -> dict[str, Any]:
    """Assemble from exact DB key set. Dict storage precludes duplicate keys."""
    if lease is None:
        raise AssemblyError("assemble_from_db requires an ExecutionLease")
    resolved = resolve_block_plans(teaching_plan, form_plan)
    repo = PageDocumentRepository(session, generation_id)
    form_dump = form_plan.model_dump(mode="json")
    expected = await repo.load_expected_writer_results(
        form_plan=form_dump,
        variant_id=variant_id,
    )
    expected_keys = expected_execution_keys(form_plan, variant_id=variant_id)
    stored = await repo.load_block_results()
    stored_keys = set(stored.keys())
    missing = sorted(expected_keys - stored_keys)
    unknown = sorted(stored_keys - expected_keys)
    failures: list[str] = []
    if missing:
        failures.append(f"missing:{missing}")
    if unknown:
        failures.append(f"unknown:{unknown}")
    for key in expected_keys:
        outcome = expected.get(key) or stored.get(key) or {}
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

    section_plans = resolved.to_section_block_plans()
    sections_out = []
    answer_entries: list[dict[str, Any]] = []
    writer_results: list[WriterOutcome] = []
    for section in resolved.sections:
        ordered: list[WriterOutcome] = []
        for block in section.blocks:
            key = execution_key(section.slot_id, block.id, variant_id)
            outcome = expected[key]
            if str(outcome.get("object") or "") != block.object:
                raise AssemblyError(f"object mismatch for {key}")
            if str(outcome.get("intent") or "") != block.intent:
                raise AssemblyError(f"intent mismatch for {key}")
            result = _writer_result_from_outcome({**outcome, "block_id": block.id})
            ordered.append(result)
            writer_results.append(result)
            for entry in result.answer_entries:
                answer_entries.append(dict(entry))
        sections_out.append(
            assemble_section(
                section_id=section.slot_id,
                title=_section_title(section, teaching_plan=teaching_plan),
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
        answer_entries=answer_entries or None,
        writer_results=writer_results if not answer_entries else None,
    )
    before_hash = canonical_document_sha256(document)
    await repo.persist_document_candidate(
        document,
        document_sha256=before_hash,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
    )

    async with async_session_factory() as fresh:
        gen2 = await fresh.get(GenerationModel, generation_id)
        if gen2 is None:
            raise KeyError(generation_id)
        reloaded = reload_document(gen2.document_json)
        errors = validate_document(reloaded)
        if errors:
            raise AssemblyError(f"fresh-session validation failed: {errors[:5]}")
        after_hash = canonical_document_sha256(reloaded)
        if after_hash != before_hash:
            raise AssemblyError("fresh-session hash mismatch")

    pending_visuals = any(
        str((expected[key] or {}).get("status") or "") == "visual_pending"
        for key in expected_keys
    )
    await repo.finalize_verified_document(
        expected_document_sha256=before_hash,
        reloaded_sha256=after_hash,
        pending_visuals=pending_visuals,
        worker_id=lease.worker_id,
        lease_token=lease.lease_token,
    )
    terminal = "awaiting_visuals" if pending_visuals else "ready"
    return {
        "document": document,
        "terminal": terminal,
        "writer_count": len(expected_keys),
        "document_sha256": before_hash,
        "reloaded_sha256": after_hash,
    }


async def execute_after_teaching_approval(
    *,
    session: AsyncSession,
    generation_id: str,
    packet: ImmutableLessonPacket | None = None,
    teaching_plan: TeachingPlan | None = None,
    worker_id: str | None = None,
    lease: ExecutionLease | None = None,
) -> dict[str, Any]:
    """Resume-safe form plan → write blocks → assemble from DB."""
    if lease is None and worker_id is not None:
        # Reconstruct lease token from current execution metadata.
        repo0 = PageDocumentRepository(session, generation_id)
        state0 = await repo0.load_page_generation_state()
        execution = state0.get("execution") or {}
        lease = ExecutionLease(
            generation_id=generation_id,
            worker_id=worker_id,
            lease_token=int(execution.get("lease_token") or 0),
            stage=str((await session.get(GenerationModel, generation_id)).status or ""),
        )

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
    wid = lease.worker_id if lease else None
    ltok = lease.lease_token if lease else None
    if current == "queued":
        await repo.transition(
            expected={"queued"},
            target="planning_forms",
            event="form_plan_started",
            worker_id=wid,
            lease_token=ltok,
        )

    form_plan_raw = state.get("form_plan")
    form_plan: FormPlan | None = None
    legality: LessonLegalitySnapshot | None = None
    try:
        legality_raw = await repo.load_lesson_legality()
        legality = LessonLegalitySnapshot.model_validate(legality_raw)
    except LessonLegalityError:
        legality = None

    if teaching_plan is None:
        raise RuntimeError("teaching_plan required for form execution and assembly")

    if isinstance(form_plan_raw, dict) and legality is not None:
        try:
            candidate = coerce_form_plan(form_plan_raw)
            form_proj = project_form_guidance(
                permitted_object_ids=set(legality.permitted_objects)
            )
            candidate_map = build_form_candidate_map(
                teaching_plan,
                form_guidance=form_proj,
                permitted_object_ids=set(legality.permitted_objects),
            )
            revalidation = validate_form_plan(
                candidate, teaching_plan, candidate_map=candidate_map
            )
            if revalidation.ok:
                form_plan = candidate
                await repo.append_event(
                    make_event(
                        "form_plan_reused",
                        generation_id=generation_id,
                        status="ready",
                    ),
                    worker_id=wid,
                    lease_token=ltok,
                )
        except Exception:  # noqa: BLE001
            form_plan = None

    if form_plan is None:
        await repo.append_event(
            make_event("form_plan_started", generation_id=generation_id, status="started"),
            worker_id=wid,
            lease_token=ltok,
        )
        if legality is None:
            error = {
                "type": "LessonLegalityError",
                "code": "LESSON_LEGALITY_MISSING",
                "message": "lesson_legality snapshot missing; cannot plan forms",
                "stage": "planning_forms",
                "retryable": False,
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            await repo.transition(
                expected={"planning_forms"},
                target="failed_terminal",
                event="form_plan_failed",
                error=error,
                worker_id=wid,
                lease_token=ltok,
            )
            if lease is not None:
                await repo.release_execution(
                    worker_id=lease.worker_id, lease_token=lease.lease_token
                )
            return {"status": "failed_terminal", "error": error}
        try:
            form_result = await run_form_planner(
                packet,
                teaching_plan,
                legality=legality,
                generation_id=generation_id,
            )
        except NoLegalFormCandidatesError as exc:
            error = {
                "type": "NoLegalFormCandidatesError",
                "code": exc.code,
                "message": str(exc),
                "stage": "planning_forms",
                "block_ids": exc.block_ids,
                "retryable": False,
                "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            await repo.transition(
                expected={"planning_forms"},
                target="failed_terminal",
                event="form_plan_failed",
                error=error,
                worker_id=wid,
                lease_token=ltok,
            )
            if lease is not None:
                await repo.release_execution(
                    worker_id=lease.worker_id, lease_token=lease.lease_token
                )
            return {"status": "failed_terminal", "error": error}
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
                worker_id=wid,
                lease_token=ltok,
            )
            if lease is not None:
                await repo.release_execution(
                    worker_id=lease.worker_id, lease_token=lease.lease_token
                )
            return {"status": "failed_recoverable", "error": error}
        await repo.save_form_plan(
            plan=form_result.plan.model_dump(mode="json"),
            validation=form_result.validation.to_dict(),
            qc=form_result.qc,
            prompt=form_result.prompt,
            raw=form_result.raw_response,
            worker_id=wid,
            lease_token=ltok,
        )
        form_plan = form_result.plan
        await repo.append_event(
            make_event("form_plan_ready", generation_id=generation_id, status="ready"),
            worker_id=wid,
            lease_token=ltok,
        )

    generation = await session.get(GenerationModel, generation_id)
    if generation and generation.status == "planning_forms":
        await repo.transition(
            expected={"planning_forms"},
            target="writing_sections",
            event="writing_sections_started",
            worker_id=wid,
            lease_token=ltok,
        )

    write_outcomes = await write_form_blocks(
        generation_id=generation_id,
        form_plan=form_plan,
        packet=packet,
        teaching_plan=teaching_plan,
        lease=lease,
    )
    if any(o.get("status") == "lease_lost" for o in write_outcomes):
        return {"status": "lease_lost"}

    async with async_session_factory() as check_session:
        check_repo = PageDocumentRepository(check_session, generation_id)
        expected = await check_repo.load_expected_writer_results(
            form_plan=form_plan.model_dump(mode="json")
        )
    retryable = [
        key
        for key, outcome in expected.items()
        if str((outcome or {}).get("status") or "")
        in {"failed_recoverable", "failed", "started", ""}
    ]
    terminal_failed = [
        key
        for key, outcome in expected.items()
        if str((outcome or {}).get("status") or "") == "failed_terminal"
    ]
    writing_expected = set(WRITING_STATUSES) | {"assembling"}
    if terminal_failed:
        async with async_session_factory() as s:
            r = PageDocumentRepository(s, generation_id)
            await r.transition(
                expected=writing_expected,
                target="failed_terminal",
                event="writing_failed_terminal",
                error={
                    "type": "WriterError",
                    "code": "TERMINAL_BLOCK_FAILURE",
                    "message": f"terminal failures: {terminal_failed}",
                    "stage": "writing_sections",
                    "retryable": False,
                    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                worker_id=wid,
                lease_token=ltok,
            )
            if lease is not None:
                await r.release_execution(
                    worker_id=lease.worker_id, lease_token=lease.lease_token
                )
        return {"status": "failed_terminal", "failed": terminal_failed}
    if retryable:
        async with async_session_factory() as s:
            r = PageDocumentRepository(s, generation_id)
            await r.transition(
                expected=writing_expected,
                target="failed_recoverable",
                event="writing_failed_recoverable",
                error={
                    "type": "WriterError",
                    "code": "RETRYABLE_BLOCK_FAILURE",
                    "message": f"retryable failures: {retryable}",
                    "stage": "writing_sections",
                    "retryable": True,
                    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                worker_id=wid,
                lease_token=ltok,
            )
            if lease is not None:
                await r.release_execution(
                    worker_id=lease.worker_id, lease_token=lease.lease_token
                )
        return {"status": "failed_recoverable", "failed": retryable}

    async with async_session_factory() as s:
        r = PageDocumentRepository(s, generation_id)
        generation = await s.get(GenerationModel, generation_id)
        if generation and generation.status in WRITING_STATUSES:
            await r.transition(
                expected=set(WRITING_STATUSES),
                target="assembling",
                event="document_assembling",
                worker_id=wid,
                lease_token=ltok,
            )
        assembled = await assemble_from_db(
            session=s,
            generation_id=generation_id,
            packet=packet,
            form_plan=form_plan,
            teaching_plan=teaching_plan,
            lease=lease,
        )
        if lease is not None:
            await r.release_execution(
                worker_id=lease.worker_id, lease_token=lease.lease_token
            )
        return {
            "status": assembled["terminal"],
            "form_plan": form_plan.model_dump(mode="json"),
            "document": assembled["document"],
            "writer_count": assembled["writer_count"],
            "document_sha256": assembled.get("document_sha256"),
        }

"""Native item generation and teaching-plan halt.

Moved out of the legacy Studio router. Chunked HTTP adapters may still call
these functions while `/api/v1/v3` remains the compatibility URL.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LessonProvenanceModel,
    PackItemModel,
)
from core.database.session import async_session_factory
from curriculum.items.generator import ItemGenerationResult
from curriculum.planning.models import (
    ConceptCard,
    Misconception,
    VariantSpec,
    adapt_legacy_structural_plan,
)
from curriculum.planning.persistence import (
    append_item_attempt_records,
    load_chunked_state,
    persist_chunked_state,
)
from print.http.v3_studio.dtos import (
    V3ChunkedPlanStateDTO,
    V3ChunkedStatusDTO,
    V3InputForm,
    V3SignalSummary,
)
from print.http.v3_studio.generation_writer import V3GenerationWriter
from print.http.v3_studio.session_store import v3_studio_store

logger = logging.getLogger(__name__)

_chunked_stage2_tasks: dict[str, asyncio.Task[None]] = {}


def _render_chunked_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _normalize_chunked_state(generation_id: str, state: dict[str, Any]) -> V3ChunkedPlanStateDTO:
    next_action: str | None = None
    stage = str(state.get("stage") or "unknown")
    context = state.get("context")
    signals = context.get("signals") if isinstance(context, dict) else None
    form = context.get("form") if isinstance(context, dict) else None
    display_title = state.get("display_title")
    if not isinstance(display_title, str) or not display_title.strip():
        display_title = form.get("topic") if isinstance(form, dict) else None
    if stage in {"awaiting_review", "plan_ready"}:
        next_action = "approve_or_regenerate"
    elif stage == "stage2_running":
        next_action = "wait_for_stage2"
    elif stage == "variants_running":
        next_action = "wait_for_variants"
    elif stage == "assembly_blocked":
        next_action = "retry_failed_sections"
    elif stage == "stage2_error":
        next_action = "resume_stage2"
    elif stage == "blueprint_ready":
        next_action = "generation_running"
    elif stage == "complete":
        next_action = "done"

    return V3ChunkedPlanStateDTO(
        generation_id=generation_id,
        pack_id=state.get("pack_id") if isinstance(state.get("pack_id"), str) else None,
        stage=stage,
        structural_plan=state.get("structural_plan")
        if isinstance(state.get("structural_plan"), dict)
        else None,
        section_briefs=state.get("section_briefs")
        if isinstance(state.get("section_briefs"), dict)
        else {},
        failed_sections=[
            str(section)
            for section in state.get("failed_sections", [])
            if isinstance(section, str)
        ]
        if isinstance(state.get("failed_sections"), list)
        else [],
        blueprint_id=state.get("blueprint_id")
        if isinstance(state.get("blueprint_id"), str)
        else None,
        execution_started=bool(state.get("execution_started") is True),
        next_action=next_action,
        display_title=display_title.strip() if isinstance(display_title, str) else None,
        error=state.get("error") if isinstance(state.get("error"), str) else None,
        error_type=state.get("error_type") if isinstance(state.get("error_type"), str) else None,
        inferred_lesson_mode=signals.get("inferred_lesson_mode")
        if isinstance(signals, dict) and isinstance(signals.get("inferred_lesson_mode"), str)
        else None,
        lesson_mode_confidence=signals.get("lesson_mode_confidence")
        if isinstance(signals, dict) and isinstance(signals.get("lesson_mode_confidence"), str)
        else None,
        variants=state.get("variants") if isinstance(state.get("variants"), list) else [],
        variant_generation_ids=state.get("variant_generation_ids")
        if isinstance(state.get("variant_generation_ids"), dict)
        else {},
        requested_realization_path=(
            state.get("requested_realization_path")
            if state.get("requested_realization_path") in {"learn", "print"}
            else None
        ),
    )

def _normalize_chunked_status(
    generation_id: str,
    state: dict[str, Any],
    document_json: Any,
    *,
    generation_status: str | None = None,
) -> V3ChunkedStatusDTO:
    from print.generation.whole_lesson.native_status import project_native_status

    full_state = _normalize_chunked_state(generation_id, state)
    progress = document_json.get("progress") if isinstance(document_json, dict) else None
    doc_version = progress.get("updated_at") if isinstance(progress, dict) else None
    if not isinstance(doc_version, str) and isinstance(document_json, dict):
        canonical = json.dumps(document_json, sort_keys=True, separators=(",", ":"), default=str)
        doc_version = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"

    native = project_native_status(
        generation_id,
        state,
        document_json,
        generation_status=generation_status,
    )
    if native is not None:
        # Prefer monotonic document_revision so pollers see streaming/visual patches.
        revision = native.get("document_revision")
        if revision is not None:
            doc_version = f"rev:{int(revision)}"
        failed_sections = list(native.get("failed_section_ids") or full_state.failed_sections)
        return V3ChunkedStatusDTO(
            generation_id=generation_id,
            pack_id=full_state.pack_id,
            stage=str(native.get("stage") or full_state.stage),
            doc_version=doc_version if isinstance(doc_version, str) else None,
            failed_sections=failed_sections,
            blueprint_id=full_state.blueprint_id,
            execution_started=bool(native.get("execution_started", full_state.execution_started)),
            next_action=native.get("next_action"),
            error=native.get("error") if isinstance(native.get("error"), str) else full_state.error,
            error_type=native.get("error_type")
            if isinstance(native.get("error_type"), str)
            else full_state.error_type,
            variant_generation_ids=full_state.variant_generation_ids,
            requested_realization_path=full_state.requested_realization_path,
            document_version=native.get("document_version"),
            document_exists=bool(native.get("document_exists")),
            sections_total=int(native.get("sections_total") or 0),
            sections_ready=int(native.get("sections_ready") or 0),
            sections_failed=int(native.get("sections_failed") or 0),
            blocks_total=int(native.get("blocks_total") or 0),
            blocks_ready=int(native.get("blocks_ready") or 0),
            blocks_failed=int(native.get("blocks_failed") or 0),
            failed_section_ids=list(native.get("failed_section_ids") or []),
            failed_block_ids=list(native.get("failed_block_ids") or []),
            error_detail=native.get("error_detail")
            if isinstance(native.get("error_detail"), dict)
            else None,
            visual_quality=native.get("visual_quality")
            if isinstance(native.get("visual_quality"), dict)
            else {},
        )

    return V3ChunkedStatusDTO(
        generation_id=generation_id,
        pack_id=full_state.pack_id,
        stage=full_state.stage,
        doc_version=doc_version if isinstance(doc_version, str) else None,
        failed_sections=full_state.failed_sections,
        blueprint_id=full_state.blueprint_id,
        execution_started=full_state.execution_started,
        next_action=full_state.next_action,
        error=full_state.error,
        error_type=full_state.error_type,
        variant_generation_ids=full_state.variant_generation_ids,
        requested_realization_path=full_state.requested_realization_path,
    )

async def _chunked_emit_event(generation_id: str, event: str, payload: dict[str, Any]) -> None:
    queue = await v3_studio_store.get_chunked_queue(generation_id)
    if queue is None:
        return
    await queue.put(_render_chunked_sse(event, payload))

async def _load_owned_generation(
    generation_id: str,
    user_id: str,
) -> GenerationModel:
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        if model is None or model.user_id != user_id:
            raise HTTPException(status_code=404, detail="Generation not found")
        return model

def _contract_version_for_generation(
    model: GenerationModel,
    state: dict[str, Any],
) -> int:
    """Return the strongest persisted document contract declaration."""
    versions: list[int] = []
    plan = state.get("structural_plan")
    if isinstance(plan, dict):
        try:
            versions.append(int(plan.get("document_contract_version") or 1))
        except (TypeError, ValueError):
            pass
    if isinstance(model.planning_spec_json, str) and model.planning_spec_json.strip():
        try:
            spec = json.loads(model.planning_spec_json)
        except (TypeError, ValueError):
            spec = None
        if isinstance(spec, dict):
            try:
                versions.append(int(spec.get("document_contract_version") or 1))
            except (TypeError, ValueError):
                pass
    return max(versions, default=1)

async def _require_current_native_generation(
    generation_id: str,
    user_id: str,
    *,
    state: dict[str, Any] | None = None,
) -> tuple[GenerationModel, dict[str, Any], LessonProvenanceModel]:
    """Authorize current path approval before any task/state mutation.

    Current product approval is intentionally stricter than the historical
    native-routing heuristic: the persisted contract must be v2, the state must
    carry native provenance, and the immutable path provenance row must identify
    both the path version and path lesson.  Older v1 records remain readable but
    cannot enter new execution.
    """
    model = await _load_owned_generation(generation_id, user_id)
    resolved_state = state if state is not None else await load_chunked_state(generation_id)
    contract_version = _contract_version_for_generation(model, resolved_state)
    context = resolved_state.get("context")
    native_state = bool(
        resolved_state.get("native_whole_lesson")
        or (context.get("native_whole_lesson") if isinstance(context, dict) else False)
        or resolved_state.get("page_document_v2")
    )
    shared_preparation = bool(
        resolved_state.get("shared_preparation")
        or (context.get("shared_preparation") if isinstance(context, dict) else False)
        or resolved_state.get("path_prepared")
    )
    async with async_session_factory() as session:
        provenance = await session.get(LessonProvenanceModel, generation_id)
    has_path_provenance = bool(
        provenance is not None
        and provenance.path_version_id
        and provenance.path_lesson_id
    )
    # Print-native v2 generations keep the historical gate. Unit shared
    # preparation (P02) intentionally persists document_contract_version=1
    # until a path consumer admits a native realization; those rows must still
    # pass with immutable path provenance so teaching can run.
    allowed = has_path_provenance and (
        (contract_version >= 2 and native_state)
        or shared_preparation
    )
    if not allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                "Current lesson approval requires native document contract v2 "
                "and immutable path provenance"
            ),
        )
    return model, resolved_state, provenance

def _decode_chunked_context(
    state: dict[str, Any],
) -> tuple[V3SignalSummary, V3InputForm, dict[str, Any]]:
    context = state.get("context")
    if not isinstance(context, dict):
        raise TypeError("Chunked context is missing.")
    signals_raw = context.get("signals")
    form_raw = context.get("form")
    resource_spec = context.get("resource_spec")
    if not isinstance(signals_raw, dict) or not isinstance(form_raw, dict):
        raise TypeError("Chunked context is incomplete.")
    if not isinstance(resource_spec, dict):
        raise TypeError("Chunked resource_spec is missing.")
    return (
        V3SignalSummary.model_validate(signals_raw),
        V3InputForm.model_validate(form_raw),
        resource_spec,
    )

async def _generate_shared_pack_items(
    *,
    generation_id: str,
    form: V3InputForm,
    plan: StructuralPlan,
    worker_id: str | None = None,
    lease_token: int | None = None,
) -> dict[str, Any]:
    """Generate the pack's single diagnostic set from approved cards alone."""
    from curriculum.items.generator import (
        ITEM_MAX_ATTEMPTS,
        execute_items_with_diagnostics,
    )

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise ValueError(f"Generation '{generation_id}' not found")
        pack_id = generation.pack_id or generation.id
        rows = await session.execute(
            select(ConceptCardModel)
            .where(ConceptCardModel.pack_id == pack_id)
            .order_by(ConceptCardModel.created_at, ConceptCardModel.id)
        )
        cards = list(rows.scalars())

        existing_rows = await session.execute(
            select(PackItemModel).where(PackItemModel.pack_id == pack_id)
        )
        item_rows = list(existing_rows.scalars())
        ready_card_ids = {
            card.id
            for card in cards
            if len(
                [
                    item
                    for item in item_rows
                    if item.card_id == card.id and not item.stale
                ]
            )
            == 5
        }

    notation = plan.variant_spec().voice.notation
    pending_cards = [row for row in cards if row.id not in ready_card_ids]
    results: list[ItemGenerationResult] = []
    attempts_journal: list[dict[str, Any]] = []
    failed_cards: list[dict[str, Any]] = []
    flushed_attempt_keys: set[tuple[str, str, int]] = set()

    async def _flush_attempts(
        *,
        new_attempts: list[dict[str, Any]] | None = None,
        new_failed: list[dict[str, Any]] | None = None,
    ) -> None:
        batch = list(new_attempts or [])
        pending = [
            dict(row)
            for row in attempts_journal
            if (
                str(row.get("correlation_id") or ""),
                str(row.get("card_id") or ""),
                int(row.get("attempt") or 0),
            )
            not in flushed_attempt_keys
        ]
        to_write = batch + pending
        if not to_write and not new_failed:
            return
        await append_item_attempt_records(
            generation_id,
            attempts=to_write,
            failed_cards=new_failed,
            pack_id=pack_id,
            worker_id=worker_id,
            lease_token=lease_token,
        )
        for row in to_write:
            flushed_attempt_keys.add(
                (
                    str(row.get("correlation_id") or ""),
                    str(row.get("card_id") or ""),
                    int(row.get("attempt") or 0),
                )
            )

    async def _one(row: ConceptCardModel) -> None:
        card = _approved_card_for_items(
            row,
            subject=form.subject,
            level=form.grade_level,
            notation=notation,
        )
        try:
            run = await execute_items_with_diagnostics(
                card,
                generation_id=generation_id,
                max_attempts=ITEM_MAX_ATTEMPTS,
            )
            results.append(run.result)
            attempts_journal.extend(run.attempts)
            await _flush_attempts(new_attempts=list(run.attempts))
        except Exception as exc:
            journal = list(getattr(exc, "item_attempts", []) or [])
            attempts_journal.extend(journal)
            failed_row = {
                "card_id": row.id,
                "correlation_id": getattr(exc, "item_correlation_id", None),
                "error": str(exc)[:500],
                "attempts": journal,
            }
            failed_cards.append(failed_row)
            await _flush_attempts(new_attempts=journal, new_failed=[failed_row])
            raise

    try:
        if pending_cards:
            await asyncio.gather(*(_one(row) for row in pending_cards))
    finally:
        await _flush_attempts()

    if results:
        await _persist_item_results(
            pack_id,
            results,
            generation_id=generation_id,
            worker_id=worker_id,
            lease_token=lease_token,
        )

    review_cards = [
        {
            "card_id": result.card_id,
            "missing_misconceptions": list(result.missing_misconceptions),
            "unmapped_options": result.unmapped_options,
        }
        for result in results
        if result.needs_review or result.unmapped_options
    ]
    return {
        "pack_id": pack_id,
        "generated_card_count": len(results),
        "generated_item_count": sum(len(result.items) for result in results),
        "review_cards": review_cards,
        "attempts": attempts_journal,
        "failed_cards": failed_cards,
        "retry_budget": ITEM_MAX_ATTEMPTS,
    }

def _approved_card_for_items(
    row: ConceptCardModel,
    *,
    subject: str,
    level: str,
    notation: str | None,
) -> ConceptCard:
    misconceptions = [
        Misconception.model_validate(item)
        for item in (row.misconceptions or [])
        if isinstance(item, dict)
    ]
    return ConceptCard(
        id=row.id,
        title=row.title,
        objective=row.objective,
        prereqs=list(row.prereqs or []),
        misconceptions=misconceptions,
    ).with_item_context(
        subject=subject,
        level=level,
        notation=notation,
    )

def _item_row_teacher_edited(row: PackItemModel) -> bool:
    return any(
        isinstance(option, dict) and option.get("teacher_edited") is True
        for option in (row.options or [])
    )

async def _persist_item_results(
    pack_id: str,
    results: list[ItemGenerationResult],
    *,
    generation_id: str | None = None,
    worker_id: str | None = None,
    lease_token: int | None = None,
) -> None:
    leased = worker_id is not None or lease_token is not None
    if leased and (generation_id is None or worker_id is None or lease_token is None):
        raise ValueError(
            "generation_id, worker_id, and lease_token are required for leased PackItem writes"
        )

    async with async_session_factory() as session:
        if leased:
            from print.generation.whole_lesson.repository import (
                PageDocumentRepository,
                _page_state_lock,
            )

            lock = await _page_state_lock(str(generation_id))
            async with lock:
                repo = PageDocumentRepository(session, str(generation_id))
                await repo.require_execution_lease(
                    worker_id=str(worker_id),
                    lease_token=int(lease_token),
                )
                await _write_pack_item_rows(session, pack_id, results)
                await session.commit()
            return

        await _write_pack_item_rows(session, pack_id, results)
        await session.commit()

async def _write_pack_item_rows(
    session: AsyncSession,
    pack_id: str,
    results: list[ItemGenerationResult],
) -> None:
    for result in results:
        stored = await session.execute(
            select(PackItemModel).where(
                PackItemModel.pack_id == pack_id,
                PackItemModel.card_id == result.card_id,
            )
        )
        existing_rows = {row.id: row for row in stored.scalars()}
        generated_ids: set[str] = set()
        for item in result.items:
            correct = next(option for option in item.options if option.correct)
            db_id = f"{pack_id}:{item.question_id}"
            generated_ids.add(db_id)
            existing = existing_rows.get(db_id)
            if existing is not None and _item_row_teacher_edited(existing):
                existing.stale = True
                continue
            payload = {
                "stem": item.prompt_text,
                "options": [
                    {
                        **option.model_dump(mode="json"),
                        "teacher_edited": False,
                    }
                    for option in item.options
                ],
                "correct_key": correct.key,
                "diagnoses": {
                    option.key: option.diagnoses
                    for option in item.options
                },
                "stale": False,
            }
            if existing is None:
                session.add(
                    PackItemModel(
                        id=db_id,
                        pack_id=pack_id,
                        card_id=result.card_id,
                        **payload,
                    )
                )
            else:
                for field, value in payload.items():
                    setattr(existing, field, value)

        for db_id, existing in existing_rows.items():
            if db_id in generated_ids:
                continue
            if _item_row_teacher_edited(existing):
                existing.stale = True
            else:
                await session.delete(existing)

async def _run_chunked_stage2_pipeline(
    *,
    generation_id: str,
    user_id: str,
) -> None:
    async def emit_event(event: str, payload: dict[str, Any]) -> None:
        await _chunked_emit_event(generation_id, event, payload)

    print(
        f"\n[STAGE2 PIPELINE START] generation_id={generation_id}",
        flush=True,
    )
    cache_token = None
    native_failure_stage = "item_generation"
    try:
        from core.prompts import (
            bind_prompt_cache,
            reset_prompt_cache,
            resolve_all_prompts,
        )

        async with async_session_factory() as session:
            prompt_texts, prompt_hashes = await resolve_all_prompts(user_id, session)
        cache_token = bind_prompt_cache(prompt_texts)
        try:
            writer = V3GenerationWriter(async_session_factory)
            await writer.record_prompt_hashes(generation_id, prompt_hashes)
        except Exception:
            logger.exception(
                "Failed to stamp prompt hashes generation_id=%s", generation_id
            )

        state = await load_chunked_state(generation_id)
        plan_raw = state.get("structural_plan")
        if not isinstance(plan_raw, dict):
            await persist_chunked_state(
                generation_id,
                {"stage": "assembly_blocked", "failed_sections": []},
            )
            await emit_event(
                "generation_warning",
                {
                    "generation_id": generation_id,
                    "message": "No structural plan found for this chunked generation.",
                },
            )
            return

        plan = adapt_legacy_structural_plan(
            plan_raw,
            source=f"generation:{generation_id}",
        )
        variant_raw = state.get("variant_spec")
        if isinstance(variant_raw, dict):
            plan = plan.with_variant(VariantSpec.model_validate(variant_raw))
        _signals, form, _resource_spec = _decode_chunked_context(state)
        display_title = state.get("display_title")
        if not isinstance(display_title, str) or not display_title.strip():
            display_title = form.topic

        async def _items_job() -> dict[str, Any] | None:
            if state.get("skip_item_generation"):
                return None
            item_summary = await _generate_shared_pack_items(
                generation_id=generation_id,
                form=form,
                plan=plan,
            )
            await persist_chunked_state(
                generation_id,
                {"item_generation": item_summary},
            )
            await emit_event(
                "pack_items_ready",
                {
                    "generation_id": generation_id,
                    **item_summary,
                },
            )
            return item_summary

        # Native whole-lesson path: items → teaching plan → halt for teacher approval.
        # Do not run legacy section briefs, assembly, or component writers.
        # Unit shared preparation (P02) also uses this teaching halt even though
        # document_contract_version stays 1 until a Print realization upgrades it.
        from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson

        native_whole_lesson = generation_is_native_whole_lesson(state) or (
            int(getattr(plan, "document_contract_version", 1) or 1) >= 2
        )
        shared_unit_prep = bool(
            state.get("shared_preparation")
            or state.get("path_prepared")
            or (
                isinstance(state.get("context"), dict)
                and state["context"].get("shared_preparation")
            )
        )
        if native_whole_lesson or shared_unit_prep:
            await _items_job()
            native_failure_stage = "planning_teaching"
            from print.generation.whole_lesson.service import run_and_persist_teaching_plan

            async with async_session_factory() as session:
                teaching_summary = await run_and_persist_teaching_plan(
                    session, generation_id, require_items=True
                )
            await persist_chunked_state(
                generation_id,
                {
                    "stage": "awaiting_teaching_approval",
                    "native_whole_lesson": True,
                    "shared_preparation": True if shared_unit_prep else state.get("shared_preparation"),
                    "teaching_plan_summary": {
                        "arc": (teaching_summary.get("teaching_plan") or {}).get("arc"),
                        "section_count": len(
                            (teaching_summary.get("teaching_plan") or {}).get("sections")
                            or []
                        ),
                    },
                },
            )
            await emit_event(
                "awaiting_teaching_approval",
                {
                    "generation_id": generation_id,
                    "arc": (teaching_summary.get("teaching_plan") or {}).get("arc"),
                },
            )
            print(
                f"\n[STAGE2 NATIVE TEACHING HALT] generation_id={generation_id}",
                flush=True,
            )
            return

        # Phase 02 Commit F: legacy stage2 back half is disabled for new lessons.
        # Historical v1 documents remain readable; new work must use the native path.
        logger.error(
            "legacy resume_stage2 blocked for new generation generation_id=%s",
            generation_id,
        )
        await persist_chunked_state(
            generation_id,
            {
                "stage": "stage2_error",
                "error": "Legacy stage2 back half is disabled; use native whole-lesson path",
                "error_type": "LegacyBackHalfDisabled",
            },
        )
        await emit_event(
            "stage2_error",
            {
                "generation_id": generation_id,
                "error": "Legacy stage2 back half is disabled for new lessons",
            },
        )
        return
    except Exception as exc:
        import traceback

        print(
            f"\n[STAGE2 PIPELINE ERROR] generation_id={generation_id}"
            f" type={type(exc).__name__}"
            f"\nmessage={exc!s}"
            f"\n{traceback.format_exc()}",
            flush=True,
        )
        logger.exception(
            "chunked stage2 pipeline failed generation_id=%s",
            generation_id,
        )
        # Prefer native atomic failure sync when this generation is native whole-lesson.
        failure_state: dict[str, Any] = {}
        try:
            failure_state = await load_chunked_state(generation_id)
        except Exception:  # noqa: BLE001
            failure_state = {}
        from print.generation.whole_lesson.native_routing import generation_is_native_whole_lesson
        from print.generation.whole_lesson.repository import persist_native_failure_for_generation

        is_native = generation_is_native_whole_lesson(failure_state) or bool(
            failure_state.get("page_document_v2")
            or (failure_state.get("context") or {}).get("native_whole_lesson")
        )
        if is_native:
            stage_name = native_failure_stage
            await persist_native_failure_for_generation(
                generation_id,
                exc=exc,
                stage=str(stage_name),
                event="pre_worker_failure",
            )
            await _chunked_emit_event(
                generation_id,
                "native_failure",
                {
                    "generation_id": generation_id,
                    "stage": str(stage_name),
                    "message": str(exc)[:400],
                },
            )
        else:
            await persist_chunked_state(
                generation_id,
                {
                    "stage": "stage2_error",
                    "execution_started": False,
                    "error": str(exc)[:400],
                    "error_type": type(exc).__name__,
                },
            )
            await _chunked_emit_event(
                generation_id,
                "generation_warning",
                {
                    "generation_id": generation_id,
                    "message": "Chunked expansion failed. Retry a failed section or regenerate the plan.",
                },
            )
    finally:
        if cache_token is not None:
            from core.prompts import reset_prompt_cache

            reset_prompt_cache(cache_token)
        _chunked_stage2_tasks.pop(generation_id, None)
        print(
            f"\n[STAGE2 PIPELINE DONE] generation_id={generation_id}",
            flush=True,
        )


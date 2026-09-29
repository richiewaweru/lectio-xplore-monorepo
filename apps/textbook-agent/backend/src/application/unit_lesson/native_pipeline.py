"""Chunked-plan state normalisation and current-preparation authorisation.

Preparation stage 2 (per-card practice items + the V2 Teaching Plan) runs as a
``preparation`` Run on the shared generation runtime (Option D, 3A): see
``application.unit_lesson.preparation_runs`` / ``preparation_worker``.  What
remains here are the read-side helpers the chunked HTTP adapters still use
until the frontend reads lesson-status only (3B).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import HTTPException

from core.database.models import GenerationModel, LessonProvenanceModel
from core.database.session import async_session_factory
from curriculum.planning.persistence import load_chunked_state
from print.http.v3_studio.dtos import V3ChunkedPlanStateDTO, V3ChunkedStatusDTO

logger = logging.getLogger(__name__)


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

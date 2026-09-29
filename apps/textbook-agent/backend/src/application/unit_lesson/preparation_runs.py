"""Preparation Runs: plan generation on the shared generation runtime (Option D, 3A).

Stage 1 (structural planning, synchronous in ``:prepare``) and the structural
review are unchanged.  When the teacher approves the structure, this module
admits a ``preparation`` Run:

* source identity: ``lesson_structural_plan`` = the prep generation id, pinned to
  ``path_lesson_revision`` and a canonical hash of the structural plan, its
  context, ``planning_spec_json`` and the objective hash;
* one ``items:{concept_card_id}`` work item per concept card (the worker admits
  the ``teaching_plan`` item after every card is ready);
* one Build for the path lesson, reused by the SharedDocument Run admitted after
  the teacher approves the plan (one timeline).

Admission is idempotent.  ``regenerate`` admits a new bounded attempt for a
failed-terminal / cancelled Run or a rejected plan.  Teacher approval is not a
job: "awaiting approval" is ``run ready and teaching_review.status == pending``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from curriculum.planning.persistence import load_chunked_state, persist_chunked_state
from curriculum.workspace_projection import PreparationRunView
from infra.database.models import GenerationRunModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    AdmissionResult,
    AttemptLimitExceeded,
    BuildAdmission,
    InvalidWorkItemTransition,
    RunAdmission,
    RunAdmissionConflict,
    RunType,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemConflict,
    active_work_items,
    add_work_item,
    admit_run,
    create_build,
    retry_work_items,
)

PREPARATION_STAGE = "preparation"
ITEMS_ITEM_STAGE = "item_generation"
TEACHING_ITEM_STAGE = "planning_teaching"
ITEMS_KEY_PREFIX = "items:"
TEACHING_ITEM_KEY = "teaching_plan"
SOURCE_ARTIFACT_TYPE = "lesson_structural_plan"
PLAN_ARTIFACT_TYPE = "teaching_plan_revision"
MAX_ATTEMPTS = 3
DEFINITION_VERSION = "preparation-v1"

# Same precondition the retired chunked approve used.
APPROVABLE_STAGES = frozenset({"awaiting_review", "plan_ready", "stage2_error", "assembly_blocked"})
_TERMINAL_RUN_STATUSES = frozenset({"failed_terminal", "cancelled"})


class PreparationRunError(Exception):
    """Expected admission/retry refusal; ``status_code`` maps to HTTP."""

    def __init__(self, message: str, *, code: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class PreparationAdmission:
    run: GenerationRunModel
    created: bool
    attempt: int


@dataclass(frozen=True)
class _Context:
    generation: GenerationModel
    provenance: LessonProvenanceModel
    lesson: PathLessonModel
    state: dict[str, Any]


def item_key(card_id: str) -> str:
    return f"{ITEMS_KEY_PREFIX}{card_id}"


def preparation_request_key(generation_id: str, source_hash: str, attempt: int = 1) -> str:
    base = f"preparation:{generation_id}:{source_hash}"
    return base if attempt <= 1 else f"{base}:attempt-{attempt}"


def source_hash_for(
    *,
    structural_plan: Any,
    context: Any,
    planning_spec_json: Any,
    objective_hash: Any,
) -> str:
    return content_hash(
        {
            "structural_plan": structural_plan,
            "context": context,
            "planning_spec_json": planning_spec_json,
            "objective_hash": objective_hash,
        }
    )


def source_identity_from_rows(
    generation: GenerationModel,
    provenance: LessonProvenanceModel,
    state: dict[str, Any],
) -> SourceIdentity:
    plan = state.get("structural_plan")
    if not isinstance(plan, dict):
        raise PreparationRunError(
            "Structural plan is not ready yet", code="PREPARATION_STRUCTURE_MISSING"
        )
    return SourceIdentity(
        source_artifact_type=SOURCE_ARTIFACT_TYPE,
        source_artifact_id=str(generation.id),
        source_revision=int(provenance.path_lesson_revision or 1),
        source_hash=source_hash_for(
            structural_plan=plan,
            context=state.get("context"),
            planning_spec_json=generation.planning_spec_json,
            objective_hash=provenance.objective_hash,
        ),
    )


def run_source(run: GenerationRunModel) -> SourceIdentity:
    return SourceIdentity(
        source_artifact_type=run.source_artifact_type,
        source_artifact_id=run.source_artifact_id,
        source_revision=run.source_revision,
        source_hash=run.source_hash,
    )


async def load_current_source(
    session: AsyncSession, *, generation_id: str
) -> SourceIdentity:
    """Recompute the source identity from persisted rows (worker + verifier)."""
    generation = await session.get(GenerationModel, generation_id, populate_existing=True)
    provenance = await session.get(LessonProvenanceModel, generation_id, populate_existing=True)
    if generation is None or provenance is None:
        raise PreparationRunError("Preparation is unavailable", code="PREPARATION_NOT_FOUND")
    if provenance.invalidated_at is not None:
        raise PreparationRunError(
            "Preparation provenance is invalidated", code="PREPARATION_STALE"
        )
    state = await load_chunked_state(generation_id, session)
    return source_identity_from_rows(generation, provenance, state)


async def _lock_owner(session: AsyncSession, owner_user_id: str) -> None:
    """Serialize concurrent admissions for one owner (SQLite ignores FOR UPDATE)."""
    if session.get_bind().dialect.name == "sqlite":
        await session.execute(
            update(UserModel)
            .where(UserModel.id == owner_user_id)
            .values(created_at=UserModel.created_at)
        )
    else:
        await session.scalar(
            select(UserModel.id).where(UserModel.id == owner_user_id).with_for_update()
        )


async def _load_context(
    session: AsyncSession, *, generation_id: str, owner_user_id: str
) -> _Context:
    generation = await session.get(GenerationModel, generation_id, populate_existing=True)
    if generation is None or generation.user_id != owner_user_id:
        raise PreparationRunError(
            "Preparation not found", code="PREPARATION_NOT_FOUND", status_code=404
        )
    provenance = await session.get(LessonProvenanceModel, generation_id, populate_existing=True)
    if provenance is None or not provenance.path_lesson_id:
        raise PreparationRunError(
            "This generation is not a path-lesson preparation",
            code="PREPARATION_NOT_PATH_LESSON",
        )
    lesson = await session.scalar(
        select(PathLessonModel)
        .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
        .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
        .where(
            PathLessonModel.id == provenance.path_lesson_id,
            UnitModel.owner_id == owner_user_id,
        )
        .execution_options(populate_existing=True)
    )
    if lesson is None:
        raise PreparationRunError(
            "Preparation not found", code="PREPARATION_NOT_FOUND", status_code=404
        )
    if lesson.pack_id != generation_id:
        raise PreparationRunError(
            "This preparation is not the lesson's current preparation",
            code="PREPARATION_NOT_CURRENT",
        )
    if (
        provenance.invalidated_at is not None
        or provenance.objective_hash != lesson.objective_hash
        or provenance.path_lesson_revision not in {None, lesson.revision}
    ):
        raise PreparationRunError(
            "This preparation is stale; regenerate the lesson preparation",
            code="PREPARATION_STALE",
        )
    try:
        state = await load_chunked_state(generation_id, session)
    except ValueError as exc:
        raise PreparationRunError(
            "This preparation predates the resumable workflow; re-prepare the lesson",
            code="PREPARATION_LEGACY",
        ) from exc
    return _Context(generation=generation, provenance=provenance, lesson=lesson, state=state)


async def _runs_by_attempt(
    session: AsyncSession, *, owner_user_id: str, generation_id: str, source_hash: str
) -> list[tuple[int, GenerationRunModel]]:
    found: list[tuple[int, GenerationRunModel]] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        run = await session.scalar(
            select(GenerationRunModel)
            .options(selectinload(GenerationRunModel.work_items))
            .where(
                GenerationRunModel.owner_user_id == owner_user_id,
                GenerationRunModel.request_key
                == preparation_request_key(generation_id, source_hash, attempt),
            )
            .execution_options(populate_existing=True)
        )
        if run is not None:
            found.append((attempt, run))
    return found


async def latest_preparation_run(
    session: AsyncSession, *, generation_id: str, owner_user_id: str | None = None
) -> GenerationRunModel | None:
    """Most recently admitted preparation Run for a prep generation (any attempt)."""
    query = (
        select(GenerationRunModel)
        .options(selectinload(GenerationRunModel.work_items))
        .where(
            GenerationRunModel.run_type == RunType.PREPARATION.value,
            GenerationRunModel.source_artifact_type == SOURCE_ARTIFACT_TYPE,
            GenerationRunModel.source_artifact_id == generation_id,
        )
        .order_by(GenerationRunModel.created_at.desc(), GenerationRunModel.id.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if owner_user_id is not None:
        query = query.where(GenerationRunModel.owner_user_id == owner_user_id)
    return await session.scalar(query)


_RETRYABLE_ERROR_CLASSES = frozenset({"validation", "provider_transport", "provider_output"})


def preparation_run_view(run: GenerationRunModel) -> PreparationRunView:
    """Plain-data projection input for one preparation Run (work items loaded)."""
    items = active_work_items(tuple(run.work_items or ()))
    card_items = [i for i in items if i.item_key.startswith(ITEMS_KEY_PREFIX)]
    teaching = next((i for i in items if i.item_key == TEACHING_ITEM_KEY), None)
    failed = [i for i in items if i.status in {"failed_recoverable", "failed_terminal"}]
    retryable = (
        run.status == "failed_recoverable"
        and bool(failed)
        and all(
            i.status == "failed_recoverable"
            and i.recovery_action == "retry"
            and i.error_class in _RETRYABLE_ERROR_CLASSES
            and i.attempt < i.max_attempts
            for i in failed
        )
    )
    if teaching is None:
        teaching_state = "not_started"
    elif teaching.status in {"failed_recoverable", "failed_terminal"}:
        teaching_state = "failed"
    else:
        teaching_state = teaching.status
    error_code = run.error_code
    error_summary = run.error_summary
    if not (error_code or error_summary):
        for item in failed:
            if item.error_code or item.error_summary:
                error_code, error_summary = item.error_code, item.error_summary
                break
    return PreparationRunView(
        run_id=run.id,
        status=run.status,
        error_code=error_code,
        error_summary=error_summary,
        retryable=retryable,
        items_total=len(card_items),
        items_ready=sum(1 for i in card_items if i.status == "ready"),
        items_failed=sum(
            1 for i in card_items if i.status in {"failed_recoverable", "failed_terminal"}
        ),
        teaching_plan=teaching_state,
        failed_work_item_ids=tuple(i.id for i in failed),
    )


async def load_preparation_run_views(
    session: AsyncSession, *, generation_ids: list[str]
) -> dict[str, PreparationRunView]:
    """Latest preparation Run view per preparation generation id (one query)."""
    if not generation_ids:
        return {}
    runs = list(
        (
            await session.scalars(
                select(GenerationRunModel)
                .options(selectinload(GenerationRunModel.work_items))
                .where(
                    GenerationRunModel.run_type == RunType.PREPARATION.value,
                    GenerationRunModel.source_artifact_type == SOURCE_ARTIFACT_TYPE,
                    GenerationRunModel.source_artifact_id.in_(generation_ids),
                )
                .order_by(GenerationRunModel.created_at.asc(), GenerationRunModel.id.asc())
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    latest: dict[str, GenerationRunModel] = {}
    for run in runs:  # ascending: later rows overwrite earlier attempts
        latest[run.source_artifact_id] = run
    return {gid: preparation_run_view(run) for gid, run in latest.items()}


def _review_status(state: dict[str, Any]) -> str:
    page = state.get("page_document_v2")
    review = (page or {}).get("teaching_review") if isinstance(page, dict) else None
    return str((review or {}).get("status") or "").lower()


async def _add_card_items(
    session: AsyncSession,
    *,
    run: GenerationRunModel,
    generation: GenerationModel,
    source: SourceIdentity,
) -> int:
    pack_id = generation.pack_id or generation.id
    cards = list(
        (
            await session.scalars(
                select(ConceptCardModel)
                .where(ConceptCardModel.pack_id == pack_id)
                .order_by(ConceptCardModel.created_at, ConceptCardModel.id)
            )
        ).all()
    )
    if not cards:
        raise PreparationRunError(
            "This preparation has no concept cards", code="PREPARATION_NO_CARDS"
        )
    definition = content_hash({"definition": "preparation-items", "version": DEFINITION_VERSION})
    for card in cards:
        try:
            await add_work_item(
                session,
                WorkItemAdmission(
                    run_id=run.id,
                    item_key=item_key(card.id),
                    stage=ITEMS_ITEM_STAGE,
                    input_hash=content_hash(
                        {"card_id": card.id, "source_hash": source.source_hash}
                    ),
                    definition_hash=definition,
                ),
            )
        except WorkItemConflict as exc:  # pragma: no cover - identity is derived from source
            raise PreparationRunError(str(exc), code="PREPARATION_ITEM_CONFLICT") from exc
    return len(cards)


async def admit_preparation_run(
    session: AsyncSession,
    *,
    generation_id: str,
    owner_user_id: str,
    regenerate: bool = False,
    display_title: str | None = None,
) -> PreparationAdmission:
    """Admit (or return) the preparation Run.  Caller commits.

    ``regenerate=False``: idempotent; returns the latest existing attempt for
    the current source, otherwise admits attempt 1 (requires the structure to
    still be awaiting approval).  ``regenerate=True``: admits the next bounded
    attempt for a failed-terminal / cancelled Run or a rejected plan.
    """
    await _lock_owner(session, owner_user_id)
    ctx = await _load_context(
        session, generation_id=generation_id, owner_user_id=owner_user_id
    )
    source = source_identity_from_rows(ctx.generation, ctx.provenance, ctx.state)
    existing = await _runs_by_attempt(
        session,
        owner_user_id=owner_user_id,
        generation_id=generation_id,
        source_hash=source.source_hash,
    )

    if not regenerate:
        if existing:
            attempt, run = existing[-1]
            return PreparationAdmission(run=run, created=False, attempt=attempt)
        stage = str(ctx.state.get("stage") or "")
        if not (ctx.state.get("structure_review_open") is True or stage in APPROVABLE_STAGES):
            raise PreparationRunError(
                "Generation is not awaiting explicit approval",
                code="PREPARATION_NOT_AWAITING_APPROVAL",
            )
        attempt = 1
    else:
        if not existing:
            raise PreparationRunError(
                "No plan generation exists to regenerate", code="PREPARATION_NO_RUN"
            )
        last_attempt, last = existing[-1]
        rejected = last.status == "ready" and _review_status(ctx.state) == "rejected"
        if last.status not in _TERMINAL_RUN_STATUSES and not rejected:
            raise PreparationRunError(
                "Only a failed or rejected plan can be regenerated",
                code="PREPARATION_NOT_REGENERATABLE",
            )
        attempt = last_attempt + 1
        if attempt > MAX_ATTEMPTS:
            raise PreparationRunError(
                "Plan regeneration attempts are used up; re-prepare the lesson",
                code="PREPARATION_ATTEMPTS_EXHAUSTED",
            )

    from document.shared_lesson.run_admission import find_preparation_build_id

    build_id = await find_preparation_build_id(
        session,
        owner_user_id=owner_user_id,
        preparation_generation_id=generation_id,
        path_lesson_id=ctx.lesson.id,
    )
    if build_id is None:
        build_id = (
            await create_build(
                session,
                BuildAdmission(owner_user_id=owner_user_id, path_lesson_id=ctx.lesson.id),
            )
        ).id
    try:
        admission: AdmissionResult = await admit_run(
            session,
            RunAdmission(
                build_id=build_id,
                owner_user_id=owner_user_id,
                run_type=RunType.PREPARATION,
                request_key=preparation_request_key(generation_id, source.source_hash, attempt),
                stage=PREPARATION_STAGE,
                source_artifact_type=source.source_artifact_type,
                source_artifact_id=source.source_artifact_id,
                source_revision=source.source_revision,
                source_hash=source.source_hash,
            ),
        )
    except RunAdmissionConflict as exc:
        raise PreparationRunError(str(exc), code="PREPARATION_ADMISSION_CONFLICT") from exc
    run = admission.record
    assert isinstance(run, GenerationRunModel)
    await _add_card_items(session, run=run, generation=ctx.generation, source=source)

    patch: dict[str, Any] = {
        # Compatibility stamps for readers that predate Runs.  Nothing new reads
        # them for UI status; the Run is the status.
        "stage": "stage2_running",
        "execution_started": False,
        "structure_review_open": False,
    }
    if display_title and display_title.strip():
        patch["display_title"] = display_title.strip()
    await persist_chunked_state(generation_id, patch, session)
    refreshed = await latest_preparation_run(
        session, generation_id=generation_id, owner_user_id=owner_user_id
    )
    return PreparationAdmission(run=refreshed or run, created=admission.created, attempt=attempt)


async def retry_preparation_run(
    session: AsyncSession, *, generation_id: str, owner_user_id: str
) -> GenerationRunModel:
    """Reopen every retryable failed leaf of a failed_recoverable preparation Run."""
    generation = await session.get(GenerationModel, generation_id)
    if generation is None or generation.user_id != owner_user_id:
        raise PreparationRunError(
            "Preparation not found", code="PREPARATION_NOT_FOUND", status_code=404
        )
    run = await latest_preparation_run(
        session, generation_id=generation_id, owner_user_id=owner_user_id
    )
    if run is None:
        raise PreparationRunError(
            "This lesson was prepared before the planning update; re-prepare it",
            code="PREPARATION_LEGACY",
        )
    if run.status != "failed_recoverable":
        raise PreparationRunError(
            "Only a recoverable failure can be retried; regenerate the plan instead",
            code="PREPARATION_NOT_RETRYABLE",
        )
    failed = [
        item
        for item in active_work_items(tuple(run.work_items))
        if item.status == "failed_recoverable"
    ]
    if not failed or any(item.recovery_action != "retry" for item in failed):
        raise PreparationRunError(
            "This failure cannot be retried; regenerate the plan instead",
            code="PREPARATION_NOT_RETRYABLE",
        )
    try:
        async with session.begin_nested():
            await retry_work_items(
                session,
                run_id=run.id,
                work_item_ids=[item.id for item in failed],
                owner_user_id=owner_user_id,
            )
    except (InvalidWorkItemTransition, AttemptLimitExceeded, WorkItemConflict) as exc:
        raise PreparationRunError(
            "Retry attempts are used up; regenerate the plan instead",
            code="PREPARATION_NOT_RETRYABLE",
        ) from exc
    refreshed = await latest_preparation_run(
        session, generation_id=generation_id, owner_user_id=owner_user_id
    )
    assert refreshed is not None
    return refreshed


__all__ = [
    "APPROVABLE_STAGES",
    "ITEMS_ITEM_STAGE",
    "ITEMS_KEY_PREFIX",
    "MAX_ATTEMPTS",
    "PLAN_ARTIFACT_TYPE",
    "PREPARATION_STAGE",
    "PreparationAdmission",
    "PreparationRunError",
    "SOURCE_ARTIFACT_TYPE",
    "TEACHING_ITEM_KEY",
    "TEACHING_ITEM_STAGE",
    "admit_preparation_run",
    "item_key",
    "latest_preparation_run",
    "load_current_source",
    "load_preparation_run_views",
    "preparation_run_view",
    "preparation_request_key",
    "retry_preparation_run",
    "run_source",
    "source_hash_for",
    "source_identity_from_rows",
]

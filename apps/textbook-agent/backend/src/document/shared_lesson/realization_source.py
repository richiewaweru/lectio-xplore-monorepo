"""Owner-scoped SharedLessonDocument source for path-lesson realizations.

This module gives Learn/Print-style path realizations two small, composable
entry points onto the SharedDocument pipeline:

* ``ensure_shared_document_run`` is the sole mutating call.  It idempotently
  admits (or reuses) the Run for a path lesson's *current* approved Teaching
  Plan under a deterministic request key, and advances to a new bounded
  attempt when the latest one is terminal.
* ``load_realization_source`` is a pure, side-effect-free read.  It never
  admits; it finds whatever ``ensure_shared_document_run`` most recently
  produced for this path lesson and classifies it into a closed result a
  caller can branch on without importing generic-runtime or SharedDocument
  internals.  Because it never re-admits, a Run that has fallen behind the
  current approved Teaching Plan is reported ``stale`` rather than silently
  replaced.

``ensure_shared_document_run`` does not commit; like
``admit_shared_document_run``, the caller owns the transaction so a partial
admission (Build without Run, Run without sourcebook WorkItem) can never be
observed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from document.shared_lesson.approved_source import (
    ApprovedSourceVerificationError,
    load_current_approved_teaching_plan_source,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.media import (
    DeferredFigureMediaBinding,
    FigureMediaResult,
    SharedFigureMediaError,
    bind_durable_media_output,
)
from document.shared_lesson.media_runtime import MEDIA_STAGE
from document.shared_lesson.models import SharedLessonDocument
from document.shared_lesson.qa_runtime import DOCUMENT_QA_STAGE
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
)
from document.shared_lesson.run_admission import admit_shared_document_run
from document.shared_lesson.runtime import verify_teaching_plan_source
from infra.database.models import (
    GenerationBuildModel,
    GenerationRunModel,
    GenerationWorkItemModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    RunNotFound,
    active_work_items,
    get_run_status,
)

RealizationState = Literal["ready", "pending", "needs_review", "stale", "failed"]

_TERMINAL_RUN_STATUSES = frozenset({"failed_terminal", "cancelled"})
_MAX_TERMINAL_ATTEMPTS = 3


class RealizationSourceError(ValueError):
    """Base class for expected realization-source failures."""


class RealizationSourceNotFound(RealizationSourceError):
    """The path lesson, its preparation, or its owner cannot be resolved."""


class RealizationAttemptsExhausted(RealizationSourceError):
    """Every bounded SharedDocument attempt for this plan identity is terminal."""

    code = "REALIZATION_ATTEMPTS_EXHAUSTED"


@dataclass(frozen=True)
class ReadyRealizationSource:
    """A verified, immutable SharedLessonDocument ready for a path realization."""

    run_id: str
    document: SharedLessonDocument
    content_hash: str
    plan_id: str
    plan_revision: int
    plan_hash: str
    media_results: tuple[FigureMediaResult | DeferredFigureMediaBinding, ...]


@dataclass(frozen=True)
class PendingRealizationSource:
    """The SharedDocument Run has not reached a terminal or ready state yet.

    ``run_id`` is ``None`` only when no SharedDocument Run has ever been
    admitted for this path lesson (``ensure_shared_document_run`` has not
    been called yet).
    """

    run_id: str | None
    status: str
    stage: str


@dataclass(frozen=True)
class NeedsReviewRealizationSource:
    """A document-QA leaf is blocked on a human reviewer decision."""

    run_id: str
    work_item_id: str
    stage: str


@dataclass(frozen=True)
class StaleRealizationSource:
    """The Run's output no longer matches the current approved Teaching Plan."""

    run_id: str
    reason: str


@dataclass(frozen=True)
class FailedRealizationSource:
    """The Run (or its admission) failed terminally."""

    run_id: str | None
    error_code: str | None
    error_summary: str | None


@dataclass(frozen=True)
class RealizationSourceResult:
    """Closed union over every realization-source outcome.

    Exactly one of the typed payload attributes is populated; it is selected
    by ``state``.  Callers should branch on ``state`` rather than probe the
    payload attributes directly.
    """

    state: RealizationState
    ready: ReadyRealizationSource | None = None
    pending: PendingRealizationSource | None = None
    needs_review: NeedsReviewRealizationSource | None = None
    stale: StaleRealizationSource | None = None
    failed: FailedRealizationSource | None = None


def _request_key(
    *,
    path_lesson_id: str,
    plan_id: str,
    plan_revision: int,
    plan_hash: str,
    attempt: int,
) -> str:
    base = (
        f"shared-document-realization:{path_lesson_id}:{plan_id}:{plan_revision}:{plan_hash}"
    )
    return base if attempt == 1 else f"{base}:attempt-{attempt}"


async def _load_owned_lesson(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
) -> PathLessonModel:
    if not owner_user_id.strip() or not path_lesson_id.strip():
        raise ValueError("owner_user_id and path_lesson_id must be non-empty")
    lesson = await session.scalar(
        select(PathLessonModel)
        .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
        .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
        .where(
            PathLessonModel.id == path_lesson_id,
            UnitModel.owner_id == owner_user_id,
        )
    )
    if lesson is None:
        raise RealizationSourceNotFound("path lesson is unavailable to this owner")
    return lesson


async def ensure_shared_document_run(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
) -> GenerationRunModel:
    """Idempotently resolve the SharedDocument Run for the current approved plan.

    Derives ``preparation_generation_id`` from ``PathLessonModel.pack_id`` and
    the exact approved Teaching Plan identity, then admits (or reuses) the Run
    under a deterministic request key.  A READY or still-active Run for that
    identity is always reused.  A Run whose latest attempt is terminal
    (``failed_terminal``/``cancelled``) causes a new bounded attempt to be
    admitted instead, up to ``_MAX_TERMINAL_ATTEMPTS`` terminal attempts, after
    which ``RealizationAttemptsExhausted`` is raised.

    Returned rows may be uncommitted (a freshly admitted attempt); the caller
    commits, exactly like ``admit_shared_document_run``.
    """
    lesson = await _load_owned_lesson(
        session, owner_user_id=owner_user_id, path_lesson_id=path_lesson_id
    )
    preparation_generation_id = lesson.pack_id
    if not preparation_generation_id:
        raise RealizationSourceNotFound("path lesson has no preparation generation")

    try:
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=preparation_generation_id,
        )
    except ApprovedSourceVerificationError as exc:
        raise RealizationSourceNotFound(
            f"current approved Teaching Plan is unavailable: {exc}"
        ) from exc
    identity = verify_teaching_plan_source(source)

    # Reuse any READY Run already built from this exact approved plan identity,
    # whatever request key admitted it (e.g. a Run a reviewer promoted to
    # READY, or one admitted before Learn/Print was requested).  The reader
    # still re-verifies every hash before a realization consumes it.
    ready_existing = await session.scalar(
        select(GenerationRunModel)
        .join(GenerationBuildModel, GenerationBuildModel.id == GenerationRunModel.build_id)
        .where(
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
            GenerationRunModel.status == "ready",
            GenerationBuildModel.path_lesson_id == path_lesson_id,
            GenerationRunModel.source_artifact_type == identity.source_artifact_type,
            GenerationRunModel.source_artifact_id == identity.source_artifact_id,
            GenerationRunModel.source_revision == identity.source_revision,
            GenerationRunModel.source_hash == identity.source_hash,
        )
        .order_by(GenerationRunModel.completed_at.desc().nullslast())
        .limit(1)
    )
    if ready_existing is not None:
        return ready_existing

    for attempt in range(1, _MAX_TERMINAL_ATTEMPTS + 1):
        request_key = _request_key(
            path_lesson_id=path_lesson_id,
            plan_id=identity.source_artifact_id,
            plan_revision=identity.source_revision,
            plan_hash=identity.source_hash,
            attempt=attempt,
        )
        existing = await session.scalar(
            select(GenerationRunModel).where(
                GenerationRunModel.owner_user_id == owner_user_id,
                GenerationRunModel.request_key == request_key,
            )
        )
        if existing is None:
            try:
                admission = await admit_shared_document_run(
                    session,
                    owner_user_id=owner_user_id,
                    path_lesson_id=path_lesson_id,
                    preparation_generation_id=preparation_generation_id,
                    request_key=request_key,
                )
            except RunNotFound as exc:
                raise RealizationSourceNotFound(
                    f"SharedDocument admission owner/path lesson is unavailable: {exc}"
                ) from exc
            return admission.run
        if existing.status in _TERMINAL_RUN_STATUSES:
            continue
        return existing

    raise RealizationAttemptsExhausted(
        f"every bounded SharedDocument attempt for path lesson {path_lesson_id!r} "
        "is terminal; explicit regeneration is required"
    )


def _document_media_results(
    document: SharedLessonDocument,
    active_items: Sequence[GenerationWorkItemModel],
) -> tuple[FigureMediaResult | DeferredFigureMediaBinding, ...]:
    media_items = [
        item
        for item in active_items
        if item.stage == MEDIA_STAGE or item.item_key.startswith("media:")
    ]
    results: list[FigureMediaResult | DeferredFigureMediaBinding] = []
    for item in media_items:
        if item.status != "ready" or item.output_json is None or not item.output_hash:
            raise SharedFigureMediaError(f"media WorkItem {item.id!r} is not ready")
        if content_hash(item.output_json) != item.output_hash:
            raise SharedFigureMediaError(f"media WorkItem {item.id!r} output hash is stale")
        results.append(bind_durable_media_output(item.output_json, document))
    return tuple(results)


async def _latest_shared_document_run(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
) -> GenerationRunModel | None:
    """Read-only lookup of the most recently admitted SharedDocument Run.

    This never admits.  It reflects whatever ``ensure_shared_document_run``
    last produced for this path lesson, across every plan identity and
    attempt, so a Run that has fallen behind the current approved Teaching
    Plan is still found and can be reported ``stale`` instead of silently
    disappearing behind a fresh admission.
    """
    return await session.scalar(
        select(GenerationRunModel)
        .join(GenerationBuildModel, GenerationBuildModel.id == GenerationRunModel.build_id)
        .where(
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
            GenerationBuildModel.path_lesson_id == path_lesson_id,
            GenerationBuildModel.owner_user_id == owner_user_id,
        )
        .order_by(GenerationRunModel.created_at.desc())
        .limit(1)
    )


async def load_realization_source(
    session: AsyncSession,
    *,
    owner_user_id: str,
    path_lesson_id: str,
) -> RealizationSourceResult:
    """Read-only classification of the SharedDocument source for a realization.

    This never admits a Run; call ``ensure_shared_document_run`` explicitly to
    do that.  It finds the most recently admitted SharedDocument Run for this
    path lesson and classifies it: ``ready`` with a hash-recomputed,
    lineage-verified document and bound media; ``pending`` while the Run is
    still queued, running, awaiting review, bounded-retryable, or has never
    been admitted at all; ``needs_review`` when an active document-QA leaf is
    blocked on a human reviewer decision; ``stale`` when a ready Run's output
    no longer matches the *current* approved Teaching Plan; and ``failed`` for
    a terminal Run. Owner/path-lesson scoping failures raise directly rather
    than being folded into the closed result.
    """
    await _load_owned_lesson(session, owner_user_id=owner_user_id, path_lesson_id=path_lesson_id)

    run = await _latest_shared_document_run(
        session, owner_user_id=owner_user_id, path_lesson_id=path_lesson_id
    )
    if run is None:
        return RealizationSourceResult(
            state="pending",
            pending=PendingRealizationSource(run_id=None, status="not_started", stage="not_started"),
        )

    refreshed = await get_run_status(session, run_id=run.id, owner_user_id=owner_user_id)
    if refreshed is None:
        raise RealizationSourceNotFound("SharedDocument Run is unavailable to this owner")
    run = refreshed

    if run.status in _TERMINAL_RUN_STATUSES:
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id, error_code=run.error_code, error_summary=run.error_summary
            ),
        )

    if run.status == "failed_recoverable":
        leaves = active_work_items(tuple(run.work_items))
        review_leaves = tuple(
            item
            for item in leaves
            if item.stage == DOCUMENT_QA_STAGE
            and item.status == "failed_recoverable"
            and item.recovery_action == "review"
        )
        if review_leaves:
            leaf = review_leaves[0]
            return RealizationSourceResult(
                state="needs_review",
                needs_review=NeedsReviewRealizationSource(
                    run_id=run.id, work_item_id=leaf.id, stage=leaf.stage
                ),
            )
        return RealizationSourceResult(
            state="pending",
            pending=PendingRealizationSource(run_id=run.id, status=run.status, stage=run.stage),
        )

    if run.status != "ready":
        return RealizationSourceResult(
            state="pending",
            pending=PendingRealizationSource(run_id=run.id, status=run.status, stage=run.stage),
        )

    # run.status == "ready": recompute and verify before ever calling it ready.
    if (
        run.output_artifact_type != "shared_lesson_document"
        or not run.output_artifact_id
        or run.output_revision is None
        or not run.output_hash
    ):
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id,
                error_code="REALIZATION_OUTPUT_INCOMPLETE",
                error_summary="ready Run has no complete SharedLessonDocument output identity",
            ),
        )

    try:
        stored = await load_shared_lesson_document(
            session,
            document_id=run.output_artifact_id,
            revision=run.output_revision,
            path_lesson_id=path_lesson_id,
        )
    except SharedLessonDocumentRepositoryError as exc:
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id, error_code="REALIZATION_DOCUMENT_INVALID", error_summary=str(exc)
            ),
        )

    document = stored.document
    if stored.status != "ready":
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id,
                error_code="REALIZATION_DOCUMENT_NOT_READY",
                error_summary="Run is ready but its bound document is not READY",
            ),
        )

    recomputed_hash = shared_lesson_content_hash(document)
    # ``run.output_hash`` is the full canonical-artifact hash produced by
    # ``load_verified_shared_lesson_artifact`` (the whole document JSON,
    # including its own id/revision/content_hash), which is a different,
    # wider hash than ``shared_lesson_content_hash`` (learner content and
    # lineage only). Recompute both so a Run output identity that no longer
    # matches either the artifact bytes or the narrower content identity is
    # rejected.
    recomputed_artifact_hash = content_hash(document.model_dump(mode="json"))
    if (
        recomputed_hash != document.content_hash
        or recomputed_artifact_hash != run.output_hash
        or document.id != run.output_artifact_id
        or document.revision != run.output_revision
    ):
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id,
                error_code="REALIZATION_HASH_MISMATCH",
                error_summary="stored document identity or content hash does not match the Run output",
            ),
        )

    try:
        # Re-derive the preparation id from the *current* lesson row: the
        # lesson's pack_id can move to a newer preparation after this Run was
        # admitted, which is exactly the staleness this gate must catch.
        current_lesson = await _load_owned_lesson(
            session, owner_user_id=owner_user_id, path_lesson_id=path_lesson_id
        )
        if not current_lesson.pack_id:
            raise RealizationSourceNotFound("path lesson has no preparation generation")
        current_source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=current_lesson.pack_id,
        )
        current_identity = verify_teaching_plan_source(current_source)
    except (RealizationSourceNotFound, ApprovedSourceVerificationError) as exc:
        return RealizationSourceResult(
            state="stale",
            stale=StaleRealizationSource(
                run_id=run.id, reason=f"current approved Teaching Plan is unavailable: {exc}"
            ),
        )

    if (
        document.teaching_plan_id != current_identity.source_artifact_id
        or document.teaching_plan_revision != current_identity.source_revision
        or document.teaching_plan_hash != current_identity.source_hash
    ):
        return RealizationSourceResult(
            state="stale",
            stale=StaleRealizationSource(
                run_id=run.id,
                reason="SharedLessonDocument source lineage no longer matches the current approved plan",
            ),
        )

    try:
        media_results = _document_media_results(document, active_work_items(tuple(run.work_items)))
    except SharedFigureMediaError as exc:
        return RealizationSourceResult(
            state="failed",
            failed=FailedRealizationSource(
                run_id=run.id, error_code="REALIZATION_MEDIA_INVALID", error_summary=str(exc)
            ),
        )

    return RealizationSourceResult(
        state="ready",
        ready=ReadyRealizationSource(
            run_id=run.id,
            document=document,
            content_hash=recomputed_hash,
            plan_id=document.teaching_plan_id,
            plan_revision=document.teaching_plan_revision,
            plan_hash=document.teaching_plan_hash,
            media_results=media_results,
        ),
    )


__all__ = [
    "FailedRealizationSource",
    "NeedsReviewRealizationSource",
    "PendingRealizationSource",
    "ReadyRealizationSource",
    "RealizationAttemptsExhausted",
    "RealizationSourceError",
    "RealizationSourceNotFound",
    "RealizationSourceResult",
    "RealizationState",
    "StaleRealizationSource",
    "ensure_shared_document_run",
    "load_realization_source",
]

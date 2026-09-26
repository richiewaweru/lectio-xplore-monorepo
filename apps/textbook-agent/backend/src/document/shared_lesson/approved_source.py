"""Verify the approved Teaching Plan pinned by a shared-document run.

The generic generation runtime accepts a ``SourceVerifier`` callback.  This
module supplies the preparation-specific callback without making the runtime
know about path lessons or the Teaching Plan revision ledger.

The verifier is deliberately read-only.  It locks the preparation generation
row so a finalizer cannot validate one snapshot and then finalize another;
state is copied before ``TeachingRevisionStore`` is used because that store
normalizes legacy state during construction.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    GenerationModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)
from curriculum.shared_task_authoring import ApprovedItemSnapshot
from curriculum.teaching_plan.models import TeachingPlan
from curriculum.teaching_plan.revisions import (
    TeachingRevisionApprovedItemError,
    TeachingRevisionStore,
    read_approved_item_snapshot,
)
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from infra.generation_runtime.contracts import SourceIdentity
from infra.generation_runtime.repository import SourceVerifier


class ApprovedSourceVerificationError(ValueError):
    """The current preparation cannot prove the requested approved source."""

    code = "APPROVED_SOURCE_UNAVAILABLE"


async def load_current_approved_teaching_plan_source(
    *,
    session: AsyncSession,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
) -> TeachingPlanSource:
    """Load the exact approved Teaching Plan pinned by current preparation.

    The caller supplies only the owner and preparation/path identities.  The
    returned plan and revision record are reconstructed from the persisted
    approval ledger while the generation, path lesson, and provenance rows are
    locked for a consistent read.  No caller-supplied plan or hash participates
    in this loader.
    """

    if not owner_user_id or not path_lesson_id or not preparation_generation_id:
        raise ValueError("approved-source loader bindings must be non-empty")

    generation = await session.scalar(
        select(GenerationModel)
        .where(GenerationModel.id == preparation_generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if generation is None or generation.user_id != owner_user_id:
        raise ApprovedSourceVerificationError("preparation generation is unavailable to this owner")

    lesson = await session.scalar(
        select(PathLessonModel)
        .join(PathVersionModel, PathVersionModel.id == PathLessonModel.path_version_id)
        .join(UnitModel, UnitModel.id == PathVersionModel.unit_id)
        .where(
            PathLessonModel.id == path_lesson_id,
            UnitModel.owner_id == owner_user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if lesson is None:
        raise ApprovedSourceVerificationError("path lesson is unavailable to this owner")
    if lesson.pack_id != preparation_generation_id:
        raise ApprovedSourceVerificationError(
            "path lesson does not point at the current preparation generation"
        )

    provenance = await session.scalar(
        select(LessonProvenanceModel)
        .where(LessonProvenanceModel.pack_id == preparation_generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if provenance is None:
        raise ApprovedSourceVerificationError("preparation path provenance is missing")
    if provenance.invalidated_at is not None:
        raise ApprovedSourceVerificationError("preparation path provenance is invalidated")
    if (
        provenance.path_lesson_id != path_lesson_id
        or provenance.path_version_id != lesson.path_version_id
        or provenance.path_lesson_revision != lesson.revision
        or provenance.objective_hash != lesson.objective_hash
    ):
        raise ApprovedSourceVerificationError(
            "preparation path provenance does not match the current lesson"
        )

    state = generation.chunked_state_json
    if not isinstance(state, dict):
        raise ApprovedSourceVerificationError("preparation state is unavailable")
    page_state = state.get("page_document_v2")
    if not isinstance(page_state, dict):
        raise ApprovedSourceVerificationError(
            "preparation state has no page_document_v2 Teaching Plan ledger"
        )

    # TeachingRevisionStore currently materializes narrow legacy state in its
    # constructor.  Give it a copy so verification cannot mutate the ORM JSON
    # value or create a false approval while reading it.
    revision_state: dict[str, Any] = deepcopy(page_state)
    review = revision_state.get("teaching_review")
    if not isinstance(review, dict):
        raise ApprovedSourceVerificationError("Teaching Plan review state is missing")
    approved_raw = review.get("approved_revision")
    if isinstance(approved_raw, bool) or approved_raw is None:
        raise ApprovedSourceVerificationError("Teaching Plan approved_revision pointer is missing")
    try:
        approved_revision = int(approved_raw)
    except (TypeError, ValueError) as exc:
        raise ApprovedSourceVerificationError(
            "Teaching Plan approved_revision pointer is invalid"
        ) from exc
    if approved_revision < 1:
        raise ApprovedSourceVerificationError("Teaching Plan approved_revision pointer is invalid")

    store = TeachingRevisionStore(revision_state)
    record = store.get_revision(approved_revision)
    if record is None:
        raise ApprovedSourceVerificationError(
            f"approved Teaching Plan revision {approved_revision} is missing"
        )
    if record.status != "approved":
        raise ApprovedSourceVerificationError(
            "approved_revision must select an approved Teaching Plan record"
        )
    if not record.content_hash:
        raise ApprovedSourceVerificationError("approved Teaching Plan revision has no content hash")

    try:
        plan = TeachingPlan.model_validate(record.plan)
    except (TypeError, ValueError) as exc:
        raise ApprovedSourceVerificationError("approved Teaching Plan revision is invalid") from exc
    if plan.contract_version != 2:
        raise ApprovedSourceVerificationError(
            "shared-document source requires an approved Teaching Plan V2 record"
        )
    try:
        source = TeachingPlanSource(
            plan=plan,
            revision_record=record,
            id=record.teaching_plan_id,
            revision=record.revision,
            content_hash=record.content_hash,
        )
        verify_teaching_plan_source(source)
    except (TypeError, ValueError) as exc:
        raise ApprovedSourceVerificationError(
            "approved Teaching Plan source failed hash or identity verification"
        ) from exc
    return source


def make_approved_source_verifier(
    *,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
) -> SourceVerifier:
    """Bind a read-only approved-source verifier to one preparation context.

    The returned callback has the generic runtime's ``SourceVerifier`` shape.
    It verifies the generation owner, current path lesson/provenance link, and
    the exact approved hash-bearing V2 revision selected by the nested review
    pointer before returning a freshly recomputed ``SourceIdentity``.
    """

    if not owner_user_id or not path_lesson_id or not preparation_generation_id:
        raise ValueError("approved-source verifier bindings must be non-empty")

    async def verify(session: AsyncSession, requested: SourceIdentity) -> SourceIdentity:
        source = await load_current_approved_teaching_plan_source(
            session=session,
            owner_user_id=owner_user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=preparation_generation_id,
        )
        identity = verify_teaching_plan_source(source)

        if identity != requested:
            raise ApprovedSourceVerificationError(
                "current approved Teaching Plan differs from the requested source identity"
            )
        return identity

    return verify


async def load_approved_item_snapshot(
    *,
    session: AsyncSession,
    owner_user_id: str,
    path_lesson_id: str,
    preparation_generation_id: str,
    requested: SourceIdentity,
) -> ApprovedItemSnapshot:
    """Load the immutable item snapshot for one verified approved plan.

    The source verifier remains the authority for owner, path/provenance, and
    Teaching Plan identity.  This loader then reads the same approved revision
    from the frozen ledger and validates its revision-bound item digest.  It
    never consults the mutable lesson packet or accepts caller-supplied items.
    """

    source = await load_current_approved_teaching_plan_source(
        session=session,
        owner_user_id=owner_user_id,
        path_lesson_id=path_lesson_id,
        preparation_generation_id=preparation_generation_id,
    )
    identity = verify_teaching_plan_source(source)
    if identity != requested:
        raise ApprovedSourceVerificationError(
            "current approved Teaching Plan differs from the requested source identity"
        )

    generation = await session.scalar(
        select(GenerationModel)
        .where(GenerationModel.id == preparation_generation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if generation is None:
        # The verifier already checks this, but retain a typed failure if a
        # concurrent transaction changes the row between the two reads.
        raise ApprovedSourceVerificationError("preparation generation is unavailable")
    state = generation.chunked_state_json
    if not isinstance(state, dict):
        raise ApprovedSourceVerificationError("preparation state is unavailable")
    page_state = state.get("page_document_v2")
    if not isinstance(page_state, dict):
        raise ApprovedSourceVerificationError(
            "preparation state has no page_document_v2 Teaching Plan ledger"
        )

    try:
        review = page_state.get("teaching_review")
        if not isinstance(review, dict):
            raise TeachingRevisionApprovedItemError("Teaching Plan review state is missing")
        approved_revision = review.get("approved_revision")
        if isinstance(approved_revision, bool) or approved_revision is None:
            raise TeachingRevisionApprovedItemError(
                "Teaching Plan approved_revision pointer is missing"
            )
        record = TeachingRevisionStore(deepcopy(page_state)).get_revision(int(approved_revision))
        if record is None or record.status != "approved":
            raise TeachingRevisionApprovedItemError(
                "approved Teaching Plan revision is unavailable"
            )
        snapshot = read_approved_item_snapshot(record)
        validated = ApprovedItemSnapshot.model_validate(snapshot)
    except (TypeError, ValueError) as exc:
        raise ApprovedSourceVerificationError(
            "approved Teaching Plan item snapshot failed hash or identity verification"
        ) from exc

    if (
        validated.teaching_plan_id != requested.source_artifact_id
        or validated.teaching_plan_revision != requested.source_revision
        or validated.teaching_plan_hash != requested.source_hash
    ):
        raise ApprovedSourceVerificationError(
            "approved item snapshot differs from the requested source identity"
        )
    return validated


__all__ = [
    "ApprovedSourceVerificationError",
    "load_approved_item_snapshot",
    "load_current_approved_teaching_plan_source",
    "make_approved_source_verifier",
]

"""Publish-time SharedLessonDocument lineage verification (P10C).

A ``LearnRelease`` cut from a lesson stamped with SharedLessonDocument
lineage (P10B, ``EditableLessonModel.shared_document_id``) must prove, at
publish time, that:

1. the stamped id/revision still resolves to a READY, hash-verified shared
   document (the same recomputation the Builder open path performs at
   ``learn.authoring.builder.service._verify_shared_document_lineage``), and
2. the lesson's ordinary (non-``interaction``) nodes are still exactly the
   realization the Learn adapter would produce from that shared document —
   reusing ``learn.authoring.builder.service.ordinary_nodes_by_id`` and the
   adapter itself, so a forked ordinary edit can never publish even if it
   slipped past a single Builder save-time check.

Lessons without shared lineage (``shared_document_id`` is ``None``) are
unaffected; this module is a no-op for them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import EditableLessonModel
from document.shared_lesson.repository import (
    SharedLessonDocumentRepositoryError,
    load_shared_lesson_document,
)
from learn.authoring.builder.service import (
    SharedDocumentLineageMismatchError,
    SharedDocumentOrdinaryEditBlockedError,
    ordinary_nodes_by_id,
)
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    SharedDocumentLearnMappingError,
    realize_shared_document_for_learn,
)


@dataclass(frozen=True)
class SharedDocumentPublishLineage:
    """Verified SharedLessonDocument identity to stamp onto a ``LearnRelease``."""

    run_id: str | None
    id: str
    revision: int
    hash: str


async def verify_shared_document_lineage_for_publish(
    session: AsyncSession,
    *,
    lesson: EditableLessonModel,
    document: Mapping[str, Any],
) -> SharedDocumentPublishLineage | None:
    """Verify shared lineage for one publish, or ``None`` when unstamped.

    Raises ``SharedDocumentLineageMismatchError`` when the stamped identity no
    longer verifies (stale revision, non-READY, hash drift, or unmappable
    content), and ``SharedDocumentOrdinaryEditBlockedError`` when the lesson's
    ordinary content has forked from the shared realization.
    """
    document_id = getattr(lesson, "shared_document_id", None)
    if not document_id:
        return None

    revision = lesson.shared_document_revision
    if revision is None:
        raise SharedDocumentLineageMismatchError(
            "Lesson is stamped with a SharedLessonDocument id but no revision"
        )

    try:
        stored = await load_shared_lesson_document(
            session, document_id=document_id, revision=int(revision)
        )
    except SharedLessonDocumentRepositoryError as exc:
        raise SharedDocumentLineageMismatchError(
            f"SharedLessonDocument lineage no longer verifies: {exc}"
        ) from exc

    if stored.status != "ready":
        raise SharedDocumentLineageMismatchError(
            "SharedLessonDocument backing this lesson is no longer READY"
        )
    if stored.document.content_hash != lesson.shared_document_hash:
        raise SharedDocumentLineageMismatchError(
            "SharedLessonDocument content hash no longer matches the stamped lineage"
        )

    expected_identity = SharedDocumentIdentity(
        id=stored.document.id,
        revision=stored.document.revision,
        content_hash=stored.document.content_hash,
    )
    subject = (
        str(document.get("subject") or "general")
        if isinstance(document, Mapping)
        else "general"
    )
    try:
        realized = realize_shared_document_for_learn(
            stored,
            expected_identity=expected_identity,
            subject=subject,
            source_generation_id=lesson.source_generation_id,
            learn_document_id=lesson.id,
        )
    except SharedDocumentLearnMappingError as exc:
        raise SharedDocumentLineageMismatchError(
            f"SharedLessonDocument can no longer be realized for Learn: {exc}"
        ) from exc

    realized_nodes = realized.document.model_dump(mode="json").get("nodes")
    published_nodes = document.get("nodes") if isinstance(document, Mapping) else None
    if not isinstance(realized_nodes, list) or not isinstance(published_nodes, list):
        raise SharedDocumentOrdinaryEditBlockedError(
            "Lesson document has no ordered nodes to verify against its shared source."
        )
    # Figure image URL/alt come from the Run's media results, not the shared
    # document, so they are not part of the shared-authored fork check.
    if _without_figure_media(ordinary_nodes_by_id(realized_nodes)) != _without_figure_media(
        ordinary_nodes_by_id(published_nodes)
    ):
        raise SharedDocumentOrdinaryEditBlockedError(
            "Ordinary content on this lesson has diverged from its shared source and "
            "cannot be published."
        )

    return SharedDocumentPublishLineage(
        run_id=getattr(lesson, "shared_document_run_id", None),
        id=stored.document.id,
        revision=stored.document.revision,
        hash=stored.document.content_hash,
    )


def _without_figure_media(nodes: Mapping[Any, Any]) -> dict[Any, Any]:
    return {
        node_id: (
            {k: v for k, v in node.items() if k not in ("asset_id", "alt")}
            if isinstance(node, Mapping) and node.get("kind") == "figure"
            else node
        )
        for node_id, node in nodes.items()
    }


__all__ = [
    "SharedDocumentPublishLineage",
    "verify_shared_document_lineage_for_publish",
]

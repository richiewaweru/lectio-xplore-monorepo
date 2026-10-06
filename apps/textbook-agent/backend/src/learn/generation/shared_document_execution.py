"""Route Learn realization through the verified SharedLessonDocument (P10B).

This module replaces ``produce_learn_from_approved_teaching`` on the Learn
creation path. It never authors ordinary content: it copies the immutable
shared artifact through ``realize_shared_document_for_learn`` and persists
the result exactly where the old path persisted its output.

Option D (4A): the function is a pure, idempotent materializer.  It owns no
lease, no worker state machine and no realization status; the
``RealizationWorker`` runs it under a shared-runtime work-item lease and the
realization status is projected from the Run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import EditableLessonModel, GenerationModel, NativeRealizationModel
from document.shared_lesson.media import FigureMediaResult
from document.shared_lesson.realization_source import (
    ReadyRealizationSource,
    RealizationOutputError,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    realize_shared_document_for_learn,
)
from learn.publishing.publish_validation import validate_publishable_lesson_document


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _figure_fields_from_media(
    media: list[FigureMediaResult],
) -> dict[str, dict[str, str]]:
    return {
        m.figure_node_id: {"asset_id": m.asset_url, "alt": m.alt_text.strip()}
        for m in media
        if m.status in ("ready", "ready_with_quality_warning")
        and m.asset_url.lower().startswith(("http://", "https://"))
    }


def _with_figure_media(
    document: dict[str, Any], fields: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """Return a copy of ``document`` with image-less figure nodes given media."""
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        return document
    changed = False
    patched: list[Any] = []
    for node in nodes:
        if (
            isinstance(node, dict)
            and node.get("kind") == "figure"
            and not node.get("asset_id")
            and node.get("id") in fields
        ):
            update = fields[node["id"]]
            node = {
                **node,
                "asset_id": update["asset_id"],
                "alt": update["alt"] or node.get("alt") or node.get("caption") or "",
            }
            changed = True
        patched.append(node)
    return {**document, "nodes": patched} if changed else document


async def materialize_learn_output_from_shared_document(
    session: AsyncSession,
    *,
    realization: NativeRealizationModel,
    ready: ReadyRealizationSource,
    owner_user_id: str,
    subject: str,
) -> dict[str, Any]:
    """Realize one Learn output from a verified, READY SharedLessonDocument.

    Ordinary content is copied; only TaskAnchors are lowered to Learn
    interactions. No composer/writer/task-authoring call is made here.  The
    caller owns the transaction: this only flushes.  Re-running against the
    same immutable inputs is a no-op that returns the stored identity.
    """
    output_id = str(realization.output_id or "")
    output = await session.get(GenerationModel, output_id)
    if output is None or output.user_id != owner_user_id:
        raise RealizationOutputError("The Learn output row is missing or owned by another user.")
    output_state = dict(output.chunked_state_json or {})
    pinned = (
        output_state.get("native_learn") is True
        and output_state.get("preparation_generation_id") == realization.preparation_generation_id
        and output_state.get("teaching_plan_id") == realization.teaching_plan_id
        and int(output_state.get("teaching_plan_revision") or 0)
        == int(realization.teaching_plan_revision)
        and output_state.get("teaching_plan_hash") == realization.teaching_plan_hash
    )
    if not pinned:
        raise RealizationOutputError("The Learn output does not match its pinned realization.")

    document = ready.document
    existing_editable_id = await session.scalar(
        select(EditableLessonModel.id)
        .where(
            EditableLessonModel.source_generation_id == output_id,
            EditableLessonModel.user_id == owner_user_id,
        )
        .order_by(EditableLessonModel.created_at.desc())
    )
    figure_media = [m for m in ready.media_results if isinstance(m, FigureMediaResult)]
    if (
        output.status == "completed"
        and isinstance(output.document_json, dict)
        and existing_editable_id
        and output.shared_document_hash == ready.content_hash
    ):
        # Lessons realized before figure media was threaded into Learn have
        # figure nodes with no image.  Re-project only the figure fields from
        # the Run's verified media (no regeneration, no other edits).
        if figure_media:
            media_node_fields = _figure_fields_from_media(figure_media)
            output.document_json = _with_figure_media(output.document_json, media_node_fields)
            editable = await session.get(EditableLessonModel, existing_editable_id)
            if editable is not None and isinstance(editable.document_json, dict):
                editable.document_json = _with_figure_media(
                    editable.document_json, media_node_fields
                )
        return {
            "output_id": output_id,
            "editable_lesson_id": existing_editable_id,
            "content_hash": ready.content_hash,
            "replayed": True,
        }

    expected_identity = SharedDocumentIdentity(
        id=document.id, revision=document.revision, content_hash=ready.content_hash
    )
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=str(realization.path_lesson_id),
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    # Mapping/validation errors propagate typed; the worker turns them into a
    # terminal validation failure on the work item.
    realized = realize_shared_document_for_learn(
        stored,
        expected_identity=expected_identity,
        subject=subject,
        source_generation_id=output_id,
        learn_document_id=output_id,
        figure_media=figure_media,
    )
    learn_document = dict(realized.document.model_dump(mode="json"))
    learn_document["id"] = output_id
    learn_document["source_generation_id"] = output_id
    validate_publishable_lesson_document(learn_document)

    output.status = "completed"
    output.document_json = learn_document
    output.shared_document_run_id = ready.run_id
    output.shared_document_id = document.id
    output.shared_document_revision = document.revision
    output.shared_document_hash = ready.content_hash
    output.chunked_state_json = {
        **output_state,
        "shared_preparation": False,
        "native_learn": True,
        "learn_document": True,
        "document_version": 2,
        "control": {"pipeline": "shared_document_learn"},
        "teaching_plan_id": ready.plan_id,
        "teaching_plan_revision": ready.plan_revision,
        "teaching_plan_hash": ready.plan_hash,
        "shared_document": {
            "run_id": ready.run_id,
            "id": document.id,
            "revision": document.revision,
            "content_hash": ready.content_hash,
            "teaching_plan_id": ready.plan_id,
            "teaching_plan_revision": ready.plan_revision,
            "teaching_plan_hash": ready.plan_hash,
        },
    }

    lesson_id = existing_editable_id
    if not lesson_id:
        lesson_id = str(uuid.uuid4())
        now = _utcnow()
        session.add(
            EditableLessonModel(
                id=lesson_id,
                user_id=owner_user_id,
                source_generation_id=output_id,
                source_type="learn_document",
                title=str(learn_document.get("title") or "Learn lesson"),
                class_label=None,
                document_json={
                    **learn_document,
                    "id": lesson_id,
                    "updated_at": now.isoformat() + "Z",
                    "created_at": now.isoformat() + "Z",
                },
                created_at=now,
                updated_at=now,
                shared_document_run_id=ready.run_id,
                shared_document_id=document.id,
                shared_document_revision=document.revision,
                shared_document_hash=ready.content_hash,
            )
        )

    # Lineage only; ``realization.status`` is projected from the Run.
    realization.teaching_plan_hash = ready.plan_hash
    realization.shared_document_run_id = ready.run_id
    realization.shared_document_id = document.id
    realization.shared_document_revision = document.revision
    realization.shared_document_hash = ready.content_hash
    realization.shared_document_state = "ready"
    await session.flush()

    return {
        "output_id": output_id,
        "editable_lesson_id": lesson_id,
        "content_hash": ready.content_hash,
        "replayed": False,
    }


__all__ = ["materialize_learn_output_from_shared_document"]

"""Assemble canonical Lectio LessonDocument artifacts from checkpoints (Phase 08)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from v3_blueprint.planning.canonical_plan import CanonicalExecutionPlan
from v3_execution.runtime.checkpoints import CheckpointStore


def lesson_is_partial(plan: CanonicalExecutionPlan, store: CheckpointStore) -> bool:
    ready = {
        block_id
        for block_id, checkpoint in store.blocks.items()
        if checkpoint.state == "ready"
    }
    return any(block_id not in ready for section in plan.sections for block_id in section.block_ids)


def assemble_lesson_document(
    plan: CanonicalExecutionPlan,
    store: CheckpointStore,
    *,
    title: str,
    human_revision: int = 0,
    generator_revision: int | None = None,
    subject: str = "General",
    preset_id: str = "blue-classroom",
    template_id: str | None = None,
    source: str = "generated",
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Build a Builder-openable Lectio LessonDocument from ready checkpoints.

    Human-edit fence: if human_revision > generator_revision, ready generator
    payloads for older revisions are ignored for those blocks.

    Generation-runtime fields (plan_hash, pipeline, partial) stay out of this document.
    """
    gen_rev = plan.plan_revision if generator_revision is None else generator_revision
    now = datetime.now(timezone.utc).isoformat()
    stamp = created_at or now
    generation_id = plan.generation_id or "lesson"
    resolved_template = template_id or plan.template_id

    blocks: dict[str, Any] = {}
    sections: list[dict[str, Any]] = []

    ready = {
        block_id: checkpoint
        for block_id, checkpoint in store.blocks.items()
        if checkpoint.state == "ready"
    }

    for section in plan.sections:
        block_ids: list[str] = []
        for block_id in section.block_ids:
            checkpoint = ready.get(block_id)
            if checkpoint is None:
                continue
            if human_revision > gen_rev and checkpoint.plan_revision <= gen_rev:
                continue
            meta = next(b for b in plan.blocks if b.block_id == block_id)
            content = checkpoint.payload.get("content", {})
            if not isinstance(content, dict):
                content = {"value": content}
            blocks[block_id] = {
                "id": block_id,
                "component_id": meta.component_id,
                "content": content,
                "position": meta.position,
            }
            block_ids.append(block_id)
        sections.append(
            {
                "id": section.section_id,
                "template_id": resolved_template,
                "block_ids": block_ids,
                "title": section.title,
                "position": section.position,
            }
        )

    return {
        "version": 1,
        "id": generation_id,
        "title": title,
        "subject": subject,
        "preset_id": preset_id,
        "source": source,
        "source_generation_id": generation_id,
        "sections": sections,
        "blocks": blocks,
        "media": {},
        "created_at": stamp,
        "updated_at": updated_at or stamp,
    }


def reconnect_from_store(store: CheckpointStore) -> dict[str, Any]:
    """Browser/SSE reconnect reconstructs from durable store alone."""
    return store.reconstruct()

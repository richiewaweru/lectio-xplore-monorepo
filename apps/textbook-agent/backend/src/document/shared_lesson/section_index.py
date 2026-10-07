"""Read-only section titles for one SharedDocument Run.

Lets teacher-facing surfaces (Issues tab, Quality Notes) show a section's title
instead of its internal id. Tolerant by design: anything missing yields no
titles, never an error.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database.models import GenerationRunModel, SharedLessonDocumentModel


async def load_run_sections(
    session: AsyncSession,
    *,
    run_id: str | None,
    owner_user_id: str,
) -> list[dict[str, Any]]:
    """``[{id, title, nodes: [{id}]}]`` for the run's finished document, else ``[]``."""
    if not run_id:
        return []
    run = await session.scalar(
        select(GenerationRunModel).where(
            GenerationRunModel.id == run_id,
            GenerationRunModel.owner_user_id == owner_user_id,
            GenerationRunModel.run_type == "shared_document",
        )
    )
    if (
        run is None
        or run.output_artifact_type != "shared_lesson_document"
        or not run.output_artifact_id
        or run.output_revision is None
    ):
        return []
    row = await session.get(
        SharedLessonDocumentModel,
        {"id": run.output_artifact_id, "revision": run.output_revision},
    )
    payload = row.document_json if row is not None else None
    raw_sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(raw_sections, list):
        return []
    sections: list[dict[str, Any]] = []
    for section in raw_sections:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str):
            continue
        nodes = section.get("nodes")
        sections.append(
            {
                "id": section["id"],
                "title": section.get("title") if isinstance(section.get("title"), str) else "",
                "nodes": [
                    {"id": node["id"]}
                    for node in (nodes if isinstance(nodes, list) else [])
                    if isinstance(node, dict) and isinstance(node.get("id"), str)
                ],
            }
        )
    return sections


__all__ = ["load_run_sections"]

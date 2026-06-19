from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.models import ProductionBlueprint

SCHEMA_VERSION = "v3_planning_artifact_v1"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_planning_artifact(
    *,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
    blueprint: ProductionBlueprint,
    form: V3InputForm | None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    section_ids = [section.section_id for section in blueprint.sections]
    component_count = sum(len(section.components) for section in blueprint.sections)
    visual_required_count = sum(1 for section in blueprint.sections if section.visual_required)

    source_payload = {
        "kind": "teacher_approved_blueprint",
        "parent_generation_id": None,
        "parent_blueprint_id": None,
        "target_resource_type": None,
    }
    if source:
        source_payload.update(source)

    return {
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "blueprint_id": blueprint_id,
        "template_id": template_id,
        "created_at": _utc_iso(),
        "source": source_payload,
        "form": form.model_dump(mode="json") if form is not None else None,
        "blueprint": blueprint.model_dump(mode="json"),
        "derived": {
            "title": blueprint.metadata.title,
            "subject": blueprint.metadata.subject,
            "resource_type": blueprint.lesson.resource_type,
            "section_count": len(blueprint.sections),
            "section_ids": section_ids,
            "component_count": component_count,
            "question_count": len(blueprint.question_plan),
            "visual_required_count": visual_required_count,
        },
    }


def planning_summary_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    derived = artifact.get("derived")
    if not isinstance(derived, dict):
        derived = {}

    return {
        "schema_version": artifact.get("schema_version"),
        "blueprint_id": artifact.get("blueprint_id"),
        "template_id": artifact.get("template_id"),
        "resource_type": derived.get("resource_type"),
        "title": derived.get("title"),
        "subject": derived.get("subject"),
        "section_count": derived.get("section_count", 0),
        "section_ids": derived.get("section_ids", []),
        "component_count": derived.get("component_count", 0),
        "question_count": derived.get("question_count", 0),
        "visual_required_count": derived.get("visual_required_count", 0),
        "has_full_planning_artifact": True,
        "source": artifact.get("source", {}),
    }


def parse_planning_artifact(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    if parsed.get("schema_version") != SCHEMA_VERSION:
        return None
    return parsed


__all__ = [
    "SCHEMA_VERSION",
    "build_planning_artifact",
    "parse_planning_artifact",
    "planning_summary_from_artifact",
]

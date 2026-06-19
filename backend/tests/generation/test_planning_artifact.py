from __future__ import annotations

import json
from pathlib import Path

from generation.v3_studio.dtos import V3InputForm
from generation.v3_studio.planning_artifact import (
    SCHEMA_VERSION,
    build_planning_artifact,
    parse_planning_artifact,
    planning_summary_from_artifact,
)
from v3_blueprint.models import ProductionBlueprint


def _example_bp(name: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / name
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _example_form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 8",
        subject="Mathematics",
        duration_minutes=50,
        topic="Compound area (L-shapes)",
        subtopics=["L-shapes"],
        prior_knowledge="Rectangle area",
        lesson_mode="first_exposure",
        intended_outcome="understand",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        support_needs=["visuals"],
        free_text="Teach compound area with scaffolded examples.",
    )


def test_build_planning_artifact_contains_full_blueprint() -> None:
    blueprint = _example_bp("amara_compound_area.json")
    form = _example_form()

    artifact = build_planning_artifact(
        generation_id="gen-1",
        blueprint_id="bp-1",
        template_id="guided-concept-path",
        blueprint=blueprint,
        form=form,
    )

    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["generation_id"] == "gen-1"
    assert artifact["blueprint_id"] == "bp-1"
    assert isinstance(artifact["blueprint"], dict)
    assert artifact["form"]["grade_level"] == "Grade 8"

    derived = artifact["derived"]
    assert derived["title"] == blueprint.metadata.title
    assert derived["subject"] == blueprint.metadata.subject
    assert derived["resource_type"] == blueprint.lesson.resource_type
    assert derived["section_count"] == len(blueprint.sections)
    assert derived["component_count"] == sum(
        len(section.components) for section in blueprint.sections
    )
    assert derived["question_count"] == len(blueprint.question_plan)
    assert derived["visual_required_count"] == sum(
        1 for section in blueprint.sections if section.visual_required
    )
def test_planning_summary_from_artifact_is_lightweight() -> None:
    blueprint = _example_bp("amara_compound_area.json")
    artifact = build_planning_artifact(
        generation_id="gen-1",
        blueprint_id="bp-1",
        template_id="guided-concept-path",
        blueprint=blueprint,
        form=None,
    )

    summary = planning_summary_from_artifact(artifact)

    assert summary["blueprint_id"] == "bp-1"
    assert summary["has_full_planning_artifact"] is True
    assert summary["section_count"] == len(blueprint.sections)
    assert "blueprint" not in summary


def test_parse_planning_artifact_handles_null_and_bad_json() -> None:
    assert parse_planning_artifact(None) is None
    assert parse_planning_artifact("not-json") is None
    assert parse_planning_artifact('{"schema_version": "other"}') is None

from __future__ import annotations

import json
from pathlib import Path

import pytest

from generation.v3_studio.dtos import V3InputForm
from v3_blueprint.models import ProductionBlueprint

from generation.v3_studio.preview_mapper import blueprint_to_preview_dto


def _example_bp(name: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / name
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def test_blueprint_to_preview_dto_shape() -> None:
    bp = _example_bp("amara_compound_area.json")
    dto = blueprint_to_preview_dto(
        blueprint_id="bid-test",
        blueprint=bp,
        template_id="guided-concept-path",
    )
    assert dto.blueprint_id == "bid-test"
    assert dto.title == bp.metadata.title
    assert dto.section_plan
    assert dto.question_plan
    assert all(sec.components for sec in dto.section_plan)
    for sec in dto.section_plan:
        for comp in sec.components:
            assert comp.teacher_label
            assert comp.component_id


def test_blueprint_to_preview_dto_default_template_id() -> None:
    bp = _example_bp("amara_compound_area.json")
    dto = blueprint_to_preview_dto(blueprint_id="bid-default", blueprint=bp)
    assert dto.template_id == "guided-concept-path"
    assert dto.learner_context is None


def test_blueprint_to_preview_dto_includes_learner_context_when_form_provided() -> None:
    bp = _example_bp("amara_compound_area.json")
    form = V3InputForm(
        grade_level="Grade 8",
        subject="Mathematics",
        duration_minutes=50,
        resource_type="lesson",
        topic="Compound area",
        subtopics=["L-shapes"],
        prior_knowledge="Rectangle area",
        outcome="Students can find the area of compound shapes.",
        struggle="They may not know how to split the shape into rectangles.",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="some_ell",
        prior_knowledge_level="some_background",
        free_text="",
    )
    dto = blueprint_to_preview_dto(
        blueprint_id="bid-with-context",
        blueprint=bp,
        template_id="guided-concept-path",
        form=form,
    )
    assert dto.learner_context is not None
    assert dto.learner_context.grade_level == "Grade 8"
    assert dto.learner_context.subject == "Mathematics"
    assert dto.learner_context.resource_type == "lesson"
    assert dto.learner_context.outcome == "Students can find the area of compound shapes."


@pytest.mark.asyncio
async def test_v3_studio_router_import() -> None:
    from generation.v3_studio.router import v3_studio_router

    assert v3_studio_router.prefix == "/v3"

from __future__ import annotations

import json
from pathlib import Path

from v3_blueprint.compiler import BlueprintCompiler
from v3_blueprint.models import ProductionBlueprint
from v3_blueprint.validators import validate_blueprint_completeness


EXAMPLE_FILENAMES = [
    "amara_compound_area.json",
    "david_parallel_circuits.json",
    "priya_equivalent_fractions_repair.json",
    "james_mitosis_booklet.json",
]


def _examples_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples"


def _load_blueprint(filename: str) -> ProductionBlueprint:
    payload = json.loads((_examples_dir() / filename).read_text(encoding="utf-8"))
    return ProductionBlueprint.model_validate(payload)


def test_all_persona_blueprints_validate() -> None:
    for filename in EXAMPLE_FILENAMES:
        blueprint = _load_blueprint(filename)
        assert blueprint.metadata.version == "3.0"
        assert validate_blueprint_completeness(blueprint) == []


def test_all_work_orders_compile() -> None:
    compiler = BlueprintCompiler()
    for filename in EXAMPLE_FILENAMES:
        blueprint = _load_blueprint(filename)
        orders = compiler.compile_all(blueprint)
        assert len(orders.section_orders) > 0
        assert orders.visual_order is not None
        assert len(orders.interaction_orders) > 0
        assert orders.answer_key_order is not None
        assert orders.coherence_review_order is not None


def test_blueprint_compiler_is_deterministic() -> None:
    blueprint = _load_blueprint("amara_compound_area.json")
    compiler = BlueprintCompiler()

    first = compiler.compile_all(blueprint).model_dump(mode="json")
    second = compiler.compile_all(blueprint).model_dump(mode="json")

    assert first == second


def test_amara_has_no_cold_questions() -> None:
    blueprint = _load_blueprint("amara_compound_area.json")
    assert blueprint.lesson.lesson_mode == "first_exposure"
    assert blueprint.anchor.reuse_scope == "entire_resource"
    assert all(item.temperature != "cold" for item in blueprint.question_plan)


def test_priya_repair_focus_is_populated() -> None:
    blueprint = _load_blueprint("priya_equivalent_fractions_repair.json")
    assert blueprint.lesson.lesson_mode == "repair"
    assert blueprint.repair_focus is not None
    assert blueprint.repair_focus.fault_line.strip()
    assert blueprint.repair_focus.what_not_to_teach


def test_james_mini_booklet_has_summary_section() -> None:
    blueprint = _load_blueprint("james_mitosis_booklet.json")
    assert blueprint.lesson.resource_type == "mini_booklet"
    assert any(section.section_id == "summary" for section in blueprint.sections)

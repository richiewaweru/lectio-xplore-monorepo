from __future__ import annotations

import json
from pathlib import Path

from v3_blueprint.models import ProductionBlueprint


FIXTURE_DIR = Path(__file__).resolve().parent


def test_generation_5aed3804_fixtures_load() -> None:
    pack = json.loads((FIXTURE_DIR / "gen_5aed3804_pack.json").read_text(encoding="utf-8"))
    blueprint = ProductionBlueprint.model_validate_json(
        (FIXTURE_DIR / "gen_5aed3804_blueprint.json").read_text(encoding="utf-8")
    )

    assert len(pack["sections"]) == 5
    assert len(blueprint.sections) == 5
    close = next(section for section in pack["sections"] if section["section_id"] == "close")
    assert "practice" in close
    assert len(blueprint.question_plan) == 4
    assert sum(len(section.components) for section in blueprint.sections) == 15
    assert sum(1 for section in blueprint.sections if section.visual_required) == 2

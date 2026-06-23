from __future__ import annotations

import json
from pathlib import Path

from v3_blueprint.models import ProductionBlueprint
from v3_execution.compile_orders import compile_execution_bundle


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def test_compile_orders_derives_multiple_diagram_series_frames() -> None:
    bp = _load_example("james_mitosis_booklet.json")
    vis = next(v for v in bp.visual_strategy.visuals if v.section_id == "diagram_sequence")

    bundle = compile_execution_bundle(
        bp,
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
    )
    order = next(o for o in bundle.visual_orders if o.visual.attaches_to == "diagram_sequence")

    assert order.visual.mode == "diagram_series"
    assert len(order.visual.frames) == 3
    assert order.dependency == "blueprint_only"
    assert "Prophase" in order.visual.frames[0].description
    assert "Metaphase" in order.visual.frames[1].description
    assert "Anaphase" in order.visual.frames[2].description


def test_compile_orders_series_falls_back_without_markers() -> None:
    bp = _load_example("james_mitosis_booklet.json")
    sec = next(s for s in bp.sections if s.section_id == "diagram_sequence")
    comp = next(c for c in sec.components if c.component == "diagram_series")
    comp.content_intent = "A single generic mitosis sequence description."
    vis = next(v for v in bp.visual_strategy.visuals if v.section_id == "diagram_sequence")
    vis.strategy = "mitosis diagram series"
    vis.frames = []

    bundle = compile_execution_bundle(
        bp,
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
    )
    order = next(o for o in bundle.visual_orders if o.visual.attaches_to == "diagram_sequence")

    assert order.visual.mode == "diagram"
    assert order.visual.frames == []


def test_compile_orders_series_uses_legacy_frame_fallback_for_old_blueprints() -> None:
    bp = _load_example("james_mitosis_booklet.json")
    sec = next(s for s in bp.sections if s.section_id == "diagram_sequence")
    comp = next(c for c in sec.components if c.component == "diagram_series")
    comp.content_intent = (
        "Three panels: Panel 1 - Prophase chromosomes condense. "
        "Panel 2 - Metaphase chromosomes align at equator. "
        "Panel 3 - Anaphase chromatids separate."
    )
    vis = next(v for v in bp.visual_strategy.visuals if v.section_id == "diagram_sequence")
    vis.frames = []

    bundle = compile_execution_bundle(
        bp,
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
    )
    order = next(o for o in bundle.visual_orders if o.visual.attaches_to == "diagram_sequence")

    assert order.visual.mode == "diagram_series"
    assert len(order.visual.frames) == 3


def test_compile_orders_series_prefers_structured_frames_over_legacy_markers() -> None:
    bp = _load_example("james_mitosis_booklet.json")
    sec = next(s for s in bp.sections if s.section_id == "diagram_sequence")
    comp = next(c for c in sec.components if c.component == "diagram_series")
    comp.content_intent = (
        "Three panels: Panel 1 - Legacy one. "
        "Panel 2 - Legacy two. "
        "Panel 3 - Legacy three."
    )
    vis = next(v for v in bp.visual_strategy.visuals if v.section_id == "diagram_sequence")

    bundle = compile_execution_bundle(
        bp,
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
    )
    order = next(o for o in bundle.visual_orders if o.visual.attaches_to == "diagram_sequence")

    assert order.visual.mode == "diagram_series"
    assert len(order.visual.frames) == len(vis.frames)
    assert all("Legacy" not in frame.description for frame in order.visual.frames)


def test_compile_orders_dependency_uses_source_question_ids() -> None:
    bp = _load_example("amara_compound_area.json")
    order = next(
        o
        for o in compile_execution_bundle(
            bp,
            generation_id="g1",
            blueprint_id="b1",
            template_id="guided-concept-path",
        ).visual_orders
        if o.visual.attaches_to == "practice"
    )

    assert order.dependency == "question_text"
    assert order.visual.must_show == ["clear compound outlines", "dimension labels where needed"]

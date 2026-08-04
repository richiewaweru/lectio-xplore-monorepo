from __future__ import annotations

import json
from pathlib import Path

from contracts.lectio import get_section_field_for_component
from v3_blueprint.models import ProductionBlueprint
from v3_execution.assembly.section_builder import V3SectionBuilder
from v3_execution.component_aliases import canonical_component_id
from v3_execution.models import GeneratedComponentBlock, GeneratedQuestionBlock, GeneratedVisualBlock


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _component_payload(field: str, seed: str) -> dict:
    if field == "explanation":
        return {"body": seed, "emphasis": []}
    if field == "worked_example":
        return {
            "title": seed,
            "solution": [{"step": "", "latex": "", "explain": "", "diagramRef": []}],
            "answer": "",
        }
    if field == "summary":
        return {"paragraphs": [seed], "key_points": [], "cta": {}}
    if field == "hook":
        return {"headline": seed, "body": seed, "anchor": "anchor"}
    if field == "practice":
        return {"introduction": "", "items": [], "footnote": "", "diagram": None}
    return {"detail": seed}


def _build_component_blocks(blueprint: ProductionBlueprint) -> list[GeneratedComponentBlock]:
    out: list[GeneratedComponentBlock] = []
    for section in blueprint.sections:
        for idx, component in enumerate(section.components):
            component_id = canonical_component_id(component.component)
            field = get_section_field_for_component(component_id) or "explanation"
            out.append(
                GeneratedComponentBlock(
                    block_id=f"{section.section_id}-{component_id}",
                    section_id=section.section_id,
                    component_id=component_id,
                    section_field=field,
                    position=idx,
                    data=_component_payload(field, component.content_intent),
                    source_work_order_id=f"wo-{section.section_id}",
                )
            )
    return out


def _build_question_blocks(blueprint: ProductionBlueprint) -> list[GeneratedQuestionBlock]:
    out: list[GeneratedQuestionBlock] = []
    for q in blueprint.question_plan:
        out.append(
            GeneratedQuestionBlock(
                question_id=q.question_id,
                section_id=q.section_id,
                difficulty=q.temperature,
                data={
                    "question": q.prompt or q.question_id,
                    "difficulty": q.temperature,
                    "hints": [],
                    "problem_type": "open",
                },
                expected_answer=q.expected_answer,
                source_work_order_id=f"wo-q-{q.section_id}",
                diagram_required=q.diagram_required,
            )
        )
    return out


def _build_visual_blocks(blueprint: ProductionBlueprint) -> list[GeneratedVisualBlock]:
    out: list[GeneratedVisualBlock] = []
    for idx, sec in enumerate(blueprint.sections):
        out.append(
            GeneratedVisualBlock(
                visual_id=f"v-{idx}",
                attaches_to=sec.section_id,
                mode="diagram",
                image_url=f"https://cdn.example/{sec.section_id}.png",
                source_work_order_id=f"wo-v-{sec.section_id}",
                caption=sec.title,
                alt_text=sec.title,
            )
        )
    return out


def test_all_sections_complete_when_all_outputs_present() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    sections, warnings, diagnostics = builder.build_sections(
        bp,
        _build_component_blocks(bp),
        _build_question_blocks(bp),
        _build_visual_blocks(bp),
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert len(sections) == len(bp.sections)
    assert not warnings
    assert all(d.status == "complete" for d in diagnostics)


def test_missing_visual_marks_section_incomplete_but_keeps_renderable_sections() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    visuals = _build_visual_blocks(bp)
    visuals = visuals[1:]
    sections, warnings, diagnostics = builder.build_sections(
        bp,
        _build_component_blocks(bp),
        _build_question_blocks(bp),
        visuals,
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert sections
    assert warnings
    assert any(d.status == "incomplete" for d in diagnostics)


def test_missing_component_marks_section_incomplete() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    components = _build_component_blocks(bp)
    components = components[1:]
    sections, warnings, diagnostics = builder.build_sections(
        bp,
        components,
        _build_question_blocks(bp),
        _build_visual_blocks(bp),
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert sections
    assert warnings
    assert any(d.missing_components for d in diagnostics)


def test_ready_visual_delivered_component_does_not_emit_missing_component_warning() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    components = [
        block for block in _build_component_blocks(bp) if block.component_id != "diagram-block"
    ]

    _sections, warnings, diagnostics = builder.build_sections(
        bp,
        components,
        _build_question_blocks(bp),
        _build_visual_blocks(bp),
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert not any("Missing component output for diagram-block" in warning for warning in warnings)
    assert all("diagram-block" not in d.missing_components for d in diagnostics)


def test_flagged_visual_is_placed_in_diagram_bucket() -> None:
    bp = _load_example("amara_compound_area.json")
    section_id = next(section.section_id for section in bp.sections if section.visual_required)
    builder = V3SectionBuilder()
    components = [
        block for block in _build_component_blocks(bp) if block.component_id != "diagram-block"
    ]
    visuals = [visual for visual in _build_visual_blocks(bp) if visual.attaches_to != section_id]
    visuals.append(
        GeneratedVisualBlock(
            visual_id="v-flagged",
            attaches_to=section_id,
            mode="diagram",
            image_url="https://cdn.example/flagged.png",
            source_work_order_id="wo-v-flagged",
            status="flagged_quality",
            qc_reasons=["label is faint"],
            component_id="diagram-block",
        )
    )

    sections, warnings, diagnostics = builder.build_sections(
        bp,
        components,
        _build_question_blocks(bp),
        visuals,
        template_id="guided-concept-path",
        answer_key=None,
    )

    bucket = next(section for section in sections if section["section_id"] == section_id)
    assert bucket["diagram"]["image_url"] == "https://cdn.example/flagged.png"
    assert not any("was not delivered" in warning for warning in warnings)
    assert next(d for d in diagnostics if d.section_id == section_id).status == "complete"


def test_failed_visual_delivered_component_gets_visual_delivery_warning() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    failed_section = next(section.section_id for section in bp.sections if section.visual_required)
    components = [
        block for block in _build_component_blocks(bp) if block.component_id != "diagram-block"
    ]
    visuals = [
        visual for visual in _build_visual_blocks(bp) if visual.attaches_to != failed_section
    ]
    visuals.append(
        GeneratedVisualBlock(
            visual_id="v-failed",
            attaches_to=failed_section,
            mode="diagram",
            source_work_order_id="wo-v-failed",
            status="failed",
            error_message="provider timeout",
            component_id="diagram-block",
        )
    )

    _sections, warnings, diagnostics = builder.build_sections(
        bp,
        components,
        _build_question_blocks(bp),
        visuals,
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert any("was not delivered (status: failed)" in warning for warning in warnings)
    failed_diag = next(d for d in diagnostics if d.section_id == failed_section)
    assert "diagram-block" not in failed_diag.missing_components
    assert failed_diag.status == "incomplete"


def test_one_section_can_fail_without_collapsing_whole_pack() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    failed_section = bp.sections[0].section_id
    components = [c for c in _build_component_blocks(bp) if c.section_id != failed_section]
    visuals = [v for v in _build_visual_blocks(bp) if v.attaches_to != failed_section]
    questions = [q for q in _build_question_blocks(bp) if q.section_id != failed_section]
    sections, warnings, diagnostics = builder.build_sections(
        bp,
        components,
        questions,
        visuals,
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert len(sections) < len(bp.sections)
    assert warnings
    failed_diag = next(d for d in diagnostics if d.section_id == failed_section)
    assert failed_diag.status in {"failed", "incomplete"}
    assert not failed_diag.renderable


def test_no_sections_assemble_when_no_component_outputs_exist() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    sections, warnings, diagnostics = builder.build_sections(
        bp,
        [],
        [],
        [],
        template_id="guided-concept-path",
        answer_key=None,
    )

    assert sections == []
    assert warnings
    assert all(not d.renderable for d in diagnostics)


def test_series_visual_takes_precedence_over_singleton_diagram() -> None:
    bp = _load_example("james_mitosis_booklet.json")
    section_id = "diagram_sequence"
    builder = V3SectionBuilder()

    sections, _warnings, _diagnostics = builder.build_sections(
        bp,
        [],
        [],
        [
            GeneratedVisualBlock(
                visual_id="vs-0",
                attaches_to=section_id,
                mode="diagram_series",
                image_url="https://cdn.example/frame-1.png",
                frame_index=0,
                caption="Frame 1",
                source_work_order_id="wo-series",
            ),
            GeneratedVisualBlock(
                visual_id="vs-1",
                attaches_to=section_id,
                mode="diagram_series",
                image_url="https://cdn.example/frame-2.png",
                frame_index=1,
                caption="Frame 2",
                source_work_order_id="wo-series",
            ),
            GeneratedVisualBlock(
                visual_id="vd-0",
                attaches_to=section_id,
                mode="diagram",
                image_url="https://cdn.example/singleton.png",
                caption="Singleton",
                source_work_order_id="wo-singleton",
            ),
        ],
        template_id="guided-concept-path",
        answer_key=None,
    )

    bucket = next(s for s in sections if s["section_id"] == section_id)
    assert "diagram_series" in bucket
    assert "diagram" not in bucket
    assert len(bucket["diagram_series"]["diagrams"]) == 2


def test_compare_visuals_render_through_singleton_diagram_bucket() -> None:
    bp = _load_example("amara_compound_area.json")
    section_id = bp.sections[0].section_id
    builder = V3SectionBuilder()

    sections, _warnings, _diagnostics = builder.build_sections(
        bp,
        [],
        [],
        [
            GeneratedVisualBlock(
                visual_id="vc-0",
                attaches_to=section_id,
                mode="diagram_compare",
                image_url="https://cdn.example/compare.png",
                caption="Compare view",
                alt_text="Compare view",
                component_id="diagram-compare",
                source_work_order_id="wo-compare",
            )
        ],
        template_id="guided-concept-path",
        answer_key=None,
    )

    bucket = next(s for s in sections if s["section_id"] == section_id)
    assert bucket["diagram"]["image_url"] == "https://cdn.example/compare.png"
    assert "diagram_compare" not in bucket


def test_component_order_metadata_matches_emitted_component_sequence() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    sections, _warnings, _diagnostics = builder.build_sections(
        bp,
        _build_component_blocks(bp),
        _build_question_blocks(bp),
        _build_visual_blocks(bp),
        template_id="guided-concept-path",
        answer_key=None,
    )
    first = sections[0]
    expected_fields: list[str] = []
    expected_positions: dict[str, int] = {}
    for component in bp.sections[0].components:
        field = get_section_field_for_component(canonical_component_id(component.component)) or "explanation"
        if field in first and field not in expected_positions:
            expected_positions[field] = len(expected_fields)
            expected_fields.append(field)

    assert first["_component_order"] == expected_fields
    assert first["_component_positions"] == expected_positions


def test_component_order_metadata_excludes_missing_component_fields() -> None:
    bp = _load_example("amara_compound_area.json")
    builder = V3SectionBuilder()
    all_components = _build_component_blocks(bp)
    removed = all_components[0]
    components = all_components[1:]

    sections, _warnings, _diagnostics = builder.build_sections(
        bp,
        components,
        _build_question_blocks(bp),
        _build_visual_blocks(bp),
        template_id="guided-concept-path",
        answer_key=None,
    )
    section = next(s for s in sections if s["section_id"] == removed.section_id)
    order = section["_component_order"]
    positions = section["_component_positions"]

    assert removed.section_field not in order
    assert removed.section_field not in positions
    assert positions == {field: idx for idx, field in enumerate(order)}

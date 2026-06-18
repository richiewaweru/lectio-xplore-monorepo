from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from generation import service as generation_service
from planning import routes as planning_routes
from planning.models import PlanningSectionPlan
from pipeline.nodes import content_generator as content_generator_mod
from pipeline.nodes import curriculum_planner as curriculum_planner_mod
from pipeline.prompts.content import (
    _section_plan_policy_block,
    _visual_context_block,
    build_content_user_prompt,
    build_core_user_prompt,
)
from pipeline.prompts.curriculum import build_curriculum_system_prompt
from pipeline.state import TextbookPipelineState
from pipeline.types.content_phases import CoreContent, EnrichmentPhaseContent, PracticePhaseContent
from pipeline.types.requests import BlockVisualPlacement, GenerationMode, PipelineRequest, SectionPlan
from pipeline.types.section_content import (
    DefinitionContent,
    ExplanationContent,
    HookHeroContent,
    PracticeContent,
    PracticeHint,
    PracticeProblem,
    SectionHeaderContent,
    WhatNextContent,
)
from pipeline.types.template_contract import GenerationGuidance, TemplateContractSummary


class FakeAgent:
    def __init__(self, *, model, output_type, system_prompt) -> None:
        self.model = model
        self.output_type = output_type
        self.system_prompt = system_prompt


def _guidance() -> GenerationGuidance:
    return GenerationGuidance(
        tone="clear",
        pacing="steady",
        chunking="medium",
        emphasis="explanation first",
        avoid=["long prose"],
    )


def _contract(**overrides) -> TemplateContractSummary:
    defaults = dict(
        id="guided-concept-path",
        name="Guided Concept Path",
        family="guided-concept",
        intent="introduce-concept",
        tagline="test",
        lesson_flow=["Hook", "Explain", "Practice"],
        required_components=[
            "section-header",
            "hook-hero",
            "explanation-block",
            "practice-stack",
            "what-next-bridge",
        ],
        optional_components=["definition-card", "diagram-block"],
        default_behaviours={},
        generation_guidance=_guidance(),
        best_for=[],
        not_ideal_for=[],
        learner_fit=["general"],
        subjects=["science"],
        interaction_level="medium",
        allowed_presets=["blue-classroom"],
    )
    defaults.update(overrides)
    return TemplateContractSummary(**defaults)


def _request(**overrides) -> PipelineRequest:
    defaults = dict(
        context="Photosynthesis basics",
        subject="Science",
        grade_band="secondary",
        template_id="guided-concept-path",
        preset_id="blue-classroom",
        learner_fit="general",
        section_count=2,
        mode=GenerationMode.BALANCED,
        generation_id="gen-policy",
    )
    defaults.update(overrides)
    return PipelineRequest(**defaults)


def _section_plan(**overrides) -> SectionPlan:
    defaults = dict(
        section_id="s-01",
        title="Photosynthesis basics",
        position=1,
        focus="Introduce the core idea.",
        role="intro",
        required_components=[
            "section-header",
            "hook-hero",
            "explanation-block",
            "practice-stack",
            "what-next-bridge",
            "definition-card",
        ],
        optional_components=[],
    )
    defaults.update(overrides)
    return SectionPlan(**defaults)


def _base_state(**overrides) -> TextbookPipelineState:
    defaults = dict(
        request=_request(),
        contract=_contract(),
        current_section_id="s-01",
        current_section_plan=_section_plan(),
        curriculum_outline=[_section_plan(), _section_plan(section_id="s-02", title="Practice plants", position=2)],
    )
    defaults.update(overrides)
    return TextbookPipelineState(**defaults)


def test_section_models_accept_payloads_without_legacy_visual_fields() -> None:
    plan = SectionPlan.model_validate(
        {
            "section_id": "s-01",
            "title": "Intro",
            "position": 1,
            "focus": "Set the scene.",
        }
    )
    planning_section = PlanningSectionPlan.model_validate(
        {
            "id": "section-1",
            "order": 1,
            "role": "intro",
            "title": "Intro",
            "selected_components": ["hook-hero"],
            "rationale": "Lead with context.",
        }
    )

    assert plan.terms_to_define == []
    assert plan.terms_assumed == []
    assert plan.practice_target is None
    assert plan.visual_placements == []
    assert planning_section.terms_to_define == []
    assert planning_section.terms_assumed == []
    assert planning_section.practice_target is None
    assert planning_section.visual_placements == []


def test_planning_to_pipeline_adapters_forward_placement_fields() -> None:
    planning_section = PlanningSectionPlan(
        id="section-1",
        order=1,
        role="intro",
        title="Intro",
        selected_components=["hook-hero"],
        rationale="Lead with context.",
        terms_to_define=["chlorophyll"],
        terms_assumed=["cell"],
        practice_target="identify chlorophyll's role in absorbing light",
        visual_placements=[
            BlockVisualPlacement(
                block="explanation",
                slot_type="diagram",
                hint="Use a labeled leaf diagram.",
            )
        ],
    )

    planning_route_plan = planning_routes._pipeline_section_from_planning(
        planning_section,
        always_present=[],
        generation_mode=GenerationMode.BALANCED,
    )
    generation_service_plan = generation_service._pipeline_section_from_planning(
        planning_section,
        always_present=[],
        generation_mode=GenerationMode.BALANCED,
    )

    assert planning_route_plan.terms_to_define == ["chlorophyll"]
    assert planning_route_plan.terms_assumed == ["cell"]
    assert planning_route_plan.practice_target == "identify chlorophyll's role in absorbing light"
    assert planning_route_plan.visual_placements == planning_section.visual_placements
    assert planning_route_plan.needs_diagram is True
    assert generation_service_plan.visual_placements == planning_section.visual_placements
    assert generation_service_plan.needs_diagram is True


def test_planning_to_pipeline_adapters_derive_needs_diagram_only_from_placements() -> None:
    planning_section = PlanningSectionPlan(
        id="section-1",
        order=1,
        role="intro",
        title="Intro",
        selected_components=["diagram-block"],
        visual_policy={
            "required": True,
            "intent": "explain_structure",
            "mode": "svg",
            "goal": "Show the structure clearly.",
            "style_notes": "Use a clean diagram.",
        },
        rationale="Lead with context.",
        visual_placements=[],
    )

    planning_route_plan = planning_routes._pipeline_section_from_planning(
        planning_section,
        always_present=[],
        generation_mode=GenerationMode.BALANCED,
    )
    generation_service_plan = generation_service._pipeline_section_from_planning(
        planning_section,
        always_present=[],
        generation_mode=GenerationMode.BALANCED,
    )

    assert planning_route_plan.needs_diagram is False
    assert planning_route_plan.diagram_policy == "allowed"
    assert generation_service_plan.needs_diagram is False
    assert generation_service_plan.diagram_policy == "allowed"


def test_curriculum_prompts_no_longer_delegate_needs_diagram_to_llm() -> None:
    system_prompt = build_curriculum_system_prompt(
        template_id="guided-concept-path",
        template_name="Guided Concept Path",
        template_family="guided-concept",
    )

    assert "needs_diagram" not in system_prompt


def test_policy_block_reports_visual_placement_count() -> None:
    plan = _section_plan(
        terms_to_define=["chlorophyll"],
        terms_assumed=["leaf"],
        practice_target="apply the chlorophyll definition",
        visual_placements=[
            BlockVisualPlacement(
                block="explanation",
                slot_type="diagram_series",
                hint="Sequence of light capture stages.",
            )
        ],
    )

    policy = _section_plan_policy_block(plan)

    assert "terms_to_define: chlorophyll" in policy
    assert "terms_assumed: leaf" in policy
    assert "practice_target: apply the chlorophyll definition" in policy
    assert "visual_placements: 1 placement(s)" in policy


def test_visual_context_block_for_core_without_placements_forbids_visual_references() -> None:
    visual = _visual_context_block(_section_plan(), phase="core")
    assert "NO diagram or visual element" in visual
    assert "Do NOT reference" in visual


@pytest.mark.parametrize(
    ("slot_type", "expected"),
    [
        ("diagram", "diagram alongside the explanation"),
        ("diagram_series", "diagram series above the explanation"),
        ("diagram_compare", "diagram series above the explanation"),
    ],
)
def test_visual_context_uses_placements_for_core_and_monolithic_prompts(
    slot_type: str,
    expected: str,
) -> None:
    plan = _section_plan(
        visual_placements=[
            BlockVisualPlacement(block="explanation", slot_type=slot_type, hint="Test placement.")
        ]
    )

    monolithic = build_content_user_prompt(
        section_plan=plan,
        subject="Science",
        context="Photosynthesis",
        grade_band="secondary",
        learner_fit="general",
        template_id="guided-concept-path",
    )
    core = build_core_user_prompt(
        section_plan=plan,
        subject="Science",
        context="Photosynthesis",
        grade_band="secondary",
        learner_fit="general",
        template_id="guided-concept-path",
    )

    assert expected in monolithic
    assert expected in core


def test_visual_context_block_targets_only_selected_practice_problems() -> None:
    plan = _section_plan(
        visual_placements=[
            BlockVisualPlacement(
                block="practice",
                slot_type="diagram",
                sizing="compact",
                hint="Use a compact grid diagram.",
                problem_indices=[0, 2],
            )
        ]
    )

    visual = _visual_context_block(plan, phase="practice")

    assert "problems 1 and 3" in visual
    assert "Only those specific problems may say 'the diagram'" in visual


def test_visual_context_block_forbids_practice_references_when_section_diagram_is_elsewhere() -> None:
    plan = _section_plan(
        visual_placements=[
            BlockVisualPlacement(block="explanation", slot_type="diagram", hint="Use a core diagram.")
        ]
    )

    visual = _visual_context_block(plan, phase="practice")

    assert "appears elsewhere in the section" in visual
    assert "Describe every scenario in words" in visual


def test_visual_context_block_allows_only_worked_example_visual_references_in_enrichment() -> None:
    plan = _section_plan(
        visual_placements=[
            BlockVisualPlacement(
                block="worked_example",
                slot_type="diagram",
                sizing="compact",
                hint="Use a compact worked-example diagram.",
            )
        ]
    )

    visual = _visual_context_block(plan, phase="enrichment")

    assert "worked example may include its own compact diagram" in visual
    assert "All other enrichment content must avoid visual references." in visual


@pytest.mark.asyncio
async def test_curriculum_planner_seeded_outline_preserves_planning_enrichment_and_routes_visuals(monkeypatch) -> None:
    outline = [
        _section_plan(
            section_id="s-01",
            title="Intro plants",
            position=1,
            role="intro",
            required_components=["diagram-block"],
            terms_to_define=["chlorophyll"],
            practice_target="name chlorophyll and what it does",
        ),
        _section_plan(
            section_id="s-02",
            title="Practice plants",
            position=2,
            role="process",
            required_components=["diagram-series"],
            terms_assumed=["chlorophyll"],
            practice_target="apply chlorophyll knowledge to explain leaf colour",
        ),
    ]
    state = _base_state(
        request=_request(section_plans=outline),
        current_section_plan=None,
    )

    monkeypatch.setattr(curriculum_planner_mod, "Agent", FakeAgent)
    async def unexpected_run_llm(**kwargs):
        raise AssertionError("seeded outlines should not call curriculum enrichment LLM")

    monkeypatch.setattr(curriculum_planner_mod, "run_llm", unexpected_run_llm)
    monkeypatch.setattr(curriculum_planner_mod, "get_node_text_model", lambda *args, **kwargs: "fast-model")
    published_events: list[object] = []
    monkeypatch.setattr(
        curriculum_planner_mod,
        "publish_runtime_event",
        lambda generation_id, event: published_events.append(event),
    )

    result = await curriculum_planner_mod.curriculum_planner(state)

    enriched = result["curriculum_outline"]
    assert enriched[0].terms_to_define == ["chlorophyll"]
    assert enriched[1].terms_assumed == ["chlorophyll"]
    assert enriched[0].practice_target == "name chlorophyll and what it does"
    assert enriched[1].practice_target == "apply chlorophyll knowledge to explain leaf colour"
    assert enriched[0].visual_placements[0].slot_type == "diagram"
    assert enriched[1].visual_placements[0].slot_type == "diagram_series"
    assert enriched[0].needs_diagram is True
    assert enriched[1].needs_diagram is True
    planner_event = next(event for event in published_events if event.type == "curriculum_planned")
    assert "visual_commitment" not in planner_event.runtime_curriculum_outline[0].model_dump()
    assert planner_event.planner_trace_sections[0].visual_placements_count == 1


@pytest.mark.asyncio
async def test_curriculum_planner_fresh_path_routes_visual_placements_after_llm_output(monkeypatch) -> None:
    state = _base_state(
        request=_request(section_plans=None),
        current_section_plan=None,
        curriculum_outline=None,
    )

    async def fake_run_llm(**kwargs):
        return SimpleNamespace(
            output=curriculum_planner_mod.CurriculumOutput(
                sections=[
                    _section_plan(
                        section_id="s-01",
                        position=1,
                        required_components=["diagram-block"],
                        terms_to_define=["chlorophyll"],
                        practice_target="name the role of chlorophyll",
                    ),
                    _section_plan(
                        section_id="s-02",
                        position=2,
                        title="Repeat chlorophyll",
                        required_components=["diagram-series"],
                        role="process",
                        terms_to_define=["Chlorophyll"],
                        practice_target="spot the repeated term",
                    ),
                ]
            )
        )

    monkeypatch.setattr(curriculum_planner_mod, "Agent", FakeAgent)
    monkeypatch.setattr(curriculum_planner_mod, "run_llm", fake_run_llm)
    monkeypatch.setattr(curriculum_planner_mod, "get_node_text_model", lambda *args, **kwargs: "fast-model")
    published_events: list[object] = []
    monkeypatch.setattr(
        curriculum_planner_mod,
        "publish_runtime_event",
        lambda generation_id, event: published_events.append(event),
    )

    result = await curriculum_planner_mod.curriculum_planner(state)

    section = result["curriculum_outline"][0]
    assert section.visual_placements[0].slot_type == "diagram"
    assert section.needs_diagram is True
    planner_event = next(event for event in published_events if event.type == "curriculum_planned")
    assert len(planner_event.duplicate_term_warnings) == 1
    assert "visual_commitment" not in planner_event.runtime_curriculum_outline[0].model_dump()
    assert planner_event.planner_trace_sections[0].visual_placements_count == 1


def test_warn_duplicate_terms_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    sections = [
        _section_plan(section_id="s-01", terms_to_define=["chlorophyll"]),
        _section_plan(section_id="s-02", position=2, terms_to_define=["Chlorophyll"]),
    ]

    with caplog.at_level(logging.WARNING):
        warnings = curriculum_planner_mod._warn_duplicate_terms(sections, "gen-dup")

    assert len(warnings) == 1
    assert "Duplicate term assignment in curriculum plan" in warnings[0]


@pytest.mark.asyncio
async def test_phased_content_generator_includes_phase_aware_visual_context_in_practice_prompt(monkeypatch) -> None:
    captured_prompts: dict[str, str] = {}

    async def fake_run_llm(**kwargs):
        captured_prompts[kwargs["node"]] = kwargs["user_prompt"]
        node = kwargs["node"]
        if node == "content_generator_core":
            return SimpleNamespace(
                output=CoreContent(
                    section_id="s-01",
                    template_id="guided-concept-path",
                    header=SectionHeaderContent(
                        title="Photosynthesis basics",
                        subject="Science",
                        grade_band="secondary",
                    ),
                    hook=HookHeroContent(
                        headline="Why leaves matter",
                        body="Leaves capture light energy.",
                        anchor="photosynthesis",
                    ),
                    explanation=ExplanationContent(
                        body="Plants use chlorophyll to capture light.",
                        emphasis=["chlorophyll"],
                    ),
                )
            )
        if node == "content_generator_practice":
            return SimpleNamespace(
                output=PracticePhaseContent(
                    practice=PracticeContent(
                        problems=[
                            PracticeProblem(
                                difficulty="warm",
                                question="Why would a shaded leaf make less food?",
                                hints=[PracticeHint(level=1, text="Think about light capture.")],
                            )
                        ]
                    ),
                    what_next=WhatNextContent(
                        body="Next we connect this to plant structure.",
                        next="Plant structure",
                    ),
                )
            )
        if node == "content_generator_enrichment":
            return SimpleNamespace(
                output=EnrichmentPhaseContent(
                    definition=DefinitionContent(
                        term="chlorophyll",
                        formal="A pigment that absorbs light energy in photosynthesis.",
                        plain="The green substance that helps plants capture light.",
                    )
                )
            )
        raise AssertionError(f"Unexpected node {node}")

    monkeypatch.setattr(content_generator_mod, "Agent", FakeAgent)
    monkeypatch.setattr(content_generator_mod, "run_llm", fake_run_llm)
    monkeypatch.setattr(content_generator_mod, "get_node_text_model", lambda *args, **kwargs: "standard-model")

    state = _base_state(
        current_section_plan=_section_plan(
            visual_placements=[
                BlockVisualPlacement(
                    block="explanation",
                    slot_type="diagram",
                    hint="Use a core diagram only.",
                )
            ],
            terms_to_define=["chlorophyll"],
            practice_target="apply chlorophyll knowledge to explain light capture",
        )
    )

    result = await content_generator_mod.content_generator(state)

    assert "content_generator" in result["completed_nodes"]
    assert "appears elsewhere in the section" in captured_prompts["content_generator_practice"]
    assert "Describe every scenario in words" in captured_prompts["content_generator_practice"]
    assert "practice_target: apply chlorophyll knowledge to explain light capture" in captured_prompts[
        "content_generator_practice"
    ]

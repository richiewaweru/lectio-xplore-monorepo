from __future__ import annotations

from types import SimpleNamespace

import pytest

from pipeline.graph import retry_media_frame
from pipeline.media.types import MediaPlan, VisualFrame, VisualSlot
from pipeline.nodes import content_generator as content_generator_module
from pipeline.nodes import process_section as process_section_module
from pipeline.nodes import section_assembler as section_assembler_module
from pipeline.state import QCReport, RerenderRequest, StyleContext, TextbookPipelineState
from pipeline.types.content_phases import (
    CoreContent,
    EnrichmentPhaseContent,
    PracticePhaseContent,
)
from pipeline.types.requests import PipelineRequest, SectionPlan
from pipeline.types.section_content import (
    CalloutBlockContent,
    DiagramContent,
    ExplanationContent,
    HookHeroContent,
    InteractionSpec,
    PracticeContent,
    PracticeHint,
    PracticeProblem,
    SectionContent,
    SectionHeaderContent,
    SimulationContent,
    SummaryBlockContent,
    SummaryItem,
    WhatNextContent,
)
from pipeline.types.template_contract import (
    GenerationGuidance,
    TemplateContractSummary,
)


class DummyAgent:
    def __init__(self, *args, **kwargs) -> None:
        _ = (args, kwargs)


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
        optional_components=[
            "callout-block",
            "definition-card",
            "diagram-block",
            "simulation-block",
            "summary-block",
        ],
        default_behaviours={},
        generation_guidance=_guidance(),
        best_for=[],
        not_ideal_for=[],
        learner_fit=["general"],
        subjects=["mathematics"],
        interaction_level="medium",
        allowed_presets=["blue-classroom"],
    )
    defaults.update(overrides)
    return TemplateContractSummary(**defaults)


def _request(**overrides) -> PipelineRequest:
    defaults = dict(
        topic="Introduction to derivatives",
        subject="Mathematics",
        grade_band="secondary",
        template_id="guided-concept-path",
        preset_id="blue-classroom",
        learner_fit="general",
        section_count=1,
        generation_id="gen-test",
    )
    defaults.update(overrides)
    return PipelineRequest(**defaults)


def _plan(sid: str = "s-01", *, required_components: list[str] | None = None) -> SectionPlan:
    return SectionPlan(
        section_id=sid,
        title=f"Section {sid}",
        position=1,
        focus="Teach the core idea clearly.",
        needs_diagram=True,
        required_components=required_components or [],
    )


def _style_context() -> StyleContext:
    return StyleContext(
        preset_id="blue-classroom",
        palette="navy, sky, parchment",
        surface_style="crisp",
        density="standard",
        typography="standard",
        template_id="guided-concept-path",
        template_family="guided-concept",
        interaction_level="medium",
        grade_band="secondary",
        learner_fit="general",
    )


def _section(sid: str = "s-01") -> SectionContent:
    return SectionContent(
        section_id=sid,
        template_id="guided-concept-path",
        header=SectionHeaderContent(
            title=f"Section {sid}",
            subject="Mathematics",
            grade_band="secondary",
        ),
        hook=HookHeroContent(
            headline="Why this matters",
            body="A compelling hook body",
            anchor="derivatives",
        ),
        explanation=ExplanationContent(
            body="The explanation of the concept",
            emphasis=["key point 1", "key point 2"],
        ),
        practice=PracticeContent(
            problems=[
                PracticeProblem(
                    difficulty="warm",
                    question="What is 2+2?",
                    hints=[PracticeHint(level=1, text="Think about it")],
                )
            ]
        ),
        what_next=WhatNextContent(body="Next we cover integrals", next="Integrals"),
    )


def _state(**overrides) -> TextbookPipelineState:
    defaults = dict(
        request=_request(),
        contract=_contract(),
        current_section_id="s-01",
        current_section_plan=_plan("s-01"),
        curriculum_outline=[_plan("s-01")],
        style_context=_style_context(),
    )
    defaults.update(overrides)
    return TextbookPipelineState(**defaults)


def _interaction_spec() -> InteractionSpec:
    return InteractionSpec(
        type="graph_slider",
        goal="Understand the idea",
        anchor_content={"headline": "Hook", "body": "Explain"},
        context={
            "learner_level": "allowed",
            "template_id": "guided-concept-path",
            "color_mode": "light",
            "accent_color": "#17417a",
            "surface_color": "#f7fbff",
            "font_mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        },
        dimensions={
            "width": "100%",
            "height": 420,
            "resizable": True,
        },
        print_translation="static_diagram",
    )


def _rerender_state(**overrides) -> TextbookPipelineState:
    """State with a pending rerender — forces monolithic content_generator path."""
    return _state(
        rerender_requests={
            "s-01": RerenderRequest(
                section_id="s-01",
                block_type="hook",
                reason="Weak hook needs improvement",
            )
        },
        **overrides,
    )


@pytest.mark.asyncio
async def test_content_generator_validation_failure_surfaces_without_auto_repair(monkeypatch) -> None:
    calls: list[str] = []
    events: list[object] = []

    async def fake_run_llm(*, node: str, **kwargs):
        _ = kwargs
        calls.append(node)
        raise RuntimeError("Exceeded maximum retries (1) for output validation")

    monkeypatch.setattr(content_generator_module, "Agent", DummyAgent)
    monkeypatch.setattr(content_generator_module, "get_node_text_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(content_generator_module, "run_llm", fake_run_llm)
    monkeypatch.setattr(content_generator_module, "publish_runtime_event", lambda generation_id, event: events.append(event))

    result = await content_generator_module.content_generator(_rerender_state())

    assert "s-01" not in result["generated_sections"]
    assert result["failed_sections"]["s-01"].failed_at_node == "content_generator"
    assert result["errors"][0].node == "content_generator"
    assert [event.type for event in events] == ["section_failed"]
    assert calls == ["content_generator"]


@pytest.mark.asyncio
async def test_content_generator_persists_failed_section_after_repair_failure(monkeypatch) -> None:
    events: list[object] = []

    async def fake_run_llm(*, node: str, **kwargs):
        _ = (node, kwargs)
        raise RuntimeError("Exceeded maximum retries (1) for output validation")

    monkeypatch.setattr(content_generator_module, "Agent", DummyAgent)
    monkeypatch.setattr(content_generator_module, "get_node_text_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(content_generator_module, "run_llm", fake_run_llm)
    monkeypatch.setattr(content_generator_module, "publish_runtime_event", lambda generation_id, event: events.append(event))

    result = await content_generator_module.content_generator(_rerender_state())

    assert "generated_sections" in result
    assert "s-01" not in result["generated_sections"]
    assert result["failed_sections"]["s-01"].failed_at_node == "content_generator"
    assert result["errors"][0].node == "content_generator"
    assert [event.type for event in events] == ["section_failed"]


@pytest.mark.asyncio
async def test_content_generator_phased_generates_selected_callout_and_summary(monkeypatch) -> None:
    prompts_by_node: dict[str, str] = {}

    async def fake_run_llm(*, node: str, user_prompt: str, **kwargs):
        _ = kwargs
        prompts_by_node[node] = user_prompt
        if node == "content_generator_core":
            return SimpleNamespace(
                output=CoreContent(
                    section_id="s-01",
                    template_id="guided-concept-path",
                    header=SectionHeaderContent(
                        title="Section s-01",
                        subject="Mathematics",
                        grade_band="secondary",
                    ),
                    hook=HookHeroContent(
                        headline="Why this matters",
                        body="A compelling hook body",
                        anchor="derivatives",
                    ),
                    explanation=ExplanationContent(
                        body="The explanation of the concept",
                        emphasis=["key point 1", "key point 2"],
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
                                question="What is 2+2?",
                                hints=[PracticeHint(level=1, text="Think about it")],
                            )
                        ]
                    ),
                    what_next=WhatNextContent(body="Next we cover integrals", next="Integrals"),
                )
            )
        if node == "content_generator_enrichment":
            return SimpleNamespace(
                output=EnrichmentPhaseContent(
                    callout=CalloutBlockContent(
                        variant="tip",
                        heading="Exam tip",
                        body="Check the sign before you compare steepness.",
                    ),
                    summary=SummaryBlockContent(
                        heading="In summary",
                        items=[
                            SummaryItem(text="Slope is rise over run."),
                            SummaryItem(text="The sign tells you direction."),
                        ],
                        closing="Next we connect this to straight-line equations.",
                    ),
                )
            )
        raise AssertionError(f"Unexpected node {node}")

    monkeypatch.setattr(content_generator_module, "Agent", DummyAgent)
    monkeypatch.setattr(content_generator_module, "get_node_text_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(content_generator_module, "run_llm", fake_run_llm)

    state = _state(
        contract=_contract(),
        current_section_plan=_plan(
            "s-01",
            required_components=[
                "section-header",
                "hook-hero",
                "explanation-block",
                "practice-stack",
                "what-next-bridge",
                "callout-block",
                "summary-block",
            ],
        ),
        curriculum_outline=[
            _plan(
                "s-01",
                required_components=[
                    "section-header",
                    "hook-hero",
                    "explanation-block",
                    "practice-stack",
                    "what-next-bridge",
                    "callout-block",
                    "summary-block",
                ],
            )
        ],
    )

    result = await content_generator_module.content_generator(state)
    section = result["generated_sections"]["s-01"]

    assert section.callout is not None
    assert section.summary is not None
    assert "Generate these enrichment fields: callout, summary" in prompts_by_node["content_generator_enrichment"]


@pytest.mark.asyncio
async def test_retry_media_frame_runs_targeted_executor_and_reassembly(monkeypatch) -> None:
    captured_steps: list[str] = []

    async def fake_run_section_steps(state, *, steps, **kwargs):
        _ = (state, kwargs)
        captured_steps[:] = [name for name, _fn in steps]
        return {"completed_nodes": captured_steps}

    monkeypatch.setattr("pipeline.graph.run_section_steps", fake_run_section_steps)

    state = _state(
        generated_sections={"s-01": _section("s-01")},
        assembled_sections={"s-01": _section("s-01")},
        media_plans={
            "s-01": MediaPlan(
                section_id="s-01",
                slots=[
                    VisualSlot(
                        slot_id="diagram",
                        slot_type="diagram",
                        required=True,
                        preferred_render="svg",
                        pedagogical_intent="Explain the core idea.",
                        caption="Diagram caption",
                        frames=[
                            VisualFrame(
                                slot_id="diagram",
                                index=0,
                                label="Main view",
                                generation_goal="Render the main diagram.",
                            )
                        ],
                    )
                ],
            )
        },
        current_media_retry={
            "section_id": "s-01",
            "slot_id": "diagram",
            "slot_type": "diagram",
            "frame_key": "0",
            "frame_index": 0,
            "executor_node": "diagram_generator",
        },
    )
    result = await retry_media_frame(state)

    assert captured_steps == ["diagram_generator", "section_assembler", "qc_agent"]
    assert result["completed_nodes"] == captured_steps


@pytest.mark.asyncio
async def test_process_section_runs_phases_and_merges_outputs(monkeypatch) -> None:
    section = _section("s-01")
    section_with_diagram = section.model_copy(
        update={
            "diagram": DiagramContent(
                svg_content="<svg/>",
                caption="diagram",
                alt_text="diagram",
            )
        }
    )
    interaction_spec = _interaction_spec()
    section_with_simulation = section_with_diagram.model_copy(
        update={
            "simulation": SimulationContent(
                spec=interaction_spec,
                explanation="Interactive view",
            )
        }
    )
    media_plan = MediaPlan(
        section_id="s-01",
        slots=[
            VisualSlot(
                slot_id="diagram",
                slot_type="diagram",
                required=True,
                preferred_render="svg",
                pedagogical_intent="Show the concept visually.",
                caption="diagram",
                frames=[
                    VisualFrame(
                        slot_id="diagram",
                        index=0,
                        label="Main view",
                        generation_goal="Render the concept map.",
                    )
                ],
            ),
            VisualSlot(
                slot_id="simulation",
                slot_type="simulation",
                required=False,
                preferred_render="html_simulation",
                fallback_render="svg",
                pedagogical_intent="Let learners manipulate the idea.",
                caption="Interactive view",
                frames=[
                    VisualFrame(
                        slot_id="simulation",
                        index=0,
                        label="Interactive view",
                        generation_goal="Render the interaction.",
                    )
                ],
            ),
        ],
    )

    async def fake_run_section_steps(state, *, steps, **kwargs):
        _ = (state, kwargs)
        first = steps[0][0]
        if first == "content_generator":
            return {
                "generated_sections": {"s-01": section},
                "completed_nodes": ["content_generator", "schema_validator"],
            }
        if first == "media_planner":
            return {
                "media_plans": {"s-01": media_plan},
                "completed_nodes": ["media_planner"],
            }
        return {
            "assembled_sections": {"s-01": section_with_simulation},
            "qc_reports": {
                "s-01": QCReport(section_id="s-01", passed=True, issues=[], warnings=[])
            },
            "section_pending_assets": {"s-01": []},
            "completed_nodes": ["section_assembler", "qc_agent"],
        }

    async def fake_parallel_phase(state, *, steps, **kwargs):
        _ = (state, steps, kwargs)
        return {
            "generated_sections": {"s-01": section_with_simulation},
            "interaction_specs": {"s-01": interaction_spec},
            "diagram_outcomes": {"s-01": "success"},
            "completed_nodes": ["diagram_generator", "interaction_generator"],
        }

    monkeypatch.setattr(process_section_module, "run_section_steps", fake_run_section_steps)
    monkeypatch.setattr(process_section_module, "_run_parallel_phase", fake_parallel_phase)

    result = await process_section_module.process_section(_state())

    assert result["media_plans"]["s-01"].section_id == "s-01"
    assert result["interaction_specs"]["s-01"].type == "graph_slider"
    assert result["diagram_outcomes"]["s-01"] == "success"
    assert result["assembled_sections"]["s-01"].simulation is not None
    assert result["qc_reports"]["s-01"].passed is True
    assert result["completed_nodes"] == [
        "content_generator",
        "schema_validator",
        "media_planner",
        "diagram_generator",
        "interaction_generator",
        "section_assembler",
        "qc_agent",
    ]


@pytest.mark.asyncio
async def test_section_assembler_accepts_singular_simulation_for_simulation_block() -> None:
    section = _section("s-01").model_copy(
        update={
            "simulation": SimulationContent(
                spec=InteractionSpec(
                    **_interaction_spec().model_dump()
                ),
                explanation="Interactive view",
            )
        }
    )

    state = _state(
        generated_sections={"s-01": section},
        current_section_plan=_plan(
            "s-01",
            required_components=[
                "section-header",
                "hook-hero",
                "explanation-block",
                "practice-stack",
                "what-next-bridge",
                "simulation-block",
            ],
        ).model_copy(update={"needs_diagram": False}),
        curriculum_outline=[
            _plan(
                "s-01",
                required_components=[
                    "section-header",
                    "hook-hero",
                    "explanation-block",
                    "practice-stack",
                    "what-next-bridge",
                    "simulation-block",
                ],
            ).model_copy(update={"needs_diagram": False})
        ],
    )

    result = await section_assembler_module.section_assembler(state)

    assert "errors" not in result
    assert result["assembled_sections"]["s-01"].simulation is not None


@pytest.mark.asyncio
async def test_process_section_prefers_image_outcome_over_svg_skip(monkeypatch) -> None:
    sid = "s-01"
    section = _section(sid)
    section_with_image = section.model_copy(
        update={
            "diagram": DiagramContent(
                caption="diagram",
                alt_text="diagram",
                image_url="http://test/images/gen-test/s-01/diagram.png",
            )
        }
    )
    media_plan = MediaPlan(
        section_id=sid,
        slots=[
            VisualSlot(
                slot_id="diagram",
                slot_type="diagram",
                required=True,
                preferred_render="image",
                fallback_render="svg",
                pedagogical_intent="Needs an image",
                caption="diagram",
                frames=[
                    VisualFrame(
                        slot_id="diagram",
                        index=0,
                        generation_goal="Render the main visual as an image",
                    )
                ],
            )
        ],
    )

    async def fake_run_section_steps(state, *, steps, **kwargs):
        _ = kwargs
        first = steps[0][0]
        if first == "content_generator":
            return {
                "generated_sections": {sid: section},
                "completed_nodes": ["content_generator"],
            }
        if first == "media_planner":
            return {
                "media_plans": {sid: media_plan},
                "completed_nodes": ["media_planner"],
            }

        typed = TextbookPipelineState.parse(state)
        return {
            "assembled_sections": {sid: typed.generated_sections[sid]},
            "qc_reports": {
                sid: QCReport(section_id=sid, passed=True, issues=[], warnings=[])
            },
            "completed_nodes": ["section_assembler", "qc_agent"],
        }

    async def fake_diagram_generator(state, *, model_overrides=None, config=None):
        _ = (state, model_overrides, config)
        return {
            "diagram_outcomes": {sid: "skipped"},
            "completed_nodes": ["diagram_generator"],
        }

    async def fake_image_generator(state, *, model_overrides=None, config=None):
        _ = (state, model_overrides, config)
        return {
            "generated_sections": {sid: section_with_image},
            "diagram_outcomes": {sid: "success"},
            "completed_nodes": ["image_generator"],
        }

    monkeypatch.setattr(process_section_module, "run_section_steps", fake_run_section_steps)
    monkeypatch.setattr(process_section_module, "diagram_generator", fake_diagram_generator)
    monkeypatch.setattr(process_section_module, "image_generator", fake_image_generator)

    result = await process_section_module.process_section(_state())

    assert result["diagram_outcomes"]["s-01"] == "success"
    assert result["generated_sections"]["s-01"].diagram is not None
    assert result["generated_sections"]["s-01"].diagram.image_url == (
        "http://test/images/gen-test/s-01/diagram.png"
    )

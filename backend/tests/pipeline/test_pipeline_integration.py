"""
Phase 12 — Pipeline integration tests.

Tests the graph topology, QC routing, section assembler,
fan-out/join patterns, event bus, and preset validation.

Tests marked @pytest.mark.integration require real LLM API keys.
All other tests use deterministic state or the contracts on disk.
"""

from __future__ import annotations

import json
import warnings
from types import SimpleNamespace

import pytest
from langgraph.graph import END
from langgraph.types import Send

from pipeline.media.types import MediaPlan, VisualFrame, VisualSlot
from pipeline.state import (
    MediaFrameRetryRequest,
    PartialSectionRecord,
    PipelineError,
    QCReport,
    RerenderRequest,
    StyleContext,
    TextbookPipelineState,
)
from pipeline.types.requests import BlockVisualPlacement, PipelineRequest, SectionPlan, SectionVisualPolicy
from pipeline.types.section_content import (
    ExplanationContent,
    HookHeroContent,
    PracticeContent,
    PracticeHint,
    PracticeProblem,
    SectionContent,
    SectionHeaderContent,
    DiagramContent,
    WhatNextContent,
)
from pipeline.types.template_contract import (
    GenerationGuidance,
    TemplateContractSummary,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


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
        section_count=2,
    )
    defaults.update(overrides)
    return PipelineRequest(**defaults)


def _plan(sid: str = "s-01", position: int = 1) -> SectionPlan:
    return SectionPlan(
        section_id=sid,
        title=f"Test Section {sid}",
        position=position,
        focus="Test focus",
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
    """Minimal valid SectionContent matching guided-concept-path contract."""
    return SectionContent(
        section_id=sid,
        template_id="guided-concept-path",
        header=SectionHeaderContent(
            title="Test Section",
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
            emphasis=["key point 1"],
        ),
        practice=PracticeContent(
            problems=[
                PracticeProblem(
                    difficulty="warm",
                    question="What is 2+2?",
                    hints=[PracticeHint(level=1, text="Think about it")],
                ),
                PracticeProblem(
                    difficulty="medium",
                    question="What is the derivative of x^2?",
                    hints=[PracticeHint(level=1, text="Power rule")],
                ),
            ]
        ),
        what_next=WhatNextContent(body="Next we cover integrals", next="Integrals"),
    )


def _base_state(**overrides) -> TextbookPipelineState:
    defaults = dict(
        request=_request(),
        contract=_contract(),
        curriculum_outline=[_plan("s-01", 1), _plan("s-02", 2)],
        style_context=_style_context(),
    )
    defaults.update(overrides)
    return TextbookPipelineState(**defaults)


# ── Graph topology ───────────────────────────────────────────────────────────


class TestGraphTopology:

    def test_graph_compiles(self):
        from pipeline.graph import build_graph

        graph = build_graph()
        assert graph is not None

    def test_graph_compile_does_not_emit_config_signature_warnings(self):
        from pipeline.graph import build_graph

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            graph = build_graph()

        assert graph is not None
        config_warnings = [
            warning
            for warning in caught
            if "The 'config' parameter should be typed as" in str(warning.message)
        ]
        assert config_warnings == []

    def test_fan_out_produces_sends_per_section(self):
        from pipeline.graph import fan_out_sections

        state = _base_state(
            curriculum_outline=[
                _plan("s-01", 1),
                _plan("s-02", 2),
                _plan("s-03", 3),
            ],
        )
        sends = fan_out_sections(state)

        assert len(sends) == 3
        assert all(isinstance(s, Send) for s in sends)
        assert all(s.node == "process_section" for s in sends)
        sids = [s.arg["current_section_id"] for s in sends]
        assert sids == ["s-01", "s-02", "s-03"]

    def test_fan_out_empty_outline_returns_empty(self):
        from pipeline.graph import fan_out_sections

        state = _base_state(curriculum_outline=[])
        sends = fan_out_sections(state)
        assert sends == []

    def test_fan_out_none_outline_returns_empty(self):
        from pipeline.graph import fan_out_sections

        state = _base_state(curriculum_outline=None)
        sends = fan_out_sections(state)
        assert sends == []

    def test_fan_out_sends_carry_section_plan(self):
        from pipeline.graph import fan_out_sections

        plan = _plan("s-01", 1)
        state = _base_state(curriculum_outline=[plan])
        sends = fan_out_sections(state)

        payload = sends[0].arg
        assert payload["current_section_id"] == "s-01"
        assert payload["current_section_plan"]["section_id"] == "s-01"
        assert payload["current_section_plan"]["title"] == "Test Section s-01"


# ── QC routing ───────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Legacy auto-rerender routing expectations were removed by the v4-lock deterministic review cut.")
class TestQCRouting:
    """Pure state logic — no LLM or contracts mocking needed."""

    def test_all_pass_returns_end(self):
        state = _base_state(
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01", passed=True, issues=[], warnings=[]
                ),
                "s-02": QCReport(
                    section_id="s-02", passed=True, issues=[], warnings=[]
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert result == END

    def test_blocking_issue_returns_send_list(self):
        state = _base_state(
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Hook is weak",
                        }
                    ],
                    warnings=[],
                ),
                "s-02": QCReport(
                    section_id="s-02", passed=True, issues=[], warnings=[]
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Send)
        # Single text field failure routes to targeted retry_field
        assert result[0].node == "retry_field"
        assert result[0].arg["current_section_id"] == "s-01"

    def test_diagram_block_routes_to_retry_media_frame(self):
        state = _base_state(
            current_section_id="s-01",
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
                            pedagogical_intent="Show the concept clearly.",
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
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "diagram",
                            "message": "Diagram is malformed",
                        }
                    ],
                    warnings=[],
                )
            },
            rerender_requests={
                "s-01": RerenderRequest(
                    section_id="s-01",
                    block_type="diagram",
                    reason="Diagram is malformed",
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "retry_media_frame"
        assert result[0].arg["current_media_retry"]["slot_id"] == "diagram"

    def test_interaction_block_routes_to_retry_media_frame_and_emits_event(self, monkeypatch):
        from pipeline.events import SectionRetryQueuedEvent
        from pipeline.routers.qc_router import route_after_qc

        published: list[tuple[str, object]] = []

        def _publish(generation_id: str, event: object) -> None:
            published.append((generation_id, event))

        monkeypatch.setattr("pipeline.routers.qc_router.core_events.event_bus.publish", _publish)

        state = _base_state(
            request=_request(generation_id="gen-qc-route"),
            current_section_id="s-01",
            assembled_sections={"s-01": _section("s-01")},
            media_plans={
                "s-01": MediaPlan(
                    section_id="s-01",
                    slots=[
                        VisualSlot(
                            slot_id="simulation",
                            slot_type="simulation",
                            required=True,
                            preferred_render="html_simulation",
                            fallback_render="svg",
                            pedagogical_intent="Let learners explore the idea.",
                            caption="Interactive view",
                            frames=[
                                VisualFrame(
                                    slot_id="simulation",
                                    index=0,
                                    label="Simulation",
                                    generation_goal="Render the interaction.",
                                )
                            ],
                        )
                    ],
                )
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "simulation",
                            "message": "Simulation needs clearer controls",
                        }
                    ],
                    warnings=[],
                )
            },
        )

        result = route_after_qc(state)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "retry_media_frame"
        assert len(published) == 1
        generation_id, event = published[0]
        assert generation_id == "gen-qc-route"
        assert isinstance(event, SectionRetryQueuedEvent)
        assert event.section_id == "s-01"
        assert event.next_attempt == 2
        assert event.reason == "Simulation needs clearer controls"

    def test_multiple_sections_media_retry_produces_multiple_sends(self):
        state = _base_state(
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            media_plans={
                "s-01": MediaPlan(
                    section_id="s-01",
                    slots=[
                        VisualSlot(
                            slot_id="diagram",
                            slot_type="diagram",
                            required=True,
                            preferred_render="svg",
                            pedagogical_intent="Show concept.",
                            caption="Diagram",
                            frames=[
                                VisualFrame(
                                    slot_id="diagram",
                                    index=0,
                                    label="Main",
                                    generation_goal="Render diagram.",
                                )
                            ],
                        )
                    ],
                ),
                "s-02": MediaPlan(
                    section_id="s-02",
                    slots=[
                        VisualSlot(
                            slot_id="diagram",
                            slot_type="diagram",
                            required=True,
                            preferred_render="svg",
                            pedagogical_intent="Show concept.",
                            caption="Diagram",
                            frames=[
                                VisualFrame(
                                    slot_id="diagram",
                                    index=0,
                                    label="Main",
                                    generation_goal="Render diagram.",
                                )
                            ],
                        )
                    ],
                ),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "diagram",
                            "message": "Diagram is malformed",
                        }
                    ],
                    warnings=[],
                ),
                "s-02": QCReport(
                    section_id="s-02",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "diagram",
                            "message": "Diagram is malformed",
                        }
                    ],
                    warnings=[],
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)

        assert isinstance(result, list)
        media_sends = [send for send in result if send.node == "retry_media_frame"]
        assert len(media_sends) == 2
        section_ids = {
            send.arg["current_media_retry"]["section_id"]
            for send in media_sends
        }
        assert section_ids == {"s-01", "s-02"}

    def test_multi_field_block_routes_to_full_process_section(self):
        state = _base_state(
            current_section_id="s-01",
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Weak hook",
                        },
                        {
                            "severity": "blocking",
                            "block": "diagram",
                            "message": "Broken diagram",
                        },
                    ],
                    warnings=[],
                )
            },
            rerender_requests={
                "s-01": RerenderRequest(
                    section_id="s-01",
                    block_type="hook+diagram",
                    reason="Multiple blocking issues",
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "process_section"

    def test_max_rerenders_respected(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Still bad",
                        }
                    ],
                    warnings=[],
                ),
            },
            rerender_count={"s-01": 2},
            max_rerenders=2,
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert result == END

    def test_unrecoverable_error_returns_end(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Bad",
                        }
                    ],
                    warnings=[],
                ),
            },
            errors=[
                PipelineError(node="some_node", message="fatal", recoverable=False)
            ],
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert result == END

    def test_warning_only_issues_do_not_trigger_rerender(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "warning",
                            "block": "hook",
                            "message": "Minor issue",
                        }
                    ],
                    warnings=[],
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert result == END

    def test_multiple_sections_rerender(self):
        state = _base_state(
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Weak hook",
                        }
                    ],
                    warnings=[],
                ),
                "s-02": QCReport(
                    section_id="s-02",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "explanation",
                            "message": "Too vague",
                        }
                    ],
                    warnings=[],
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 2
        sids = {s.arg["current_section_id"] for s in result}
        assert sids == {"s-01", "s-02"}

    def test_current_section_scope_avoids_duplicate_retry_for_other_section(self):
        state = _base_state(
            current_section_id="s-02",
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Weak hook",
                        }
                    ],
                    warnings=[],
                ),
                "s-02": QCReport(
                    section_id="s-02",
                    passed=True,
                    issues=[],
                    warnings=[],
                ),
            },
            rerender_requests={
                "s-01": RerenderRequest(
                    section_id="s-01",
                    block_type="hook",
                    reason="Weak hook",
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert result == END

    def test_rerender_send_carries_section_plan(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Weak",
                        }
                    ],
                    warnings=[],
                ),
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        payload = result[0].arg
        assert payload["current_section_plan"]["section_id"] == "s-01"
        assert payload["current_section_plan"]["focus"] == "Test focus"

    def test_single_blocking_issue_routes_to_targeted_retry(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "practice",
                            "message": "Practice needs stronger progression",
                        }
                    ],
                    warnings=[],
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "retry_field"

    def test_multi_blocking_issue_escalates_to_full_rerender(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "hook",
                            "message": "Hook is weak",
                        },
                        {
                            "severity": "blocking",
                            "block": "diagram",
                            "message": "Diagram is malformed",
                        },
                    ],
                    warnings=[],
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        result = route_after_qc(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].node == "process_section"

    def test_extended_single_blocking_fields_route_to_retry_field(self):
        from pipeline.routers.qc_router import route_after_qc

        for block_type in (
            "callout",
            "summary",
            "student_textbox",
            "short_answer",
            "fill_in_blank",
            "key_fact",
            "divider",
        ):
            state = _base_state(
                assembled_sections={"s-01": _section("s-01")},
                qc_reports={
                    "s-01": QCReport(
                        section_id="s-01",
                        passed=False,
                        issues=[
                            {
                                "severity": "blocking",
                                "block": block_type,
                                "message": f"{block_type} needs improvement",
                            }
                        ],
                        warnings=[],
                    )
                },
            )

            result = route_after_qc(state)
            assert isinstance(result, list), block_type
            assert len(result) == 1, block_type
            assert result[0].node == "retry_field", block_type

    def test_extended_schema_single_field_failures_route_to_retry_field(self):
        from pipeline.routers.qc_router import route_after_qc

        field_paths = {
            "callout": "callout.body",
            "summary": "summary.items.0.text",
            "student_textbox": "student_textbox.prompt",
            "short_answer": "short_answer.question",
            "fill_in_blank": "fill_in_blank.segments.1.answer",
            "key_fact": "key_fact.fact",
            "divider": "divider.label",
        }

        for field_name, failure_path in field_paths.items():
            state = _base_state(
                current_section_id="s-01",
                errors=[
                    PipelineError(
                        node="schema_validator",
                        section_id="s-01",
                        message=json.dumps(
                            {
                                "summary": "schema_validation_failed",
                                "failures": [
                                    {
                                        "field": failure_path,
                                        "type": "required_manifest",
                                        "message": "Required field missing.",
                                    }
                                ],
                            }
                        ),
                        recoverable=True,
                    )
                ],
            )

            result = route_after_qc(state)
            assert isinstance(result, list), field_name
            assert len(result) == 1, field_name
            assert result[0].node == "retry_field", field_name

    def test_router_text_fields_are_supported_by_field_regenerator(self):
        from pipeline.prompts.field_regen import RETRYABLE_FIELDS
        from pipeline.routers.qc_router import _TEXT_FIELDS

        assert _TEXT_FIELDS <= RETRYABLE_FIELDS


# ── Section assembler (deterministic, uses contracts on disk) ────────────────

class TestDeterministicReviewRouting:

    def test_route_after_qc_returns_end_for_blocking_qc_flags(self):
        state = _base_state(
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=False,
                    issues=[
                        {
                            "severity": "blocking",
                            "block": "practice",
                            "message": "Practice needs stronger progression",
                        }
                    ],
                    warnings=["Keep this flag visible for the teacher."],
                )
            },
        )
        from pipeline.routers.qc_router import route_after_qc

        assert route_after_qc(state) == END

    def test_route_after_qc_returns_end_for_schema_failures(self):
        state = _base_state(
            current_section_id="s-01",
            errors=[
                PipelineError(
                    node="schema_validator",
                    section_id="s-01",
                    message=json.dumps(
                        {
                            "summary": "schema_validation_failed",
                            "failures": [
                                {
                                    "field": "practice.problems.0.question",
                                    "type": "required_manifest",
                                    "message": "Required field missing.",
                                }
                            ],
                        }
                    ),
                    recoverable=True,
                )
            ],
        )
        from pipeline.routers.qc_router import route_after_qc

        assert route_after_qc(state) == END

    def test_merge_state_updates_can_queue_and_clear_rerender_request(self):
        from pipeline.state import merge_state_updates

        raw = _base_state().model_dump()
        request = RerenderRequest(
            section_id="s-01",
            block_type="practice",
            reason="Practice set is too easy",
        )

        merge_state_updates(raw, {"rerender_requests": {"s-01": request}})
        queued = TextbookPipelineState.parse(raw)
        assert queued.pending_rerender_for("s-01") == request

        merge_state_updates(raw, {"rerender_requests": {"s-01": None}})
        cleared = TextbookPipelineState.parse(raw)
        assert cleared.pending_rerender_for("s-01") is None


class TestDocumentQuality:

    def test_quality_passed_requires_full_qc_coverage(self):
        from pipeline import run as run_mod

        command = run_mod.PipelineCommand(
            generation_id="gen-quality",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=4,
        )
        state = _base_state(
            request=command,
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(section_id="s-01", passed=True, issues=[], warnings=[]),
                "s-02": QCReport(section_id="s-02", passed=True, issues=[], warnings=[]),
            },
        )

        document = run_mod._build_document(
            command,
            state,
            status="completed",
            generation_time_seconds=1.0,
        )

        assert document.quality_passed is False

    async def test_content_generator_does_not_treat_cleared_retry_as_rerender(self, monkeypatch):
        from pipeline.nodes import content_generator as cg_mod
        from pipeline.state import merge_state_updates

        state = _base_state(
            current_section_id="s-01",
            current_section_plan=_plan("s-01"),
        )
        raw = state.model_dump()
        merge_state_updates(
            raw,
            {
                "rerender_requests": {
                    "s-01": RerenderRequest(
                        section_id="s-01",
                        block_type="hook",
                        reason="Weak hook",
                    )
                }
            },
        )
        merge_state_updates(raw, {"rerender_requests": {"s-01": None}})
        cleared_state = TextbookPipelineState.parse(raw)

        class DummyAgent:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        async def fake_run_llm(**kwargs):
            return SimpleNamespace(output=_section("s-01"))

        monkeypatch.setattr(cg_mod, "Agent", DummyAgent)
        monkeypatch.setattr(cg_mod, "get_node_text_model", lambda *args, **kwargs: object())
        monkeypatch.setattr(cg_mod, "run_llm", fake_run_llm)

        result = await cg_mod.content_generator(cleared_state)

        assert result["rerender_count"] == {}


class TestSectionAssembler:

    async def test_valid_section_assembled(self):
        from pipeline.nodes.section_assembler import section_assembler

        state = _base_state(
            current_section_id="s-01",
            generated_sections={"s-01": _section("s-01")},
        )
        result = await section_assembler(state)

        assert "s-01" in result["assembled_sections"]
        assert "s-01" in result["qc_reports"]
        assert result["qc_reports"]["s-01"].passed is True
        assert "section_assembler" in result["completed_nodes"]

    async def test_missing_section_returns_error(self):
        from pipeline.nodes.section_assembler import section_assembler

        state = _base_state(
            current_section_id="s-01",
            generated_sections={},
        )
        result = await section_assembler(state)

        assert len(result.get("errors", [])) == 1
        err = result["errors"][0]
        assert err.node == "section_assembler"
        assert err.section_id == "s-01"
        assert not err.recoverable

    async def test_capacity_warnings_populated(self):
        from pipeline.nodes.section_assembler import _check_capacity

        # Section with a headline exceeding 12 words
        section_dict = _section("s-01").model_dump(exclude_none=True)
        section_dict["hook"]["headline"] = " ".join(["word"] * 15)

        warnings = _check_capacity(section_dict)
        assert any("hook.headline" in w for w in warnings)

    async def test_section_assembler_accepts_sections_without_visual_placements(self):
        from pipeline.nodes.section_assembler import section_assembler

        state = _base_state(
            contract=_contract(
                required_components=[
                    "section-header",
                    "hook-hero",
                    "explanation-block",
                    "practice-stack",
                    "what-next-bridge",
                    "diagram-block",
                ],
                optional_components=["definition-card"],
            ),
            current_section_id="s-01",
            generated_sections={"s-01": _section("s-01")},
        )
        result = await section_assembler(state)

        assert "s-01" in result["assembled_sections"]
        assert result["section_pending_assets"]["s-01"] == []
        assert result["section_lifecycle"]["s-01"] == "final"
        assert "section_assembler" in result["completed_nodes"]

    async def test_final_section_assembler_defers_while_placed_visual_is_pending(self):
        from pipeline.nodes.section_assembler import section_assembler

        state = _base_state(
            contract=_contract(
                required_components=[
                    "section-header",
                    "hook-hero",
                    "explanation-block",
                    "practice-stack",
                    "what-next-bridge",
                    "diagram-block",
                ],
                optional_components=["definition-card"],
            ),
            current_section_id="s-01",
            current_section_plan=_plan("s-01").model_copy(
                update={
                    "visual_placements": [
                        BlockVisualPlacement(block="explanation", slot_type="diagram")
                    ]
                }
            ),
            generated_sections={"s-01": _section("s-01")},
            media_plans={
                "s-01": MediaPlan(
                    section_id="s-01",
                    slots=[
                        VisualSlot(
                            slot_id="diagram",
                            slot_type="diagram",
                            required=True,
                            preferred_render="svg",
                            pedagogical_intent="Show the concept clearly.",
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
        )
        result = await section_assembler(state)

        assert "assembled_sections" not in result
        assert "errors" not in result
        assert result["section_pending_assets"]["s-01"] == ["diagram"]
        assert result["section_lifecycle"]["s-01"] == "awaiting_assets"

    async def test_final_section_assembler_succeeds_after_required_visual_writeback(self):
        from pipeline.nodes.section_assembler import section_assembler

        state = _base_state(
            contract=_contract(
                required_components=[
                    "section-header",
                    "hook-hero",
                    "explanation-block",
                    "practice-stack",
                    "what-next-bridge",
                    "diagram-block",
                ],
                optional_components=["definition-card"],
            ),
            current_section_id="s-01",
            generated_sections={
                "s-01": _section("s-01").model_copy(
                    update={
                        "diagram": DiagramContent(
                            svg_content="<svg/>",
                            caption="diagram",
                            alt_text="diagram",
                        )
                    }
                )
            },
        )
        result = await section_assembler(state)

        assert "s-01" in result["assembled_sections"]
        assert result["section_pending_assets"]["s-01"] == []


# ── Preset validation (uses contracts on disk) ───────────────────────────────


class TestQCAgent:

    async def test_qc_agent_preserves_existing_report_for_current_section(self, monkeypatch):
        from pipeline.nodes import qc_agent as qca_mod

        state = _base_state(
            current_section_id="s-02",
            assembled_sections={
                "s-01": _section("s-01"),
                "s-02": _section("s-02"),
            },
            qc_reports={
                "s-01": QCReport(
                    section_id="s-01",
                    passed=True,
                    issues=[],
                    warnings=["existing s-01 warning"],
                ),
                "s-02": QCReport(
                    section_id="s-02",
                    passed=True,
                    issues=[],
                    warnings=["capacity warning"],
                ),
            },
        )

        result = await qca_mod.qc_agent(state)

        assert result["qc_reports"]["s-01"].warnings == ["existing s-01 warning"]
        assert result["qc_reports"]["s-02"].warnings == ["capacity warning"]
        assert "rerender_requests" not in result

    async def test_qc_agent_creates_default_pass_report_when_missing(self, monkeypatch):
        from pipeline.nodes import qc_agent as qca_mod

        state = _base_state(
            current_section_id="s-01",
            assembled_sections={"s-01": _section("s-01")},
            qc_reports={},
        )

        result = await qca_mod.qc_agent(state)

        assert result["qc_reports"]["s-01"].passed is True
        assert result["qc_reports"]["s-01"].issues == []
        assert result["qc_reports"]["s-01"].warnings == []


class TestPresetValidation:

    async def test_invalid_preset_rejected_before_llm_call(self):
        from pipeline.nodes.curriculum_planner import curriculum_planner

        # minimal-light is not in guided-concept-path's allowed_presets
        state = _base_state(
            request=_request(preset_id="minimal-light"),
        )
        result = await curriculum_planner(state)

        assert len(result.get("errors", [])) == 1
        err = result["errors"][0]
        assert err.node == "curriculum_planner"
        assert not err.recoverable
        assert "minimal-light" in err.message
        assert "curriculum_planner" in result["completed_nodes"]
        # No curriculum_outline means fan-out produces nothing
        assert "curriculum_outline" not in result or result["curriculum_outline"] is None


# ── Event bus ────────────────────────────────────────────────────────────────


class TestEventBus:

    def test_publish_subscribe(self):
        from pipeline.events import PipelineEventBus

        bus = PipelineEventBus()
        queue = bus.subscribe("gen-1")

        bus.publish("gen-1", {"type": "pipeline_start"})
        bus.publish("gen-1", {"type": "complete"})

        assert queue.get_nowait()["type"] == "pipeline_start"
        assert queue.get_nowait()["type"] == "complete"

    def test_unsubscribe_stops_delivery(self):
        from pipeline.events import PipelineEventBus

        bus = PipelineEventBus()
        queue = bus.subscribe("gen-1")
        bus.unsubscribe("gen-1", queue)

        bus.publish("gen-1", {"type": "test"})
        assert queue.empty()

    def test_separate_generations_isolated(self):
        from pipeline.events import PipelineEventBus

        bus = PipelineEventBus()
        q1 = bus.subscribe("gen-1")
        q2 = bus.subscribe("gen-2")

        bus.publish("gen-1", {"type": "for-gen-1"})
        bus.publish("gen-2", {"type": "for-gen-2"})

        assert q1.get_nowait()["type"] == "for-gen-1"
        assert q2.get_nowait()["type"] == "for-gen-2"
        assert q1.qsize() == 0
        assert q2.qsize() == 0


class TestRunPipelineStreamingEvents:

    async def test_first_event_is_pipeline_start_with_template_and_preset(
        self, monkeypatch
    ):
        from pipeline import run as run_mod
        from pipeline.events import PipelineStartEvent

        class _EmptyGraph:
            async def astream(self, initial_state, config=None):
                _ = initial_state, config
                if False:
                    yield {}

        monkeypatch.setattr(run_mod, "build_graph", lambda: _EmptyGraph())

        events = []

        async def on_event(event):
            events.append(event)

        command = run_mod.PipelineCommand(
            generation_id="gen-start",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=3,
        )

        await run_mod.run_pipeline_streaming(command, on_event=on_event)

        assert events
        first_event = events[0]
        assert isinstance(first_event, PipelineStartEvent)
        assert first_event.generation_id == "gen-start"
        assert first_event.section_count == 3
        assert first_event.template_id == "guided-concept-path"
        assert first_event.preset_id == "blue-classroom"

    async def test_streaming_does_not_replay_direct_bus_events_through_on_event(
        self, monkeypatch
    ):
        import core.events as core_events
        from pipeline import run as run_mod
        from pipeline.events import RuntimeProgressEvent
        from pipeline.runtime_context import get_runtime_context

        class _Graph:
            async def astream(self, initial_state, config=None):
                runtime_context = get_runtime_context(config)
                assert runtime_context is not None
                _ = initial_state
                core_events.event_bus.publish(
                    runtime_context.generation_id,
                    RuntimeProgressEvent(
                        generation_id=runtime_context.generation_id,
                        snapshot=await runtime_context.progress.snapshot(),
                    ),
                )
                if False:
                    yield {}

        monkeypatch.setattr(run_mod, "build_graph", lambda: _Graph())

        events = []

        async def on_event(event):
            events.append(event)

        command = run_mod.PipelineCommand(
            generation_id="gen-no-replay",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=1,
        )

        await run_mod.run_pipeline_streaming(command, on_event=on_event)

        assert events
        assert not any(isinstance(event, RuntimeProgressEvent) for event in events)

    async def test_streaming_callback_events_are_emitted_once(self, monkeypatch):
        from collections import Counter

        from pipeline import run as run_mod
        from pipeline.events import (
            SectionAssetPendingEvent,
            SectionAssetReadyEvent,
            SectionFinalEvent,
            SectionPartialEvent,
            SectionReadyEvent,
        )
        from pipeline.runtime_context import get_runtime_context

        section = _section("s-01")

        class _Graph:
            async def astream(self, initial_state, config=None):
                runtime_context = get_runtime_context(config)
                assert runtime_context is not None
                _ = initial_state
                yield {
                    "curriculum_planner": {
                        "curriculum_outline": [_plan("s-01", 1)]
                    }
                }
                await runtime_context.emit_event(
                    SectionPartialEvent(
                        generation_id="gen-callback-once",
                        section_id="s-01",
                        section=section,
                        template_id=section.template_id,
                        status="awaiting_assets",
                        visual_mode="svg",
                        pending_assets=["diagram"],
                        updated_at="2026-04-09T00:00:00+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionAssetPendingEvent(
                        generation_id="gen-callback-once",
                        section_id="s-01",
                        pending_assets=["diagram"],
                        status="awaiting_assets",
                        visual_mode="svg",
                        updated_at="2026-04-09T00:00:00+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionAssetReadyEvent(
                        generation_id="gen-callback-once",
                        section_id="s-01",
                        ready_assets=["diagram"],
                        pending_assets=[],
                        visual_mode="svg",
                        updated_at="2026-04-09T00:00:01+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionFinalEvent(
                        generation_id="gen-callback-once",
                        section_id="s-01",
                        section=section,
                        completed_sections=1,
                        total_sections=1,
                    )
                )
                await runtime_context.emit_event(
                    SectionReadyEvent(
                        generation_id="gen-callback-once",
                        section_id="s-01",
                        section=section,
                        completed_sections=1,
                        total_sections=1,
                    )
                )

        monkeypatch.setattr(run_mod, "build_graph", lambda: _Graph())

        events = []

        async def on_event(event):
            events.append(event)

        command = run_mod.PipelineCommand(
            generation_id="gen-callback-once",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=1,
        )

        await run_mod.run_pipeline_streaming(command, on_event=on_event)

        counts = Counter(type(event).__name__ for event in events)
        assert counts["SectionStartedEvent"] == 1
        assert counts["SectionPartialEvent"] == 1
        assert counts["SectionAssetPendingEvent"] == 1
        assert counts["SectionAssetReadyEvent"] == 1
        assert counts["SectionFinalEvent"] == 1
        assert counts["SectionReadyEvent"] == 1

    async def test_completed_document_includes_section_manifest(self, monkeypatch):
        from pipeline import run as run_mod

        class _Graph:
            async def astream(self, initial_state, config=None):
                _ = initial_state, config
                yield {
                    "curriculum_planner": {
                        "curriculum_outline": [_plan("s-02", 2), _plan("s-01", 1)]
                    }
                }
                yield {
                    "process_section": {
                        "assembled_sections": {
                            "s-02": _section("s-02"),
                            "s-01": _section("s-01"),
                        }
                    }
                }

        monkeypatch.setattr(run_mod, "build_graph", lambda: _Graph())

        command = run_mod.PipelineCommand(
            generation_id="gen-manifest",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=2,
        )

        result = await run_mod.run_pipeline_streaming(command)

        assert [item.section_id for item in result.document.section_manifest] == ["s-01", "s-02"]
        assert [item.position for item in result.document.section_manifest] == [1, 2]
        assert [section.section_id for section in result.document.sections] == ["s-01", "s-02"]

    async def test_streaming_normalizes_partial_section_record_and_emits_ordered_events(self, monkeypatch):
        from pipeline import run as run_mod
        from pipeline.events import (
            SectionAssetPendingEvent,
            SectionAssetReadyEvent,
            SectionFinalEvent,
            SectionPartialEvent,
        )
        from pipeline.runtime_context import get_runtime_context

        partial_section = _section("s-01")
        final_section = partial_section.model_copy(
            update={
                "diagram": DiagramContent(
                    svg_content="<svg/>",
                    caption="diagram",
                    alt_text="diagram",
                )
            }
        )

        class _Graph:
            async def astream(self, initial_state, config=None):
                runtime_context = get_runtime_context(config)
                yield {
                    "curriculum_planner": {
                        "curriculum_outline": [_plan("s-01", 1)]
                    }
                }
                await runtime_context.emit_event(
                    SectionPartialEvent(
                        generation_id="gen-stream-order",
                        section_id="s-01",
                        section=partial_section,
                        template_id=partial_section.template_id,
                        status="awaiting_assets",
                        visual_mode="svg",
                        pending_assets=["diagram"],
                        updated_at="2026-04-09T00:00:00+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionAssetPendingEvent(
                        generation_id="gen-stream-order",
                        section_id="s-01",
                        pending_assets=["diagram"],
                        status="awaiting_assets",
                        visual_mode="svg",
                        updated_at="2026-04-09T00:00:00+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionPartialEvent(
                        generation_id="gen-stream-order",
                        section_id="s-01",
                        section=final_section,
                        template_id=final_section.template_id,
                        status="finalizing",
                        visual_mode="svg",
                        pending_assets=[],
                        updated_at="2026-04-09T00:00:01+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionAssetReadyEvent(
                        generation_id="gen-stream-order",
                        section_id="s-01",
                        ready_assets=["diagram"],
                        pending_assets=[],
                        visual_mode="svg",
                        updated_at="2026-04-09T00:00:01+00:00",
                    )
                )
                await runtime_context.emit_event(
                    SectionFinalEvent(
                        generation_id="gen-stream-order",
                        section_id="s-01",
                        completed_sections=1,
                        total_sections=1,
                    )
                )
                yield {
                    "process_section": {
                        "assembled_sections": {"s-01": final_section},
                        "qc_reports": {
                            "s-01": QCReport(
                                section_id="s-01",
                                passed=True,
                                issues=[],
                                warnings=[],
                            )
                        },
                    }
                }

        monkeypatch.setattr(run_mod, "build_graph", lambda: _Graph())

        events = []

        async def on_event(event):
            events.append(event)

        command = run_mod.PipelineCommand(
            generation_id="gen-stream-order",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=1,
        )

        await run_mod.run_pipeline_streaming(command, on_event=on_event)

        ordered_types = [
            type(event)
            for event in events
            if isinstance(
                event,
                (
                    SectionPartialEvent,
                    SectionAssetPendingEvent,
                    SectionAssetReadyEvent,
                    SectionFinalEvent,
                ),
            )
        ]
        assert ordered_types == [
            SectionPartialEvent,
            SectionAssetPendingEvent,
            SectionPartialEvent,
            SectionAssetReadyEvent,
            SectionFinalEvent,
        ]

    async def test_streaming_partial_run_does_not_emit_qc_complete(self, monkeypatch):
        from pipeline import run as run_mod
        from pipeline.events import QCCompleteEvent

        partial_section = _section("s-01")

        class _Graph:
            async def astream(self, initial_state, config=None):
                _ = initial_state, config
                yield {
                    "curriculum_planner": {
                        "curriculum_outline": [_plan("s-01", 1)]
                    }
                }
                yield {
                    "process_section": {
                        "partial_sections": {
                            "s-01": PartialSectionRecord(
                                section_id="s-01",
                                template_id=partial_section.template_id,
                                content=partial_section,
                                status="awaiting_assets",
                                pending_assets=["diagram"],
                                updated_at="2026-04-09T00:00:00+00:00",
                            )
                        },
                        "section_pending_assets": {"s-01": ["diagram"]},
                        "section_lifecycle": {"s-01": "awaiting_assets"},
                    }
                }

        monkeypatch.setattr(run_mod, "build_graph", lambda: _Graph())

        events = []

        async def on_event(event):
            events.append(event)

        command = run_mod.PipelineCommand(
            generation_id="gen-stream-partial",
            subject="Mathematics",
            context="Explain limits",
            grade_band="secondary",
            template_id="guided-concept-path",
            preset_id="blue-classroom",
            learner_fit="general",
            section_count=1,
        )

        result = await run_mod.run_pipeline_streaming(command, on_event=on_event)

        assert result.document.status == "partial"
        assert not any(isinstance(event, QCCompleteEvent) for event in events)


# ── Process section composite (forwards qc_reports) ─────────────────────────


class TestProcessSectionComposite:

    async def test_process_section_forwards_qc_reports(self, monkeypatch):
        """Verify the bug fix: process_section now includes qc_reports in output."""
        from pipeline.nodes import process_section as ps_mod

        # Mock all sub-nodes to return controlled data
        sid = "s-01"
        section = _section(sid)

        async def fake_content(state, *, model_overrides=None):
            return {
                "generated_sections": {sid: section},
                "completed_nodes": ["content_generator"],
            }

        async def fake_diagram(state, *, model_overrides=None):
            return {"completed_nodes": ["diagram_generator"]}

        async def fake_interaction_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["interaction_generator"]}

        async def fake_assembler(state, *, model_overrides=None):
            return {
                "assembled_sections": {sid: section},
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=["hook.headline exceeds 12 words"],
                    )
                },
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            return {"completed_nodes": ["qc_agent"]}

        monkeypatch.setattr(ps_mod, "content_generator", fake_content)
        monkeypatch.setattr(ps_mod, "diagram_generator", fake_diagram)
        monkeypatch.setattr(ps_mod, "interaction_generator", fake_interaction_generator)
        monkeypatch.setattr(ps_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(ps_mod, "qc_agent", fake_qc)

        state = _base_state(
            current_section_id=sid,
            current_section_plan=_plan(sid),
        )
        result = await ps_mod.process_section(state)

        # The fix: qc_reports must be forwarded
        assert "qc_reports" in result, "process_section must forward qc_reports"
        assert sid in result["qc_reports"]
        assert result["qc_reports"][sid].warnings == [
            "hook.headline exceeds 12 words"
        ]

        # Other outputs
        assert sid in result["assembled_sections"]
        assert sid in result["generated_sections"]
        assert "content_generator" in result["completed_nodes"]
        assert "section_assembler" in result["completed_nodes"]

    async def test_process_section_forwards_errors(self, monkeypatch):
        """Sub-node errors are forwarded through the composite."""
        from pipeline.nodes import process_section as ps_mod

        sid = "s-01"

        async def failing_content(state, *, model_overrides=None):
            return {
                "generated_sections": {},
                "errors": [
                    PipelineError(
                        node="content_generator",
                        section_id=sid,
                        message="LLM call failed: timeout",
                        recoverable=True,
                    )
                ],
                "completed_nodes": ["content_generator"],
            }

        async def noop(state, *, model_overrides=None):
            return {"completed_nodes": ["noop"]}

        # Assembler will fail because no generated content
        async def fake_assembler(state, *, model_overrides=None):
            return {
                "errors": [
                    PipelineError(
                        node="section_assembler",
                        section_id=sid,
                        message="No generated content",
                        recoverable=False,
                    )
                ],
                "completed_nodes": ["section_assembler"],
            }

        monkeypatch.setattr(ps_mod, "content_generator", failing_content)
        monkeypatch.setattr(ps_mod, "diagram_generator", noop)
        monkeypatch.setattr(ps_mod, "interaction_generator", noop)
        monkeypatch.setattr(ps_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(ps_mod, "qc_agent", noop)

        state = _base_state(
            current_section_id=sid,
            current_section_plan=_plan(sid),
        )
        result = await ps_mod.process_section(state)

        assert "errors" in result
        assert len(result["errors"]) >= 1
        nodes = [e.node for e in result["errors"]]
        assert "content_generator" in nodes

    async def test_process_section_emits_normalized_section_report_sources(self, monkeypatch):
        from pipeline.events import SectionReportUpdatedEvent
        from pipeline.nodes import process_section as ps_mod
        from pipeline.nodes import section_runner as sr_mod

        sid = "s-01"
        section = _section(sid)
        events = []

        async def fake_content(state, *, model_overrides=None):
            return {
                "generated_sections": {sid: section},
                "completed_nodes": ["content_generator"],
            }

        async def fake_diagram(state, *, model_overrides=None):
            return {"completed_nodes": ["diagram_generator"]}

        async def fake_interaction_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["interaction_generator"]}

        async def fake_assembler(state, *, model_overrides=None):
            return {
                "assembled_sections": {sid: section},
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=["capacity warning"],
                    )
                },
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            return {
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=False,
                        issues=[
                            {
                                "severity": "blocking",
                                "block": "practice",
                                "message": "Practice is too easy",
                            }
                        ],
                        warnings=["capacity warning", "semantic warning"],
                    )
                },
                "rerender_requests": {
                    sid: RerenderRequest(
                        section_id=sid,
                        block_type="practice",
                        reason="Practice is too easy",
                    )
                },
                "completed_nodes": ["qc_agent"],
            }

        monkeypatch.setattr(ps_mod, "content_generator", fake_content)
        monkeypatch.setattr(ps_mod, "diagram_generator", fake_diagram)
        monkeypatch.setattr(ps_mod, "interaction_generator", fake_interaction_generator)
        monkeypatch.setattr(ps_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(ps_mod, "qc_agent", fake_qc)
        monkeypatch.setattr(
            sr_mod,
            "publish_runtime_event",
            lambda generation_id, event: events.append(event),
        )

        state = _base_state(
            request=_request(generation_id="gen-sources"),
            current_section_id=sid,
            current_section_plan=_plan(sid),
        )
        await ps_mod.process_section(state)

        report_events = [event for event in events if isinstance(event, SectionReportUpdatedEvent)]
        assert [event.source for event in report_events] == ["assembler", "qc_agent"]

    async def test_process_section_does_not_crash_after_recoverable_diagram_error(self, monkeypatch):
        from pipeline.events import SectionReportUpdatedEvent
        from pipeline.nodes import process_section as ps_mod
        from pipeline.nodes import section_runner as sr_mod

        sid = "s-01"
        section = _section(sid)
        events = []

        async def fake_content(state, *, model_overrides=None):
            return {
                "generated_sections": {sid: section},
                "completed_nodes": ["content_generator"],
            }

        async def fake_diagram(state, *, model_overrides=None):
            return {
                "errors": [
                    PipelineError(
                        node="diagram_generator",
                        section_id=sid,
                        message="Diagram generation timed out",
                        recoverable=True,
                    )
                ],
                "completed_nodes": ["diagram_generator"],
            }

        async def fake_interaction_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["interaction_generator"]}

        async def fake_image_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["image_generator"]}

        async def fake_assembler(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            return {
                "assembled_sections": {sid: typed.generated_sections[sid]},
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=["diagram omitted"],
                    )
                },
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            return {"completed_nodes": ["qc_agent"]}

        monkeypatch.setattr(ps_mod, "content_generator", fake_content)
        monkeypatch.setattr(ps_mod, "diagram_generator", fake_diagram)
        monkeypatch.setattr(ps_mod, "image_generator", fake_image_generator)
        monkeypatch.setattr(ps_mod, "interaction_generator", fake_interaction_generator)
        monkeypatch.setattr(ps_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(ps_mod, "qc_agent", fake_qc)
        monkeypatch.setattr(
            sr_mod,
            "publish_runtime_event",
            lambda generation_id, event: events.append(event),
        )

        visual_plan = _plan(sid).model_copy(
            update={
                "required_components": ["diagram-block"],
                "visual_policy": SectionVisualPolicy(
                    required=True,
                    intent="explain_structure",
                    mode="svg",
                ),
                "needs_diagram": True,
            }
        )
        state = _base_state(
            request=_request(generation_id="gen-regression"),
            current_section_id=sid,
            current_section_plan=visual_plan,
        )
        result = await ps_mod.process_section(state)

        assert any(error.node == "diagram_generator" for error in result["errors"])
        report_events = [event for event in events if isinstance(event, SectionReportUpdatedEvent)]
        assert [event.source for event in report_events] == ["assembler"]
        assert result["completed_nodes"] == [
            "content_generator",
            "schema_validator",
            "media_planner",
            "diagram_generator",
            "image_generator",
            "interaction_generator",
            "section_assembler",
            "qc_agent",
        ]

    async def test_process_section_attempts_finalization_when_pending_assets_remain(self, monkeypatch):
        from pipeline.nodes import process_section as ps_mod

        sid = "s-01"
        qc_called = False
        assembler_called = False

        async def fake_content(state, *, model_overrides=None):
            return {
                "generated_sections": {sid: _section(sid)},
                "completed_nodes": ["content_generator"],
            }

        async def fake_diagram(state, *, model_overrides=None):
            return {"completed_nodes": ["diagram_generator"]}

        async def fake_interaction_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["interaction_generator"]}

        async def fake_assembler(state, *, model_overrides=None):
            nonlocal assembler_called
            assembler_called = True
            return {
                "errors": [
                    PipelineError(
                        node="section_assembler",
                        section_id=sid,
                        message="No assembled section",
                        recoverable=False,
                    )
                ],
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            nonlocal qc_called
            qc_called = True
            return {"completed_nodes": ["qc_agent"]}

        async def fake_image_generator(state, *, model_overrides=None):
            return {"completed_nodes": ["image_generator"]}

        monkeypatch.setattr(ps_mod, "content_generator", fake_content)
        monkeypatch.setattr(ps_mod, "diagram_generator", fake_diagram)
        monkeypatch.setattr(ps_mod, "image_generator", fake_image_generator)
        monkeypatch.setattr(ps_mod, "interaction_generator", fake_interaction_generator)
        monkeypatch.setattr(ps_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(ps_mod, "qc_agent", fake_qc)

        visual_plan = _plan(sid).model_copy(
            update={
                "required_components": ["diagram-block"],
                "visual_policy": SectionVisualPolicy(
                    required=True,
                    intent="explain_structure",
                    mode="svg",
                ),
                "needs_diagram": True,
            }
        )
        state = _base_state(
            current_section_id=sid,
            current_section_plan=visual_plan,
        )
        result = await ps_mod.process_section(state)

        assert qc_called is False
        assert assembler_called is True
        assert result["completed_nodes"] == [
            "content_generator",
            "schema_validator",
            "media_planner",
            "diagram_generator",
            "image_generator",
            "interaction_generator",
            "section_assembler",
        ]


class TestRetryComposites:

    async def test_retry_media_frame_preserves_text_fields_and_refreshes_qc(self, monkeypatch):
        from pipeline import graph as graph_mod

        sid = "s-01"
        original = _section(sid)
        rerender_counts = []

        async def fake_diagram(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            rerender_counts.append(typed.rerender_count.get(sid, 0))
            updated = typed.generated_sections[sid].model_copy(
                update={
                    "diagram": DiagramContent(
                        svg_content="<svg/>",
                        caption="Updated diagram",
                        alt_text="Updated diagram",
                    )
                }
            )
            return {
                "generated_sections": {sid: updated},
                "completed_nodes": ["diagram_generator"],
            }

        async def fake_assembler(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            return {
                "assembled_sections": {sid: typed.generated_sections[sid]},
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=["diagram refreshed"],
                    )
                },
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            return {
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=typed.qc_reports[sid].warnings,
                    )
                },
                "rerender_requests": {sid: None},
                "completed_nodes": ["qc_agent"],
            }

        monkeypatch.setattr(graph_mod, "diagram_generator", fake_diagram)
        monkeypatch.setattr(graph_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(graph_mod, "qc_agent", fake_qc)

        state = _base_state(
            request=_request(generation_id="gen-retry-diagram"),
            current_section_id=sid,
            current_section_plan=_plan(sid),
            generated_sections={sid: original},
            assembled_sections={sid: original},
            rerender_requests={
                sid: RerenderRequest(
                    section_id=sid,
                    block_type="diagram",
                    reason="Diagram is missing",
                )
            },
        )

        state = state.model_copy(
            update={
                "media_plans": {
                    sid: MediaPlan(
                        section_id=sid,
                        slots=[
                            VisualSlot(
                                slot_id="diagram",
                                slot_type="diagram",
                                required=True,
                                preferred_render="svg",
                                pedagogical_intent="Show the concept clearly.",
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
                "current_media_retry": MediaFrameRetryRequest(
                    section_id=sid,
                    slot_id="diagram",
                    slot_type="diagram",
                    frame_key="0",
                    frame_index=0,
                    executor_node="diagram_generator",
                ),
            }
        )

        result = await graph_mod.retry_media_frame(state)

        assert rerender_counts == [0]
        assert result["completed_nodes"] == [
            "diagram_generator",
            "section_assembler",
            "qc_agent",
        ]
        assert result["media_retry_count"] == {sid: 1}
        assert result["generated_sections"][sid].hook.model_dump() == original.hook.model_dump()
        assert result["generated_sections"][sid].explanation.model_dump() == original.explanation.model_dump()
        assert result["generated_sections"][sid].diagram.caption == "Updated diagram"
        assert result["qc_reports"][sid].passed is True
        assert result["current_media_retry"] is None

    async def test_retry_field_changes_only_targeted_field_and_clears_request(self, monkeypatch):
        from pipeline import graph as graph_mod

        sid = "s-01"
        original = _section(sid)
        rerender_counts = []
        updated_practice = PracticeContent(
            problems=[
                PracticeProblem(
                    difficulty="warm",
                    question="Different warmup question",
                    hints=[PracticeHint(level=1, text="Warmup hint")],
                ),
                PracticeProblem(
                    difficulty="medium",
                    question="Different medium question",
                    hints=[PracticeHint(level=1, text="Medium hint")],
                ),
            ]
        )

        async def fake_field_regenerator(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            rerender_counts.append(typed.rerender_count[sid])
            updated = typed.generated_sections[sid].model_copy(
                update={"practice": updated_practice}
            )
            return {
                "generated_sections": {sid: updated},
                "assembled_sections": {sid: updated},
                "completed_nodes": ["field_regenerator"],
            }

        async def fake_assembler(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            return {
                "assembled_sections": {sid: typed.generated_sections[sid]},
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=["practice refreshed"],
                    )
                },
                "completed_nodes": ["section_assembler"],
            }

        async def fake_qc(state, *, model_overrides=None):
            typed = TextbookPipelineState.parse(state)
            return {
                "qc_reports": {
                    sid: QCReport(
                        section_id=sid,
                        passed=True,
                        issues=[],
                        warnings=typed.qc_reports[sid].warnings,
                    )
                },
                "rerender_requests": {sid: None},
                "completed_nodes": ["qc_agent"],
            }

        monkeypatch.setattr(graph_mod, "field_regenerator", fake_field_regenerator)
        monkeypatch.setattr(graph_mod, "section_assembler", fake_assembler)
        monkeypatch.setattr(graph_mod, "qc_agent", fake_qc)

        state = _base_state(
            request=_request(generation_id="gen-retry-field"),
            current_section_id=sid,
            current_section_plan=_plan(sid),
            generated_sections={sid: original},
            assembled_sections={sid: original},
            rerender_requests={
                sid: RerenderRequest(
                    section_id=sid,
                    block_type="practice",
                    reason="Practice needs stronger progression",
                )
            },
        )

        result = await graph_mod.retry_field(state)

        assert rerender_counts == [1]
        assert result["rerender_count"] == {sid: 1}
        assert result["generated_sections"][sid].hook.model_dump() == original.hook.model_dump()
        assert result["generated_sections"][sid].explanation.model_dump() == original.explanation.model_dump()
        assert result["generated_sections"][sid].practice.model_dump() == updated_practice.model_dump()
        assert result["rerender_requests"] == {sid: None}
        assert result["qc_reports"][sid].passed is True

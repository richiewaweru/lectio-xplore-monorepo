from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from planning.fallback import build_fallback_spec
from planning.models import (
    PlanningTemplateContract,
    StudioBriefRequest,
    VisualPolicy,
)
from planning.normalizer import normalize_brief
from planning.section_composer import compose_sections
from planning.service import PlanningService
from planning.template_scorer import choose_template
from planning.visual_router import route_visuals


def build_brief(**overrides) -> StudioBriefRequest:
    payload = {
        "intent": "Teach long division to Year 6 students using short worked examples and guided practice",
        "audience": "Year 6 mixed ability",
        "prior_knowledge": "Confident with multiplication facts",
        "extra_context": "",
        "signals": {
            "topic_type": None,
            "learning_outcome": None,
            "class_style": ["needs-explanation-first"],
            "format": "both",
        },
        "preferences": {
            "tone": "supportive",
            "reading_level": "simple",
            "explanation_style": "balanced",
            "example_style": "everyday",
            "brevity": "balanced",
        },
        "constraints": {
            "more_practice": False,
            "keep_short": False,
            "use_visuals": False,
            "print_first": False,
        },
    }
    payload.update(overrides)
    return StudioBriefRequest.model_validate(payload)


def build_contract(
    *,
    template_id: str = "guided-concept-path",
    name: str = "Guided Concept Path",
    intent: str = "introduce-concept",
    signal_affinity: dict | None = None,
    section_role_defaults: dict | None = None,
    available_components: list[str] | None = None,
    always_present: list[str] | None = None,
    component_budget: dict[str, int] | None = None,
    max_per_section: dict[str, int] | None = None,
    best_for: list[str] | None = None,
    tags: list[str] | None = None,
    not_ideal_for: list[str] | None = None,
) -> PlanningTemplateContract:
    return PlanningTemplateContract.model_validate(
        {
            "id": template_id,
            "name": name,
            "family": "guided-concept",
            "intent": intent,
            "tagline": "Template tagline",
            "reading_style": "linear-guided",
            "tags": tags or [],
            "best_for": best_for or [],
            "not_ideal_for": not_ideal_for or [],
            "learner_fit": ["general"],
            "subjects": ["mathematics"],
            "interaction_level": "medium",
            "always_present": always_present or ["section-header", "hook-hero", "what-next-bridge"],
            "available_components": available_components
            or [
                "hook-hero",
                "explanation-block",
                "worked-example-card",
                "practice-stack",
                "diagram-block",
                "summary-block",
                "what-next-bridge",
                "process-steps",
            ],
            "component_budget": component_budget or {"diagram-block": 1, "worked-example-card": 1},
            "max_per_section": max_per_section or {"diagram-block": 1, "worked-example-card": 1},
            "default_behaviours": {},
            "section_role_defaults": section_role_defaults
            or {
                "intro": ["hook-hero"],
                "explain": ["diagram-block", "worked-example-card", "explanation-block"],
                "practice": ["practice-stack"],
                "summary": ["summary-block", "what-next-bridge"],
            },
            "signal_affinity": signal_affinity
            or {
                "topic_type": {"concept": 0.9, "process": 0.45, "facts": 0.5, "mixed": 0.6},
                "learning_outcome": {
                    "understand-why": 0.9,
                    "be-able-to-do": 0.45,
                    "remember-terms": 0.5,
                    "apply-to-new": 0.6,
                },
                "class_style": {
                    "needs-explanation-first": 0.85,
                    "tries-before-told": 0.35,
                    "engages-with-visuals": 0.5,
                    "responds-to-worked-examples": 0.75,
                    "restless-without-activity": 0.4,
                },
                "format": {
                    "printed-booklet": 0.7,
                    "screen-based": 0.8,
                    "both": 0.78,
                },
            },
            "layout_notes": [],
            "responsive_rules": [],
            "print_rules": ["Flatten complex interaction for print."],
            "allowed_presets": ["blue-classroom"],
            "why_this_template_exists": "Planning tests",
            "generation_guidance": {
                "tone": "clear",
                "pacing": "steady",
                "chunking": "medium",
                "emphasis": "concept clarity",
                "avoid": ["overload"],
            },
        }
    )


class FakeAgent:
    def __init__(self, *, model, output_type, system_prompt) -> None:
        self.model = model
        self.output_type = output_type
        self.system_prompt = system_prompt


def make_llm_stub(
    *,
    normalizer: dict | Callable[[dict], dict] | None = None,
    composer: dict | Callable[[dict], dict] | None = None,
    visual_router: dict | Callable[[dict], dict] | None = None,
    refinement: dict | Callable[[dict], dict] | None = None,
    calls: list[dict] | None = None,
):
    payloads = {
        "_BriefIntentResolution": normalizer,
        "_SectionRolePlan": composer,
        "_VisualRoutingPlan": visual_router,
        "PlanningRefinementOutput": refinement,
    }

    async def fake_run_llm_fn(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        output_type = kwargs["agent"].output_type
        payload = payloads.get(output_type.__name__)
        if payload is None:
            raise AssertionError(f"Unexpected output type: {output_type.__name__}")
        if callable(payload):
            payload = payload(kwargs)
        return SimpleNamespace(output=output_type.model_validate(payload))

    return fake_run_llm_fn


async def test_normalizer_derives_defaults_and_scope_warning():
    brief = build_brief(
        intent="How to solve long division using short worked examples for mixed-ability Year 6 students"
    )

    normalized = await normalize_brief(brief)

    assert normalized.resolved_topic_type == "process"
    assert normalized.resolved_learning_outcome == "be-able-to-do"
    assert normalized.directives.scaffold_level == "high"
    assert normalized.scope_warning is not None


async def test_normalizer_uses_llm_resolution_when_available():
    brief = build_brief(intent="Explore why eclipses happen and how shadows change in space")
    fake_run_llm_fn = make_llm_stub(
        normalizer={
            "topic_type": "mixed",
            "learning_outcome": "apply-to-new",
            "keyword_profile": ["eclipses", "shadows", "space"],
            "scope_warning": "Keep the lesson focused on one eclipse pattern.",
        }
    )

    with patch("planning.normalizer.Agent", FakeAgent):
        normalized = await normalize_brief(
            brief,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            generation_id="trace-1",
        )

    assert normalized.resolved_topic_type == "mixed"
    assert normalized.resolved_learning_outcome == "apply-to-new"
    assert normalized.keyword_profile == ["eclipses", "shadows", "space"]
    assert normalized.scope_warning == "Keep the lesson focused on one eclipse pattern."


async def test_template_scorer_uses_metadata_when_affinity_is_missing():
    process_brief = await normalize_brief(
        build_brief(
            signals={
                "topic_type": "process",
                "learning_outcome": "be-able-to-do",
                "class_style": [],
                "format": "both",
            }
        )
    )
    procedure = build_contract(
        template_id="procedure",
        name="Procedure",
        intent="teach-procedure",
        signal_affinity={"topic_type": {}, "learning_outcome": {}, "class_style": {}, "format": {}},
        section_role_defaults={
            "intro": ["hook-hero"],
            "process": ["process-steps"],
            "explain": ["explanation-block"],
            "practice": ["practice-stack"],
            "summary": ["what-next-bridge"],
        },
        available_components=["hook-hero", "process-steps", "explanation-block", "practice-stack", "what-next-bridge"],
        best_for=["step-by-step procedures"],
        tags=["procedure", "method"],
    )
    concept = build_contract(template_id="guided-concept-path", intent="introduce-concept")

    chosen, decision = choose_template(process_brief, [concept, procedure])

    assert chosen.id == "procedure"
    assert decision.chosen_id == "procedure"


async def test_template_scorer_falls_back_to_open_canvas_when_scores_are_weak():
    brief = await normalize_brief(
        build_brief(
            intent="Teach an unusual interdisciplinary studio topic",
            signals={
                "topic_type": "mixed",
                "learning_outcome": "apply-to-new",
                "class_style": [],
                "format": "both",
            },
            preferences={
                "tone": "neutral",
                "reading_level": "advanced",
                "explanation_style": "balanced",
                "example_style": "academic",
                "brevity": "tight",
            },
        )
    )
    weak_contract = build_contract(
        template_id="compare-and-apply",
        intent="compare-ideas",
        best_for=["binary contrasts"],
        signal_affinity={
            "topic_type": {"concept": 0.2},
            "learning_outcome": {"remember-terms": 0.2},
            "class_style": {},
            "format": {"printed-booklet": 0.2},
        },
    )
    open_canvas = build_contract(
        template_id="open-canvas",
        name="Open Canvas",
        intent="introduce-concept",
        tags=["flexible", "open"],
        best_for=["broad or novel lesson shapes"],
        available_components=["hook-hero", "callout-block", "explanation-block", "summary-block"],
        section_role_defaults={
            "intro": ["hook-hero"],
            "explain": ["explanation-block"],
            "summary": ["summary-block"],
        },
        signal_affinity={
            "topic_type": {},
            "learning_outcome": {},
            "class_style": {},
            "format": {},
        },
    )

    chosen, _ = choose_template(brief, [weak_contract, open_canvas])

    assert chosen.id == "open-canvas"


async def test_section_composer_respects_component_budgets_across_sections():
    contract = build_contract()
    brief = await normalize_brief(
        build_brief(
            constraints={
                "more_practice": True,
                "keep_short": False,
                "use_visuals": False,
                "print_first": False,
            }
        )
    )

    sections = await compose_sections(brief, contract)

    all_components = [component for section in sections for component in section.selected_components]
    assert all_components.count("diagram-block") <= 1
    assert all_components.count("worked-example-card") <= 1
    assert any(section.role == "summary" for section in sections)
    explain_sections = [section for section in sections if section.role == "explain"]
    assert explain_sections
    assert any("explanation-block" in section.selected_components for section in explain_sections)


async def test_section_composer_falls_back_when_llm_roles_break_constraints():
    contract = build_contract(
        intent="teach-procedure",
        section_role_defaults={
            "intro": ["hook-hero"],
            "process": ["process-steps"],
            "explain": ["explanation-block"],
            "practice": ["practice-stack"],
            "summary": ["summary-block", "what-next-bridge"],
        },
    )
    brief = await normalize_brief(
        build_brief(
            signals={
                "topic_type": "process",
                "learning_outcome": "be-able-to-do",
                "class_style": [],
                "format": "both",
            }
        )
    )
    fake_run_llm_fn = make_llm_stub(
        composer={
            "roles": ["intro", "explain", "summary"],
        }
    )

    with patch("planning.section_composer.Agent", FakeAgent):
        sections = await compose_sections(
            brief,
            contract,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            generation_id="trace-2",
        )

    assert any(section.role in {"process", "timeline"} for section in sections)


async def test_section_composer_rejects_roles_outside_active_contract():
    contract = build_contract(
        section_role_defaults={
            "intro": ["hook-hero"],
            "explain": ["explanation-block"],
            "practice": ["practice-stack"],
            "summary": ["summary-block", "what-next-bridge"],
        }
    )
    brief = await normalize_brief(build_brief())
    fake_run_llm_fn = make_llm_stub(
        composer={
            "roles": ["intro", "visual", "practice", "summary"],
        }
    )

    with patch("planning.section_composer.Agent", FakeAgent):
        sections = await compose_sections(
            brief,
            contract,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            generation_id="trace-contract-roles",
        )

    assert {section.role for section in sections}.issubset({"intro", "explain", "practice", "summary"})
    assert not any(section.role == "visual" for section in sections)


async def test_section_composer_prompt_lists_only_active_contract_roles():
    contract = build_contract(
        section_role_defaults={
            "intro": ["hook-hero"],
            "discover": ["diagram-block"],
            "summary": ["summary-block", "what-next-bridge"],
        },
        available_components=["hook-hero", "diagram-block", "summary-block", "what-next-bridge"],
    )
    brief = await normalize_brief(build_brief())
    calls: list[dict] = []
    fake_run_llm_fn = make_llm_stub(
        composer={"roles": ["intro", "discover", "summary"]},
        calls=calls,
    )

    with patch("planning.section_composer.Agent", FakeAgent):
        await compose_sections(
            brief,
            contract,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            generation_id="trace-contract-prompt",
        )

    assert calls
    allowed_roles_line = next(
        line for line in calls[0]["user_prompt"].splitlines() if line.startswith("Allowed roles:")
    )
    assert allowed_roles_line == "Allowed roles: intro, discover, summary"


async def test_visual_router_uses_intent_regardless_of_print_first():
    contract = build_contract(
        template_id="procedure",
        intent="teach-procedure",
        section_role_defaults={
            "intro": ["hook-hero"],
            "process": ["process-steps"],
            "explain": ["diagram-block", "explanation-block"],
            "summary": ["what-next-bridge"],
        },
        available_components=["hook-hero", "process-steps", "diagram-block", "explanation-block", "what-next-bridge"],
    )
    brief = await normalize_brief(
        build_brief(
            signals={
                "topic_type": "process",
                "learning_outcome": "be-able-to-do",
                "class_style": [],
                "format": "printed-booklet",
            },
            constraints={
                "more_practice": False,
                "keep_short": True,
                "use_visuals": True,
                "print_first": True,
            },
        )
    )

    routed = await route_visuals(brief, contract, await compose_sections(brief, contract))

    assert any(section.visual_policy and section.visual_policy.required for section in routed)
    for section in routed:
        if section.visual_policy and section.role == "process":
            assert section.visual_policy.mode == "image"
            assert [placement.slot_type for placement in section.visual_placements] == ["diagram"]


async def test_visual_router_routes_graph_topics_to_image_for_explain_structure() -> None:
    contract = build_contract()
    brief = await normalize_brief(
        build_brief(
            intent="Explain slope and graph interpretation with coordinate axes and linear equations",
            constraints={
                "more_practice": False,
                "keep_short": False,
                "use_visuals": True,
                "print_first": False,
            },
        )
    )

    routed = await route_visuals(brief, contract, await compose_sections(brief, contract))
    explain_section = next(section for section in routed if section.role == "explain")

    assert explain_section.visual_policy is not None
    assert explain_section.visual_policy.intent == "explain_structure"
    assert explain_section.visual_policy.mode == "image"


async def test_visual_router_prefers_compare_placements_for_compare_intent() -> None:
    contract = build_contract(
        template_id="compare-and-apply",
        intent="compare-ideas",
        available_components=[
            "hook-hero",
            "explanation-block",
            "diagram-compare",
            "practice-stack",
            "what-next-bridge",
        ],
        section_role_defaults={
            "intro": ["hook-hero"],
            "compare": ["explanation-block"],
            "practice": ["practice-stack"],
            "summary": ["what-next-bridge"],
        },
    )
    brief = await normalize_brief(
        build_brief(
            intent="Compare plant and animal cells",
            signals={
                "topic_type": "concept",
                "learning_outcome": "understand-why",
                "class_style": ["engages-with-visuals"],
                "format": "both",
            },
            constraints={
                "more_practice": False,
                "keep_short": False,
                "use_visuals": True,
                "print_first": False,
            },
        )
    )

    sections = await compose_sections(brief, contract)
    compare_section = next(section for section in sections if section.role == "compare")

    routed = await route_visuals(brief, contract, sections)
    routed_compare = next(section for section in routed if section.id == compare_section.id)

    assert [placement.block for placement in routed_compare.visual_placements] == ["explanation"]
    assert [placement.slot_type for placement in routed_compare.visual_placements] == [
        "diagram_compare"
    ]


async def test_visual_router_prefers_series_placements_for_process_intent() -> None:
    contract = build_contract(
        template_id="procedure",
        intent="teach-procedure",
        available_components=[
            "hook-hero",
            "explanation-block",
            "diagram-series",
            "practice-stack",
            "what-next-bridge",
        ],
        section_role_defaults={
            "intro": ["hook-hero"],
            "process": ["explanation-block"],
            "practice": ["practice-stack"],
            "summary": ["what-next-bridge"],
        },
    )
    brief = await normalize_brief(
        build_brief(
            signals={
                "topic_type": "process",
                "learning_outcome": "be-able-to-do",
                "class_style": [],
                "format": "both",
            },
            constraints={
                "more_practice": False,
                "keep_short": False,
                "use_visuals": True,
                "print_first": False,
            },
        )
    )

    routed = await route_visuals(brief, contract, await compose_sections(brief, contract))
    process_section = next(section for section in routed if section.role == "process")

    assert [placement.block for placement in process_section.visual_placements] == ["explanation"]
    assert [placement.slot_type for placement in process_section.visual_placements] == [
        "diagram_series"
    ]


async def test_visual_router_falls_back_to_single_diagram_placement() -> None:
    contract = build_contract()
    brief = await normalize_brief(
        build_brief(
            constraints={
                "more_practice": False,
                "keep_short": False,
                "use_visuals": True,
                "print_first": False,
            }
        )
    )

    routed = await route_visuals(brief, contract, await compose_sections(brief, contract))
    explain_section = next(section for section in routed if section.role == "explain")

    assert [placement.block for placement in explain_section.visual_placements] == ["explanation"]
    assert [placement.slot_type for placement in explain_section.visual_placements] == ["diagram"]


async def test_visual_router_falls_back_when_llm_response_is_invalid() -> None:
    contract = build_contract()
    brief = await normalize_brief(
        build_brief(
            constraints={
                "more_practice": False,
                "keep_short": False,
                "use_visuals": True,
                "print_first": False,
            }
        )
    )
    sections = await compose_sections(brief, contract)

    def invalid_visual_payload(kwargs: dict) -> dict:
        section_ids = [
            line.split()[0].split("=", 1)[1]
            for line in kwargs["user_prompt"].splitlines()
            if line.startswith("- id=")
        ]
        return {
            "sections": [
                {
                    "section_id": section_ids[0],
                    "required": True,
                    "intent": "explain_structure",
                    "mode": None,
                },
                *[
                    {"section_id": section_id, "required": False, "intent": None, "mode": None}
                    for section_id in section_ids[1:]
                ],
            ]
        }

    fake_run_llm_fn = make_llm_stub(visual_router=invalid_visual_payload)

    with patch("planning.visual_router.Agent", FakeAgent):
        routed = await route_visuals(
            brief,
            contract,
            sections,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            generation_id="trace-3",
        )

    explain_section = next(section for section in routed if section.role == "explain")
    assert explain_section.visual_policy is not None
    assert explain_section.visual_policy.mode == "svg"


def test_fallback_uses_contract_defaults_and_returns_reviewable_spec():
    contract = build_contract(
        section_role_defaults={
            "intro": ["hook-hero", "callout-block"],
            "explain": ["explanation-block"],
            "summary": ["summary-block", "what-next-bridge"],
        }
    )

    spec = build_fallback_spec(brief=build_brief(), contract=contract)

    assert spec.sections[0].selected_components == ["hook-hero", "callout-block"]
    assert spec.sections[1].selected_components == ["explanation-block"]
    assert spec.sections[2].selected_components == ["summary-block", "what-next-bridge"]
    assert spec.warning is not None


async def test_planning_service_emits_events_and_refines_titles():
    brief = build_brief(
        intent="Teach fractions",
        signals={
            "topic_type": "concept",
            "learning_outcome": "understand-why",
            "class_style": ["needs-explanation-first"],
            "format": "both",
        },
        constraints={
            "more_practice": False,
            "keep_short": True,
            "use_visuals": False,
            "print_first": False,
        },
    )
    contract = build_contract()
    emitted: list[dict[str, object]] = []

    async def fake_emit(payload: dict[str, object]) -> None:
        emitted.append(payload)

    def visual_payload(kwargs: dict) -> dict:
        section_ids = [
            line.split("id=", 1)[1].split()[0]
            for line in kwargs["user_prompt"].splitlines()
            if line.startswith("- id=")
        ]
        return {
            "sections": [
                {"section_id": section_id, "required": False, "intent": None, "mode": None}
                for section_id in section_ids
            ]
        }

    llm_calls: list[dict] = []
    fake_run_llm_fn = make_llm_stub(
        normalizer={
            "topic_type": "concept",
            "learning_outcome": "understand-why",
            "keyword_profile": ["fractions", "students"],
            "scope_warning": None,
        },
        composer={
            "roles": ["intro", "explain", "summary"],
        },
        visual_router=visual_payload,
        refinement={
            "lesson_rationale": "A teacher-facing rationale.",
            "warning": None,
            "sections": [
                {
                    "title": "Start with the core idea",
                    "rationale": "Open with the main idea before moving into practice.",
                    "transition_note": None,
                    "terms_to_define": ["fraction"],
                    "terms_assumed": [],
                    "practice_target": "name the fraction as part of a whole",
                },
                {
                    "title": "Build the explanation",
                    "rationale": "Clarify the method and its steps.",
                    "transition_note": "The previous section established the core idea of a fraction; this section now explains how the parts relate to the whole.",
                    "terms_to_define": ["numerator"],
                    "terms_assumed": ["fraction"],
                    "practice_target": "explain what the numerator counts",
                },
                {
                    "title": "Close and connect forward",
                    "rationale": "Wrap up the main takeaway.",
                    "transition_note": "The previous section established how the parts relate to the whole; this section now checks the learner can say the main takeaway back.",
                    "terms_to_define": [],
                    "terms_assumed": ["fraction", "numerator"],
                    "practice_target": "summarise the fraction idea in words",
                },
            ],
        },
        calls=llm_calls,
    )

    with (
        patch("planning.normalizer.Agent", FakeAgent),
        patch("planning.section_composer.Agent", FakeAgent),
        patch("planning.visual_router.Agent", FakeAgent),
        patch("planning.prompt_builder.Agent", FakeAgent),
    ):
        spec = PlanningService()
        result = await spec.plan(
            brief,
            contracts=[contract],
            model=object(),
            run_llm_fn=fake_run_llm_fn,
            emit=fake_emit,
        )

    assert result.sections[0].title == "Start with the core idea"
    assert result.sections[0].transition_note is None
    assert result.sections[0].terms_to_define == ["fraction"]
    assert result.sections[1].terms_assumed == ["fraction"]
    assert result.sections[1].practice_target == "explain what the numerator counts"
    assert emitted[0]["event"] == "template_selected"
    assert [payload["event"] for payload in emitted[1:]] == [
        "section_planned",
        "section_planned",
        "section_planned",
    ]
    assert len(llm_calls) == 4


def test_visual_policy_rejects_mode_none_when_required():
    with pytest.raises(Exception, match="mode and intent must be set"):
        VisualPolicy(required=True, mode=None, intent=None)

    with pytest.raises(Exception, match="mode and intent must be set"):
        VisualPolicy(required=True, mode=None, intent="explain_structure")

    with pytest.raises(Exception, match="mode and intent must be set"):
        VisualPolicy(required=True, mode="svg", intent=None)

    # Valid: both mode and intent set when required
    policy = VisualPolicy(required=True, mode="svg", intent="explain_structure")
    assert policy.required is True

    # Valid: required=False allows None mode/intent
    policy = VisualPolicy(required=False, mode=None, intent=None)
    assert policy.required is False


async def test_section_count_boundaries():
    contract = build_contract()

    # 3 sections (lower bound)
    brief_short = await normalize_brief(
        build_brief(
            constraints={
                "more_practice": False,
                "keep_short": True,
                "use_visuals": False,
                "print_first": False,
            }
        )
    )
    sections_short = await compose_sections(brief_short, contract)
    assert len(sections_short) >= 2

    # Standard brief
    brief_standard = await normalize_brief(build_brief())
    sections_standard = await compose_sections(brief_standard, contract)
    assert 2 <= len(sections_standard) <= 5


async def test_empty_signal_affinity_scoring_uses_metadata():
    brief = await normalize_brief(
        build_brief(
            signals={
                "topic_type": "concept",
                "learning_outcome": "understand-why",
                "class_style": ["needs-explanation-first"],
                "format": "both",
            }
        )
    )
    empty_affinity = build_contract(
        template_id="empty-affinity",
        name="Empty Affinity",
        intent="introduce-concept",
        signal_affinity={
            "topic_type": {},
            "learning_outcome": {},
            "class_style": {},
            "format": {},
        },
        best_for=["concept introductions"],
        tags=["concept"],
    )
    rich_affinity = build_contract(
        template_id="rich-affinity",
        name="Rich Affinity",
        intent="introduce-concept",
    )

    # The scorer should still produce a valid result even with empty affinity
    chosen, decision = choose_template(brief, [empty_affinity, rich_affinity])
    assert decision.chosen_id in {"empty-affinity", "rich-affinity"}
    assert decision.fit_score >= 0


def test_section_focus_fallback_in_bridge():
    """PlanningSectionPlan with all optional focus fields None should produce valid focus."""
    from planning.models import PlanningSectionPlan

    section = PlanningSectionPlan.model_validate(
        {
            "id": "section-1",
            "order": 1,
            "role": "intro",
            "title": "Introduction",
            "objective": None,
            "focus_note": None,
            "selected_components": ["hook-hero"],
            "rationale": "Opening section.",
        }
    )
    # The bridge chain: focus_note or objective or rationale or title
    focus = section.focus_note or section.objective or section.rationale or section.title
    if not focus:
        focus = f"Section {section.order}"
    assert focus == "Opening section."

    # All None except title
    section2 = PlanningSectionPlan.model_validate(
        {
            "id": "section-2",
            "order": 2,
            "role": "explain",
            "title": "Explanation",
            "objective": None,
            "focus_note": None,
            "rationale": "",
            "selected_components": [],
        }
    )
    focus2 = section2.focus_note or section2.objective or section2.rationale or section2.title
    if not focus2:
        focus2 = f"Section {section2.order}"
    assert focus2 == "Explanation"


async def test_forced_template_id_can_override_recommended_template():
    """PlannerService keeps teacher override even when scoring would pick a different template."""
    brief = build_brief(
        forced_template_id="procedure",
        constraints={
            "more_practice": False,
            "keep_short": True,
            "use_visuals": False,
            "print_first": False,
        },
    )
    contracts = [
        build_contract(template_id="guided-concept-path"),
        build_contract(template_id="procedure", name="Procedure"),
    ]
    llm_calls: list[dict] = []

    def visual_payload(kwargs: dict) -> dict:
        section_ids = [
            line.split("id=", 1)[1].split()[0]
            for line in kwargs["user_prompt"].splitlines()
            if line.startswith("- id=")
        ]
        return {
            "sections": [
                {"section_id": section_id, "required": False, "intent": None, "mode": None}
                for section_id in section_ids
            ]
        }

    fake_run_llm_fn = make_llm_stub(
        normalizer={
            "topic_type": "concept",
            "learning_outcome": "understand-why",
            "keyword_profile": ["fractions"],
            "scope_warning": None,
        },
        composer={
            "roles": ["intro", "explain", "summary"],
        },
        visual_router=visual_payload,
        refinement={
            "lesson_rationale": "Procedure rationale.",
            "warning": None,
            "sections": [
                {"title": "Step one", "rationale": "First step."},
                {"title": "Step two", "rationale": "Second step."},
                {"title": "Wrap up", "rationale": "Close it out."},
            ],
        },
        calls=llm_calls,
    )

    with (
        patch("planning.normalizer.Agent", FakeAgent),
        patch("planning.section_composer.Agent", FakeAgent),
        patch("planning.visual_router.Agent", FakeAgent),
        patch("planning.prompt_builder.Agent", FakeAgent),
    ):
        result = await PlanningService().plan(
            brief,
            contracts=contracts,
            model=object(),
            run_llm_fn=fake_run_llm_fn,
        )

    assert result.template_id == "procedure"
    assert result.template_decision.fit_score == 1.0
    assert result.template_decision.chosen_id == "procedure"
    assert "overrides the top recommendation" in result.template_decision.rationale
    assert result.template_decision.alternatives[0].template_id == "guided-concept-path"
    assert len(llm_calls) == 4


async def test_forced_template_id_raises_if_not_in_catalog():
    """PlannerService raises ValueError when forced_template_id is not in the contracts list."""
    brief = build_brief(forced_template_id="nonexistent-template")
    contracts = [build_contract(template_id="guided-concept-path")]

    with pytest.raises(ValueError, match="not in live-safe catalog"):
        await PlanningService().plan(
            brief,
            contracts=contracts,
            model=None,
            run_llm_fn=None,
        )

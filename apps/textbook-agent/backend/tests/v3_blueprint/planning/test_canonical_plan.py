"""Phase 03: constrained selection + canonical execution plan."""

from __future__ import annotations

import pytest

from v3_blueprint.planning.canonical_plan import (
    SelectedComponent,
    SelectionValidationError,
    SelectorChoice,
    build_canonical_execution_plan,
    build_selector_prompt_context,
    heuristic_select_components,
    validate_selector_choice,
)
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from resource_specs.candidates import resolve_role_candidates
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject


def test_selector_context_contains_only_narrowed_candidates() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    section = plan.sections[1]  # build
    candidates = resolve_role_candidates(section.role)
    context = build_selector_prompt_context(section=section, candidates=candidates)
    ids = {item["component_id"] for item in context["allowed_components"]}
    assert ids == set(candidates.candidates)
    assert "field_contracts" not in str(context)
    assert "schema" not in str(context).lower() or "schema_summary" not in str(context)
    # Full catalogue components that are not candidates must not appear.
    assert "timeline-block" not in ids
    assert "interview-anchor" not in ids


def test_validate_rejects_outside_candidate_set() -> None:
    candidates = resolve_role_candidates("orient")
    choice = SelectorChoice(
        components=[
            SelectedComponent(
                slug="practice-stack",
                purpose="illegal",
                reason="x",
            )
        ]
    )
    errors = validate_selector_choice(choice, candidates=candidates)
    assert any("outside candidate set" in error for error in errors)


def test_validate_rejects_duplicate_section_field(monkeypatch) -> None:
    candidates = resolve_role_candidates("build")
    # Force two candidates to share a field.
    from v3_blueprint.planning import canonical_plan as mod

    original = mod.get_component_card

    def fake_card(component_id: str):
        card = original(component_id) or {}
        if component_id in {"definition-card", "key-fact"}:
            return {**card, "section_field": "same"}
        return card

    monkeypatch.setattr(mod, "get_component_card", fake_card)
    choice = SelectorChoice(
        components=[
            SelectedComponent(slug="definition-card", purpose="a", reason="r"),
            SelectedComponent(slug="key-fact", purpose="b", reason="r"),
        ]
    )
    errors = validate_selector_choice(choice, candidates=candidates)
    assert any("share section_field" in error for error in errors)


def test_validate_rejects_budget_exhaustion() -> None:
    candidates = resolve_role_candidates("practice")
    if "practice-stack" not in candidates.candidates:
        pytest.skip("practice-stack not in candidates")
    choice = SelectorChoice(
        components=[SelectedComponent(slug="practice-stack", purpose="practice", reason="r")]
    )
    errors = validate_selector_choice(
        choice,
        candidates=candidates,
        remaining_budget={"practice-stack": 0},
    )
    assert any("exhausted budget" in error for error in errors)


def test_canonical_plan_deterministic_ids_across_subjects() -> None:
    hashes: list[str] = []
    for fixture in SUBJECT_FIXTURES:
        intent = _intent_plan_for_subject(**fixture)
        plan = intent_plan_to_structural_plan(intent)
        first, filled = build_canonical_execution_plan(
            plan,
            generation_id="gen-1",
            lesson_id=f"lesson-{fixture['subject']}",
        )
        second, _ = build_canonical_execution_plan(
            filled,
            generation_id="gen-1",
            lesson_id=f"lesson-{fixture['subject']}",
        )
        assert first.plan_hash == second.plan_hash
        assert first.blocks
        assert all(block.block_id for block in first.blocks)
        assert all(section.block_ids for section in first.sections)
        # No content payloads.
        assert "content" not in first.model_dump()
        hashes.append(first.plan_hash)
        # Re-run on empty components plan yields same structure for same inputs.
        again, _ = build_canonical_execution_plan(
            plan,
            generation_id="gen-1",
            lesson_id=f"lesson-{fixture['subject']}",
        )
        assert again.plan_hash == first.plan_hash
    assert len(set(hashes)) == len(SUBJECT_FIXTURES)


def test_canonical_plan_retains_selection_evidence_outside_hash() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)

    def traced_selector(context):
        allowed = context["allowed_components"]
        picked = allowed[0]["component_id"]
        return SelectorChoice(
            components=[
                SelectedComponent(
                    slug=picked,
                    purpose=f"Use {picked} for this intent.",
                    reason="best legal candidate",
                )
            ],
            budget_pressure="none",
        )

    canonical, _ = build_canonical_execution_plan(plan, selector=traced_selector)

    assert len(canonical.selection_trace) == len(plan.sections)
    first = canonical.selection_trace[0]
    assert first["candidate_set"]
    assert first["budget_before"]
    assert first["legal"] is True
    assert first["selected"][0]["reason"] == "best legal candidate"
    assert first["selected"][0]["block_id"]
    assert first["selected"][0]["lane"]

    def same_execution_different_reason(context):
        choice = traced_selector(context)
        choice.components[0].reason = "same choice, different explanation"
        return choice

    reason_changed, _ = build_canonical_execution_plan(
        plan,
        selector=same_execution_different_reason,
    )
    assert reason_changed.plan_hash == canonical.plan_hash
    assert (
        reason_changed.selection_trace[0]["selected"][0]["reason"] != first["selected"][0]["reason"]
    )


def test_misconception_prefers_pitfall_over_comparison_when_available() -> None:
    candidates = resolve_role_candidates("build")
    context = {
        "slot_purpose": "Confront the soil-food misconception",
        "misconception_focus": ["M1"],
        "allowed_components": [
            {
                "component_id": item,
                "cognitive_job": "x",
                "section_field": item,
            }
            for item in candidates.candidates
        ],
        "component_budget": {},
        "max_per_section": {},
    }
    if "pitfall-alert" not in candidates.candidates:
        # build role may not include pitfall; model role does — use model.
        candidates = resolve_role_candidates("model")
        context["allowed_components"] = [
            {
                "component_id": item,
                "cognitive_job": "x",
                "section_field": item,
            }
            for item in candidates.candidates
        ]
    choice = heuristic_select_components(context)
    if "pitfall-alert" in candidates.candidates:
        assert choice.components[0].slug == "pitfall-alert"


def test_selector_context_contains_capabilities() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)
    section = plan.sections[0]
    candidates = resolve_role_candidates(section.role)
    context = build_selector_prompt_context(section=section, candidates=candidates)
    assert context["allowed_components"]
    assert "capabilities" in context["allowed_components"][0]


def test_out_of_set_selection_raises() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[0])
    plan = intent_plan_to_structural_plan(intent)

    def bad_selector(_context):
        return SelectorChoice(
            components=[SelectedComponent(slug="timeline-block", purpose="nope", reason="x")]
        )

    with pytest.raises(SelectionValidationError):
        build_canonical_execution_plan(plan, selector=bad_selector)

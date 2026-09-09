"""R03 Print gates: model selector or sealed plan without reselect."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring.capability_selector import CapabilitySelection
from print.generation.native_production import build_closed_print_production_plan_async
from print.generation.selection_snapshot import (
    build_print_selection_snapshot_async,
    select_print_with_model_async,
)
from print.generation.whole_lesson.form_plan import FormDecision, FormPlan
from print.generation.whole_lesson.legality import LessonLegalitySnapshot, legality_hash
from print.resources.native_policy import default_print_policy, policy_version_and_hash


class RecordingChoose:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def __call__(self, context: dict) -> CapabilitySelection:
        self.calls.append(context)
        return CapabilitySelection(
            capability_id=self.responses.pop(0),
            reason="mock print selection",
        )


def _plan(*, brief: str, intent: str = "explain") -> TeachingPlan:
    return TeachingPlan(
        arc="Print selection fixture",
        teaching_plan_id="tp-r03-print",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="form choice",
                blocks=[
                    TeachingPlanBlock(
                        id="b-explain",
                        position=0,
                        intent=intent,
                        brief=brief,
                        evidence="Evidence",
                    )
                ],
            )
        ],
    )


def _packet(plan: TeachingPlan) -> SimpleNamespace:
    return SimpleNamespace(
        lesson=SimpleNamespace(
            path_lesson_id="lesson-r03",
            title="Fixture lesson",
            subject="science",
        ),
        approved_items=[],
        required_visual_slots=lambda: [],
    )


def _legality(*, explain_forms: list[str] | None = None) -> LessonLegalitySnapshot:
    forms = explain_forms or ["prose", "list", "table"]
    snap = LessonLegalitySnapshot(
        resource_id="lesson",
        catalogue_version="test",
        catalogue_hash="pending",
        permitted_intents=["explain", "summarise"],
        excluded_intents=[],
        typical_by_slot={"explain": ["explain"]},
        permitted_objects=forms + ["figure", "choices"],
        compatible_objects_by_intent={
            "explain": forms,
            "summarise": ["prose", "list"],
        },
    )
    return snap.model_copy(update={"catalogue_hash": legality_hash(snap)})


@pytest.mark.asyncio
async def test_r03_g02_print_invokes_selector_or_consumes_sealed_plan() -> None:
    """R03-G02: ambiguous Print uses selector; sealed plan skips second select."""
    plan = _plan(brief="Explain evaporation in causal prose.")
    packet = _packet(plan)
    legality = _legality()
    choose = RecordingChoose(["table"])

    _, snapshot, _ = await build_closed_print_production_plan_async(
        teaching_plan=plan,
        packet=packet,
        legality=legality,
        choose=choose,
    )
    assert snapshot.decisions[0].form_id == "table"
    assert len(choose.calls) == 1

    sealed = FormPlan.model_validate(
        {
            "sections": [
                {
                    "slot_id": "explain",
                    "forms": [
                        FormDecision(
                            block_id="b-explain",
                            object="prose",
                            placement="main",
                            reason="model planner",
                        )
                    ],
                }
            ]
        }
    )
    sealed_choose = RecordingChoose(["table"])
    _, sealed_snapshot, _ = await build_closed_print_production_plan_async(
        teaching_plan=plan,
        packet=packet,
        legality=legality,
        sealed_form_plan=sealed,
        choose=sealed_choose,
    )
    assert sealed_snapshot.decisions[0].form_id == "prose"
    assert sealed_choose.calls == []


@pytest.mark.asyncio
async def test_r03_g02_sole_print_form_skips_selector() -> None:
    """Sole legal form per block avoids unnecessary selector call."""
    plan = _plan(brief="Summarise takeaways.", intent="summarise")
    legality = _legality()
    candidate_map = {"b-explain": ("prose",)}
    choose = RecordingChoose([])
    _, policy_hash = policy_version_and_hash(default_print_policy())
    await build_print_selection_snapshot_async(
        plan,
        candidate_map=candidate_map,
        teaching_plan_hash="hash-print-sole",
        native_policy_hash=policy_hash,
        package_contract_hash="pkg-print",
        choose=choose,
    )
    assert choose.calls == []


@pytest.mark.asyncio
async def test_r03_g03_print_nonfirst_candidate_honored() -> None:
    """Print production honors lexically-disfavored nonfirst mock selection."""
    plan = _plan(brief="Summarise the lesson takeaways briefly.", intent="summarise")
    candidate_map = {"b-explain": ("prose", "list")}
    nonfirst = "list"
    choose = RecordingChoose([nonfirst])
    decisions = await select_print_with_model_async(
        plan,
        candidate_map=candidate_map,
        choose=choose,
    )
    assert decisions[0].form_id == nonfirst
    assert len(choose.calls) == 1

from __future__ import annotations

from unittest.mock import patch

from contracts.lectio import get_component_card
from generation.v3_studio.prompts import _planner_index_block, build_v3_shared_prefix
from v3_blueprint.planning.section_expander import build_stage2_system_prompt
from v3_blueprint.planning.structural_planner import build_stage1_system_prompt
from v3_execution.models import (
    QuestionWriterWorkOrder,
    SectionWriterWorkOrder,
    SourceOfTruthEntry,
    WriterQuestion,
    WriterSection,
    WriterSectionComponent,
)
from v3_execution.prompts.question_writer import build_question_writer_prompt
from v3_execution.prompts.section_writer import build_section_writer_prompt


def test_stage1_and_stage2_prompts_share_stable_prefix() -> None:
    prefix = build_v3_shared_prefix()

    with patch("v3_blueprint.planning.structural_planner._planner_index_block", return_value="PLANNER BLOCK"):
        assert build_stage1_system_prompt().startswith(prefix)
    assert build_stage2_system_prompt().startswith(prefix)


def test_stage1_component_selector_context_labels_cognitive_job_and_section_field() -> None:
    card = get_component_card("worked-example-card")
    assert card is not None

    planner_block = _planner_index_block()

    assert (
        "worked-example-card "
        f"| section_field={card['section_field']} "
        f"| cognitive_job={card['cognitive_job']}"
    ) in planner_block


def test_path_prepared_stage1_uses_zero_to_three_belief_tested_misconceptions() -> None:
    legacy_prompt = build_stage1_system_prompt()
    path_prompt = build_stage1_system_prompt(path_prepared=True)

    assert "2-4 misconceptions" in legacy_prompt
    assert "2-4 misconceptions" not in path_prompt
    assert "ZERO to THREE misconceptions" in path_prompt
    assert "confidently choose a corresponding wrong answer" in path_prompt
    assert "A card has 0-3 real misconceptions" in path_prompt


def test_stage1_role_instructions_name_skeleton_slots_as_authority() -> None:
    prompt = build_stage1_system_prompt()

    assert "supplied skeleton slot catalog" in prompt
    assert "active resource spec roles" not in prompt


def test_writer_prompts_share_stable_prefix() -> None:
    prefix = build_v3_shared_prefix()
    section_order = SectionWriterWorkOrder(
        work_order_id="wo-1",
        section=WriterSection(
            id="intro",
            title="Intro",
            learning_intent="Understand the anchor",
            components=[
                WriterSectionComponent(
                    component_id="hook-hero",
                    content_intent="Introduce the anchor example.",
                )
            ],
        ),
        source_of_truth=[SourceOfTruthEntry(key="anchor", text="Pizza slices")],
        template_id="guided-concept-path",
    )
    question_order = QuestionWriterWorkOrder(
        work_order_id="wo-2",
        section_id="intro",
        questions=[
            WriterQuestion(
                id="q1",
                difficulty="warm",
                expected_answer="One half",
            )
        ],
        source_of_truth=[SourceOfTruthEntry(key="anchor", text="Pizza slices")],
    )

    with (
        patch("contracts.lectio.get_formatting_policy", return_value={}),
        patch(
            "v3_execution.prompts.section_writer.format_component_contract_for_writer",
            return_value="contract block",
        ),
    ):
        assert build_section_writer_prompt(section_order).startswith(prefix)
    assert build_question_writer_prompt(question_order).startswith(prefix)


def test_skip_expander_writer_prompt_uses_plan_structure(monkeypatch) -> None:  # noqa: ANN001
    from v3_execution.models import WriterMisconception

    monkeypatch.setenv("V3_SKIP_EXPANDER", "true")
    section_order = SectionWriterWorkOrder(
        work_order_id="wo-1",
        section=WriterSection(
            id="practice",
            title="Practice",
            learning_intent="unused under skip",
            role="apply",
            transition_note="Apply the model from explain.",
            card_id="fractions.equivalent",
            anchor_example="A sunny windowsill plant making glucose from light, water, and CO2.",
            anchor_reuse_scope="all sections",
            misconceptions=[
                WriterMisconception(
                    id="M1",
                    description="Plants get their food by absorbing nutrients from soil.",
                ),
                WriterMisconception(
                    id="M2",
                    description="Photosynthesis is just the opposite of breathing.",
                ),
            ],
            exclusions=[],
            components=[
                WriterSectionComponent(
                    component_id="hook-hero",
                    teacher_label="Hook Hero",
                    content_intent="Have learners compare two fraction strips.",
                )
            ],
        ),
        source_of_truth=[SourceOfTruthEntry(key="anchor", text="Pizza slices")],
        component_cards={
            "hook-hero": {
                "component_id": "hook-hero",
                "section_field": "hook",
                "role": "orient",
                "cognitive_job": "activate",
                "capacity": {"max_words": 80},
                "component_constraints": ["Keep it concrete"],
                "field_contracts": {},
            }
        },
        template_id="guided-concept-path",
    )

    with patch("contracts.lectio.get_formatting_policy", return_value={}):
        prompt = build_section_writer_prompt(section_order)

    assert "STRUCTURED CONSTRAINTS" in prompt
    assert "ANCHOR: A sunny windowsill plant making glucose from light, water, and CO2." in prompt
    assert "ANCHOR_INSTRUCTION:" in prompt
    assert "- M1: Plants get their food by absorbing nutrients from soil." in prompt
    assert "- M2: Photosynthesis is just the opposite of breathing." in prompt
    assert "EXCLUSIONS" in prompt and "(none declared)" in prompt
    assert "- ROLE: apply" in prompt
    assert "- TRANSITION_NOTE: Apply the model from explain." in prompt
    assert "purpose (from plan slot): Have learners compare two fraction strips." in prompt
    assert "capacity: max_words=80" in prompt
    assert "LEARNING INTENT:" not in prompt
    assert "LECTIO COMPONENT CONTRACTS:" not in prompt
    # Must stay a list of bullets, not a concatenated brief paragraph.
    assert "PLAN CONSTRAINTS" not in prompt

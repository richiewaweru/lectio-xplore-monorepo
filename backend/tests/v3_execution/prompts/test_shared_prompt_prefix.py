from __future__ import annotations

from unittest.mock import patch

from generation.v3_studio.prompts import build_v3_shared_prefix
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

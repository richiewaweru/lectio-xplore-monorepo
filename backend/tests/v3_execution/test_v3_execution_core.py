from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.lectio import get_section_field_for_component

from v3_blueprint.models import ProductionBlueprint
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.models import (
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    QuestionWriterWorkOrder,
    VisualGeneratorWorkOrder,
    WriterQuestion,
)
from v3_execution.runtime import validation as v
from v3_execution.runtime.runner import run_generation
from v3_review.models import CoherenceReport
from v3_review.models import ReviewIssue


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def test_compile_execution_bundle() -> None:
    bp = _load_example("amara_compound_area.json")
    bundle = compile_execution_bundle(
        bp,
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
    )
    assert bundle.section_orders
    assert bundle.question_orders
    assert bundle.visual_orders
    assert bundle.answer_key_order is not None


def test_validate_visual_accepts_http_scheme() -> None:
    from v3_execution.models import VisualPlanItem

    order = VisualGeneratorWorkOrder(
        work_order_id="v1",
        visual=VisualPlanItem(id="v1", attaches_to="practice"),
        source_of_truth=[],
    )
    bad_scheme = GeneratedVisualBlock(
        visual_id="v1",
        attaches_to="practice",
        mode="diagram",
        image_url="ftp://bad",
        source_work_order_id="v1",
    )
    errs = v.validate_visual_block(bad_scheme, order)
    assert errs

    good = GeneratedVisualBlock(
        visual_id="v1",
        attaches_to="practice",
        mode="diagram",
        image_url="https://cdn.example/image.png",
        source_work_order_id="v1",
    )
    assert not v.validate_visual_block(good, order)


def test_validate_question_block_rejects_answer_drift() -> None:
    order = QuestionWriterWorkOrder(
        work_order_id="q1",
        section_id="practice",
        questions=[
            WriterQuestion(id="q1", difficulty="warm", expected_answer="nine"),
        ],
        source_of_truth=[],
    )
    block = GeneratedQuestionBlock(
        question_id="q1",
        section_id="practice",
        difficulty="warm",
        data={"question": "?"},
        expected_answer="wrong",
        source_work_order_id="q1",
    )
    assert v.validate_question_block(block, order)


@pytest.mark.asyncio
async def test_runner_with_stubbed_executors(monkeypatch: pytest.MonkeyPatch) -> None:
    bp = _load_example("amara_compound_area.json")

    async def stub_section(order, emit, **_: object) -> list[GeneratedComponentBlock]:
        blocks: list[GeneratedComponentBlock] = []
        for position, component in enumerate(order.section.components):
            field = get_section_field_for_component(component.component_id) or "explanation"
            if field == "explanation":
                payload = {"body": component.content_intent, "emphasis": []}
            elif field == "worked_example":
                payload = {
                    "title": component.content_intent,
                    "solution": [{"step": "", "latex": "", "explain": "", "diagramRef": []}],
                    "answer": "",
                }
            elif field == "summary":
                payload = {"paragraphs": [component.content_intent], "key_points": [], "cta": {}}
            elif field == "hook":
                payload = {
                    "headline": component.content_intent,
                    "body": component.content_intent,
                    "anchor": "anchor",
                }
            elif field == "practice":
                payload = {"introduction": "", "items": [], "footnote": "", "diagram": None}
            else:
                payload = {"detail": component.content_intent}
            blk = GeneratedComponentBlock(
                block_id=f"b-{component.component_id}",
                section_id=order.section.id,
                component_id=component.component_id,
                section_field=field,
                position=position,
                data=payload,
                source_work_order_id=order.work_order_id,
            )
            blocks.append(blk)
            await emit(
                "component_ready",
                {
                    "component_id": blk.component_id,
                    "section_id": blk.section_id,
                    "data": blk.data,
                },
            )
        return blocks

    async def stub_questions(
        order,
        emit,
        **_: object,
    ) -> list[GeneratedQuestionBlock]:
        out: list[GeneratedQuestionBlock] = []
        for question in order.questions:
            out.append(
                GeneratedQuestionBlock(
                    question_id=question.id,
                    section_id=order.section_id,
                    difficulty=question.difficulty,
                    data={
                        "question": question.id,
                        "difficulty": question.difficulty,
                        "hints": [],
                        "problem_type": "open",
                    },
                    expected_answer=question.expected_answer,
                    source_work_order_id=order.work_order_id,
                )
            )
        await emit("question_ready", {"section_id": order.section_id})
        return out

    async def stub_visual(order, emit, **_kwargs) -> list[GeneratedVisualBlock]:
        blk = GeneratedVisualBlock(
            visual_id=order.visual.id,
            attaches_to=order.visual.attaches_to,
            mode="diagram",
            image_url="http://localhost/generated.png",
            source_work_order_id=order.work_order_id,
            caption="caption",
            alt_text="caption",
        )
        await emit("visual_ready", {"visual_id": blk.visual_id})
        return [blk]

    async def noop_answer(order, emit, **_kwargs) -> GeneratedAnswerKeyBlock:  # noqa: ARG002
        return GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[{"question_id": q.id, "student_answer": q.expected_answer} for q in order.questions],
            source_work_order_id=order.work_order_id,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.execute_section", stub_section)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_questions", stub_questions)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_visual", stub_visual)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_answer_key", noop_answer)

    async def stub_coherence_review(
        blueprint,
        draft_pack,
        emit_event,
        **_kwargs: object,
    ) -> CoherenceReport:
        _ = blueprint
        _ = emit_event
        return CoherenceReport(
            blueprint_id=draft_pack.blueprint_id,
            generation_id=draft_pack.generation_id,
            status="passed",
            deterministic_passed=True,
            llm_review_passed=True,
            issues=[],
            repair_targets=[],
        )

    monkeypatch.setattr("v3_execution.runtime.runner.run_coherence_review", stub_coherence_review)

    captured: list[tuple[str, dict]] = []

    async def capture(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    result = await run_generation(
        blueprint=bp,
        generation_id="g-x",
        blueprint_id="b-x",
        template_id="guided-concept-path",
        emit_event=capture,
        model_overrides=None,
    )

    assert result.component_blocks
    assert result.question_blocks
    assert result.visual_blocks
    assert result.answer_key
    event_types = [event for event, _payload in captured]
    assert "draft_pack_ready" in event_types
    assert "final_pack_ready" in event_types
    assert "resource_finalised" in event_types
    assert "generation_complete" in event_types

    draft_idx = event_types.index("draft_pack_ready")
    final_idx = event_types.index("final_pack_ready")
    resource_idx = event_types.index("resource_finalised")
    complete_idx = event_types.index("generation_complete")
    assert draft_idx < final_idx < resource_idx < complete_idx

    draft_payload = next(payload for event, payload in captured if event == "draft_pack_ready")
    assert isinstance(draft_payload.get("pack"), dict)
    assert "draft_preview" not in draft_payload

    final_payload = next(payload for event, payload in captured if event == "final_pack_ready")
    assert isinstance(final_payload.get("pack"), dict)


@pytest.mark.asyncio
async def test_runner_emits_draft_status_updated_when_blocking_issues_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bp = _load_example("amara_compound_area.json")

    async def stub_section(order, emit, **_: object) -> list[GeneratedComponentBlock]:
        blocks: list[GeneratedComponentBlock] = []
        for position, component in enumerate(order.section.components):
            field = get_section_field_for_component(component.component_id) or "explanation"
            blk = GeneratedComponentBlock(
                block_id=f"b-{component.component_id}",
                section_id=order.section.id,
                component_id=component.component_id,
                section_field=field,
                position=position,
                data={"body": component.content_intent, "emphasis": []},
                source_work_order_id=order.work_order_id,
            )
            blocks.append(blk)
            await emit(
                "component_ready",
                {
                    "component_id": blk.component_id,
                    "section_id": blk.section_id,
                    "data": blk.data,
                },
            )
        return blocks

    async def stub_questions(order, emit, **_: object) -> list[GeneratedQuestionBlock]:
        out: list[GeneratedQuestionBlock] = []
        for question in order.questions:
            out.append(
                GeneratedQuestionBlock(
                    question_id=question.id,
                    section_id=order.section_id,
                    difficulty=question.difficulty,
                    data={
                        "question": question.id,
                        "difficulty": question.difficulty,
                        "hints": [],
                        "problem_type": "open",
                    },
                    expected_answer=question.expected_answer,
                    source_work_order_id=order.work_order_id,
                )
            )
        await emit("question_ready", {"section_id": order.section_id})
        return out

    async def stub_visual(order, emit, **_kwargs) -> list[GeneratedVisualBlock]:
        blk = GeneratedVisualBlock(
            visual_id=order.visual.id,
            attaches_to=order.visual.attaches_to,
            mode="diagram",
            image_url="http://localhost/generated.png",
            source_work_order_id=order.work_order_id,
            caption="caption",
            alt_text="caption",
        )
        await emit("visual_ready", {"visual_id": blk.visual_id})
        return [blk]

    async def noop_answer(order, emit, **_kwargs) -> GeneratedAnswerKeyBlock:  # noqa: ARG002
        return GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[{"question_id": q.id, "student_answer": q.expected_answer} for q in order.questions],
            source_work_order_id=order.work_order_id,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.execute_section", stub_section)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_questions", stub_questions)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_visual", stub_visual)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_answer_key", noop_answer)

    async def stub_coherence_review(
        blueprint,
        draft_pack,
        emit_event,
        **_kwargs: object,
    ) -> CoherenceReport:
        _ = blueprint
        _ = emit_event
        issue = ReviewIssue(
            severity="blocking",
            category="missing_planned_content",
            message="Blocking issue remains.",
            suggested_repair_executor="section_writer",
        )
        return CoherenceReport(
            blueprint_id=draft_pack.blueprint_id,
            generation_id=draft_pack.generation_id,
            status="failed",
            deterministic_passed=False,
            llm_review_passed=False,
            issues=[issue],
            repair_targets=[],
            blocking_count=1,
            major_count=0,
            minor_count=0,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.run_coherence_review", stub_coherence_review)

    captured: list[tuple[str, dict]] = []

    async def capture(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    await run_generation(
        blueprint=bp,
        generation_id="g-y",
        blueprint_id="b-y",
        template_id="guided-concept-path",
        emit_event=capture,
        model_overrides=None,
    )

    event_types = [event for event, _payload in captured]
    assert "draft_pack_ready" in event_types
    assert "draft_status_updated" in event_types
    assert "final_pack_ready" not in event_types
    assert "resource_finalised" in event_types
    assert "generation_complete" in event_types

    draft_idx = event_types.index("draft_pack_ready")
    draft_status_idx = event_types.index("draft_status_updated")
    resource_idx = event_types.index("resource_finalised")
    complete_idx = event_types.index("generation_complete")
    assert draft_idx < draft_status_idx < resource_idx < complete_idx

    updated_payload = next(payload for event, payload in captured if event == "draft_status_updated")
    assert isinstance(updated_payload.get("pack"), dict)


@pytest.mark.asyncio
async def test_runner_records_strategic_trace_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bp = _load_example("amara_compound_area.json")

    async def stub_section(order, emit, **_: object) -> list[GeneratedComponentBlock]:
        blocks: list[GeneratedComponentBlock] = []
        for position, component in enumerate(order.section.components):
            field = get_section_field_for_component(component.component_id) or "explanation"
            blk = GeneratedComponentBlock(
                block_id=f"b-{component.component_id}",
                section_id=order.section.id,
                component_id=component.component_id,
                section_field=field,
                position=position,
                data={"body": component.content_intent, "emphasis": []},
                source_work_order_id=order.work_order_id,
            )
            blocks.append(blk)
            await emit(
                "component_ready",
                {
                    "component_id": blk.component_id,
                    "section_id": blk.section_id,
                    "data": blk.data,
                },
            )
        return blocks

    async def stub_questions(order, emit, **_: object) -> list[GeneratedQuestionBlock]:
        out: list[GeneratedQuestionBlock] = []
        for question in order.questions:
            out.append(
                GeneratedQuestionBlock(
                    question_id=question.id,
                    section_id=order.section_id,
                    difficulty=question.difficulty,
                    data={"question": question.id, "difficulty": question.difficulty, "hints": [], "problem_type": "open"},
                    expected_answer=question.expected_answer,
                    source_work_order_id=order.work_order_id,
                )
            )
        await emit("question_ready", {"section_id": order.section_id})
        return out

    async def stub_visual(order, emit, **_kwargs) -> list[GeneratedVisualBlock]:
        blk = GeneratedVisualBlock(
            visual_id=order.visual.id,
            attaches_to=order.visual.attaches_to,
            mode="diagram",
            image_url="http://localhost/generated.png",
            source_work_order_id=order.work_order_id,
            caption="caption",
            alt_text="caption",
        )
        await emit("visual_ready", {"visual_id": blk.visual_id})
        return [blk]

    async def noop_answer(order, emit, **_kwargs) -> GeneratedAnswerKeyBlock:  # noqa: ARG002
        return GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[{"question_id": q.id, "student_answer": q.expected_answer} for q in order.questions],
            source_work_order_id=order.work_order_id,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.execute_section", stub_section)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_questions", stub_questions)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_visual", stub_visual)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_answer_key", noop_answer)

    async def stub_coherence_review(
        blueprint,
        draft_pack,
        emit_event,
        **_kwargs: object,
    ) -> CoherenceReport:
        _ = blueprint
        _ = emit_event
        issue = ReviewIssue(
            severity="minor",
            category="print_risk",
            message="Minor warning remains.",
            suggested_repair_executor="section_writer",
        )
        return CoherenceReport(
            blueprint_id=draft_pack.blueprint_id,
            generation_id=draft_pack.generation_id,
            status="passed_with_warnings",
            deterministic_passed=True,
            llm_review_passed=True,
            issues=[issue],
            repair_targets=[],
            minor_count=1,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.run_coherence_review", stub_coherence_review)

    class StubTraceWriter:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def record_work_orders(self, **_kwargs):
            self.calls.append("record_work_orders")

        async def record_execution_summary(self, **_kwargs):
            self.calls.append("record_execution_summary")

        async def record_draft_pack(self, **_kwargs):
            self.calls.append("record_draft_pack")

        async def record_booklet_status(self, **_kwargs):
            self.calls.append("record_booklet_status")

        async def record_review_summary(self, **_kwargs):
            self.calls.append("record_review_summary")

        async def record_repair_summary(self, **_kwargs):
            self.calls.append("record_repair_summary")

        async def record_final_pack(self, **_kwargs):
            self.calls.append("record_final_pack")

        async def record_terminal(self, **_kwargs):
            self.calls.append("record_terminal")

    writer = StubTraceWriter()

    async def capture(_event_type: str, _payload: dict) -> None:
        return None

    await run_generation(
        blueprint=bp,
        generation_id="g-trace",
        blueprint_id="b-trace",
        template_id="guided-concept-path",
        emit_event=capture,
        model_overrides=None,
        trace_writer=writer,  # type: ignore[arg-type]
    )

    assert "record_work_orders" in writer.calls
    assert "record_execution_summary" in writer.calls
    assert "record_draft_pack" in writer.calls
    assert "record_booklet_status" in writer.calls
    assert "record_review_summary" in writer.calls
    assert "record_repair_summary" in writer.calls
    assert "record_final_pack" in writer.calls
    assert writer.calls[-1] == "record_terminal"


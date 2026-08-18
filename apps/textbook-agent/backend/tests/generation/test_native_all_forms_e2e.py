"""Gate 9 — mocked full native E2E across all 8 forms."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
import yaml

from contracts.lectio_page import validate_document
from generation.page_objects import (
    WRITER_PROVIDER_OUTPUTS,
    ContentValidationError,
    WriterContext,
    dispatch_writer_async,
)
from generation.page_objects.document_assembly import (
    canonical_document_sha256,
    persist_document_json,
    reload_document,
)
from generation.page_objects.scripted_provider import ScriptedWriterProvider
from generation.page_objects.views import student_document, teacher_document
from planning.whole_lesson.figure_ids import stable_figure_request_id
from v3_blueprint.planning.models import PlannedBlock

REPO_ROOT = Path(__file__).resolve().parents[5]
PACK = REPO_ROOT / "docs" / "packs" / "xplore_native_e2e_implementation_pack_v1"
FIXTURES = PACK / "08_FIXTURES"
SCENARIOS = PACK / "09_MOCK_SCENARIOS" / "mock_llm_scenarios.yaml"
TOOL = Path(__file__).resolve().parents[2] / "tools" / "run_native_e2e_fixture.py"


def _load_driver():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("run_native_e2e_fixture", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_all_valid_out_of_order_e2e_flow() -> None:
    driver = _load_driver()
    lesson = driver.load_json(FIXTURES / "lesson_request_all_forms.json")
    form_plan = driver.load_form_plan(FIXTURES / "form_plan_all_forms.json")
    assessment = driver.load_json(FIXTURES / "assessment_bundle.json")
    expected = driver.load_json(FIXTURES / "expected_lectio_document_v2.json")
    scenarios = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))

    result, document, timeline, provider = await driver.run_mock_scenario(
        name="all_valid_out_of_order",
        lesson=lesson,
        form_plan=form_plan,
        assessment=assessment,
        expected=expected,
        scenarios_payload=scenarios,
    )
    assert result.status == "passed"
    assert document is not None
    errors = validate_document(document)
    assert errors == []

    objects = {
        block["object"]
        for section in document["sections"]
        for block in section["blocks"]
    }
    assert objects >= {
        "prose",
        "list",
        "table",
        "figure",
        "aside",
        "worked-example",
        "questions",
        "choices",
    }
    assert "answer_key" in document
    figure = next(
        block
        for section in document["sections"]
        for block in section["blocks"]
        if block["object"] == "figure"
    )
    assert figure["content"]["asset"]["status"] == "pending"

    envelope = persist_document_json(None, document)
    reloaded = reload_document(envelope)
    assert canonical_document_sha256(document) == canonical_document_sha256(reloaded)

    student = student_document(document)
    teacher = teacher_document(document)
    assert "answer_key" not in student
    assert "answer_key" in teacher

    assert [entry["stage"] for entry in timeline] == [
        "writing_sections",
        "assembling",
        "ready",
    ]
    assert provider.call_count() >= 6  # non-assessment LLM-path blocks


@pytest.mark.asyncio
async def test_invalid_json_then_valid_repair() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "invalid_json_then_valid": {
                "responses": {
                    "s1-prose": [
                        {"attempt": 1, "mode": "raw", "value": '{"paragraphs": ['},
                        {"attempt": 2, "mode": "valid"},
                    ]
                }
            }
        },
        scenario_name="invalid_json_then_valid",
        default_valid={"prose": {"paragraphs": ["Repaired prose."]}},
    )
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s1-prose",
                "position": 0,
                "intent": "orient",
                "object": "prose",
                "evidence": "need opening",
                "brief": "Explain light energy.",
            }
        ),
        use_llm=True,
        section_id="section-1",
        generation_id="gate9-repair",
    )
    result = await dispatch_writer_async(ctx, provider=provider)
    assert result.content["paragraphs"] == ["Repaired prose."]
    assert provider.call_count() == 2
    assert len(provider.repair_prompts()) == 1


@pytest.mark.asyncio
async def test_permanently_invalid_raises() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "permanently_invalid": {
                "responses": {
                    "s1-prose": [
                        {"attempt": 1, "mode": "dict", "value": {"paragraphs": []}},
                        {"attempt": 2, "mode": "dict", "value": {"wrong": True}},
                    ]
                }
            }
        },
        scenario_name="permanently_invalid",
    )
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s1-prose",
                "position": 0,
                "intent": "orient",
                "object": "prose",
                "evidence": "need opening",
                "brief": "Explain light energy.",
            }
        ),
        use_llm=True,
        section_id="section-1",
        generation_id="gate9-perm-invalid",
    )
    with pytest.raises(ContentValidationError):
        await dispatch_writer_async(ctx, provider=provider)


@pytest.mark.asyncio
async def test_figure_missing_alt_then_valid() -> None:
    provider = ScriptedWriterProvider(
        scenarios={
            "figure_missing_alt_then_valid": {
                "responses": {
                    "s2-figure": [
                        {
                            "attempt": 1,
                            "mode": "dict",
                            "value": {
                                "asset": {
                                    "kind": "image",
                                    "status": "pending",
                                    "request_id": "x",
                                },
                                "caption": "x",
                            },
                        },
                        {"attempt": 2, "mode": "valid"},
                    ]
                }
            }
        },
        scenario_name="figure_missing_alt_then_valid",
        default_valid={
            "figure": {
                "asset": {"kind": "image"},
                "alt_text": "A pending figure of a leaf",
                "caption": "Caption",
            }
        },
    )
    ctx = WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "s2-figure",
                "position": 0,
                "intent": "show-structure",
                "object": "figure",
                "evidence": "need diagram",
                "brief": "Diagram sunlight reaching a leaf.",
                "placement": "spanning",
            }
        ),
        use_llm=True,
        section_id="section-2",
        generation_id="gate9-figure",
    )
    result = await dispatch_writer_async(ctx, provider=provider)
    expected_request_id = stable_figure_request_id(
        generation_id="gate9-figure",
        block_id="s2-figure",
    )
    assert result.content["alt_text"]
    assert result.content["asset"]["status"] == "pending"
    assert result.request_id == expected_request_id
    assert result.content["asset"]["request_id"] == expected_request_id
    assert provider.call_count() == 2
    provider_output = provider.calls[-1].raw_result
    assert hasattr(provider_output, "model_dump")
    provider_payload = provider_output.model_dump(mode="json", exclude_none=True)
    assert set(provider_payload["asset"]) == {"kind"}
    assert "request_id" not in provider_payload["asset"]
    assert "status" not in provider_payload["asset"]


@pytest.mark.asyncio
async def test_scripted_valid_mode_rejects_provider_owned_figure_identity() -> None:
    provider = ScriptedWriterProvider(
        default_valid={
            "figure": {
                "asset": {
                    "kind": "image",
                    "request_id": "evil-provider-id",
                    "status": "ready",
                },
                "alt_text": "A leaf",
                "caption": "Leaf",
            }
        }
    )

    with pytest.raises(ValidationError):
        await provider.write(
            object_id="figure",
            section_id="section-1",
            block_id="figure-b1",
            attempt=1,
            prompt="test",
            output_model=WRITER_PROVIDER_OUTPUTS["figure"],
        )


def test_e2e_helper_path_does_not_import_legacy_resume() -> None:
    source = TOOL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    legacy_names = {"resume_stage2", "retry_failed_section"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name not in legacy_names
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in legacy_names
    assert "import resume_stage2" not in source
    assert "import retry_failed_section" not in source


def test_expected_fixture_still_validates() -> None:
    doc = json.loads((FIXTURES / "expected_lectio_document_v2.json").read_text(encoding="utf-8"))
    assert validate_document(doc) == []

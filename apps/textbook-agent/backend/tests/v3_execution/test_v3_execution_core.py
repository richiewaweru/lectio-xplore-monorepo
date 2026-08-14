from __future__ import annotations

import json
import io
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from contracts.lectio import get_section_field_for_component

from v3_blueprint.models import ProductionBlueprint
from v3_execution.compile_orders import compile_execution_bundle
from v3_execution.executors.visual_executor import _cache_key_for_visual, execute_visual
from v3_execution.models import (
    ExecutorOutcome,
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    QuestionWriterWorkOrder,
    VisualGeneratorWorkOrder,
    VisualFrameSpec,
    VisualPlanItem,
    WriterQuestion,
)
from v3_execution.runtime import validation as v
from v3_execution.runtime.runner import run_generation
from v3_review.models import CoherenceReport
from v3_review.models import ReviewIssue
from media.qc.visual_qc import VisualQCVerdict


def _png_bytes(size: tuple[int, int] = (1024, 1024)) -> bytes:
    image = Image.new("RGB", size, "#dbeafe")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture(autouse=True)
def _disable_visual_qc_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.visual_qc_enabled",
        lambda: False,
    )


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _load_v3_fixture(filename: str) -> dict:
    raw = Path(__file__).resolve().parents[1] / "fixtures" / filename
    return json.loads(raw.read_text(encoding="utf-8"))


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


@pytest.mark.asyncio
async def test_runner_skips_all_ready_sections_and_preserves_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blueprint = ProductionBlueprint.model_validate(_load_v3_fixture("gen_5aed3804_blueprint.json"))
    pack = _load_v3_fixture("gen_5aed3804_pack.json")
    preserved = pack["sections"]

    async def forbidden(*_args: object, **_kwargs: object) -> list:
        raise AssertionError("ready section executor must not run")

    async def no_answer(*_args: object, **_kwargs: object) -> None:
        return None

    async def coherence(_blueprint, draft_pack, _emit, **_kwargs: object) -> CoherenceReport:
        return CoherenceReport(
            blueprint_id=draft_pack.blueprint_id,
            generation_id=draft_pack.generation_id,
            status="passed",
            deterministic_passed=True,
        )

    monkeypatch.setattr("v3_execution.runtime.runner.execute_section", forbidden)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_questions", forbidden)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_visual", forbidden)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_answer_key", no_answer)
    monkeypatch.setattr("v3_execution.runtime.runner.run_coherence_review", coherence)
    captured: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    await run_generation(
        blueprint=blueprint,
        generation_id="resume-all-ready",
        blueprint_id="resume-blueprint",
        template_id="guided-concept-path",
        emit_event=emit,
        preserved_ready_sections=preserved,
    )

    draft = next(payload["pack"] for event, payload in captured if event == "draft_pack_ready")
    assert draft["sections"] == preserved
    assert any(event == "generation_complete" for event, _payload in captured)


def test_visual_cache_key_is_stable_and_includes_constraints() -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-cache",
        visual=VisualPlanItem(
            id="vis-cache",
            attaches_to="model",
            mode="diagram",
            must_show=["label A"],
            must_not_show=["clutter"],
        ),
    )
    same = _cache_key_for_visual(prompt="draw it", order=order, model_name="grok")
    assert same == _cache_key_for_visual(prompt="draw it", order=order, model_name="grok")

    changed = order.model_copy(deep=True)
    changed.visual.must_show = ["label B"]
    assert same != _cache_key_for_visual(prompt="draw it", order=changed, model_name="grok")


@pytest.mark.asyncio
async def test_runner_emits_skeleton_ready_before_component_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bp = _load_example("amara_compound_area.json")

    async def stub_section(order, emit, **_: object) -> list[GeneratedComponentBlock]:
        blocks: list[GeneratedComponentBlock] = []
        for position, component in enumerate(order.section.components):
            field = get_section_field_for_component(component.component_id) or "explanation"
            block = GeneratedComponentBlock(
                block_id=f"b-{component.component_id}",
                section_id=order.section.id,
                component_id=component.component_id,
                section_field=field,
                position=position,
                data={"body": component.content_intent, "emphasis": []},
                source_work_order_id=order.work_order_id,
            )
            await emit(
                "component_ready",
                {
                    "component_id": block.component_id,
                    "section_id": block.section_id,
                    "section_field": block.section_field,
                    "data": block.data,
                },
            )
            blocks.append(block)
        return blocks

    async def stub_questions(order, emit, **_: object) -> list[GeneratedQuestionBlock]:
        _ = order
        await emit("question_ready", {"section_id": order.section_id})
        return []

    async def stub_visual(order, emit, **_kwargs) -> list[GeneratedVisualBlock]:
        _ = order
        _ = emit
        return []

    async def noop_answer(order, emit, **_kwargs) -> GeneratedAnswerKeyBlock:  # noqa: ARG002
        return GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[],
            source_work_order_id="answer-key-main",
        )

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
            issues=[],
        )

    monkeypatch.setattr("v3_execution.runtime.runner.execute_section", stub_section)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_questions", stub_questions)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_visual", stub_visual)
    monkeypatch.setattr("v3_execution.runtime.runner.execute_answer_key", noop_answer)
    monkeypatch.setattr("v3_execution.runtime.runner.run_coherence_review", stub_coherence_review)

    captured: list[tuple[str, dict]] = []

    async def capture(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    await run_generation(
        blueprint=bp,
        generation_id="g-skeleton",
        blueprint_id="b-skeleton",
        template_id="guided-concept-path",
        emit_event=capture,
        model_overrides=None,
    )

    event_types = [event for event, _payload in captured]
    skeleton_idx = event_types.index("skeleton_ready")
    assert event_types.index("work_orders_compiled") < skeleton_idx
    assert skeleton_idx < event_types.index("component_ready")

    skeleton_payload = captured[skeleton_idx][1]
    pack = skeleton_payload["pack"]
    expected_section_ids = [section.section_id for section in bp.sections]
    assert skeleton_payload["section_count"] == len(expected_section_ids)
    assert [section["section_id"] for section in pack["sections"]] == expected_section_ids
    assert all(section["section_id"] for section in pack["sections"])
    assert pack["status"] == "streaming_preview"
    assert pack["sections"][0]["components"][0]["component_id"]
    component_payload = next(payload for event, payload in captured if event == "component_ready")
    assert component_payload["section_id"] in expected_section_ids


def test_validate_visual_accepts_http_scheme() -> None:
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


def test_validate_visual_accepts_diagram_compare_mode() -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v1",
        visual=VisualPlanItem(id="v1", attaches_to="practice", mode="diagram_compare"),
        source_of_truth=[],
    )
    block = GeneratedVisualBlock(
        visual_id="v1",
        attaches_to="practice",
        mode="diagram_compare",
        image_url="https://cdn.example/compare.png",
        source_work_order_id="v1",
    )

    assert not v.validate_visual_block(block, order)


def test_validate_visual_accepts_flagged_quality_with_image_url() -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="wo-flagged",
        visual=VisualPlanItem(
            id="vis-flagged",
            attaches_to="practice",
            mode="diagram",
            purpose="support question",
        ),
    )
    block = GeneratedVisualBlock(
        visual_id="vis-flagged",
        attaches_to="practice",
        mode="diagram",
        image_url="https://cdn.example/flagged.png",
        source_work_order_id="wo-flagged",
        status="flagged_quality",
        qc_reasons=["label is faint"],
    )

    assert not v.validate_visual_block(block, order)


@pytest.mark.asyncio
async def test_execute_visual_series_sets_parent_visual_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-series",
        visual=VisualPlanItem(
            id="vis-model-0",
            attaches_to="model",
            component_id="diagram-series",
            mode="diagram_series",
            purpose="show progression",
            must_show=["consistent cell outline"],
            frames=[
                VisualFrameSpec(description="Frame one", must_show=["A"]),
                VisualFrameSpec(description="Frame two", must_show=["B"]),
            ],
        ),
        source_of_truth=[],
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            return SimpleNamespace(bytes=b"img", format="png", mime_type="image/png")

    class StubStore:
        async def store_image(self, *_args, **kwargs):
            return f"https://cdn.example/{kwargs['filename']}"

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    captured: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    blocks = await execute_visual(
        order,
        emit,
        trace_id="trace",
        generation_id="gen",
    )

    assert len(blocks) == 2
    assert all(block.parent_visual_id == "vis-model-0" for block in blocks)
    assert [block.frame_index for block in blocks] == [0, 1]
    assert all(block.component_id == "diagram-series" for block in blocks)
    assert all(block.status == "ready" for block in blocks)
    assert any(event == "visual_ready" for event, _ in captured)


@pytest.mark.asyncio
async def test_execute_visual_returns_failed_block_and_event_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-fail",
        visual=VisualPlanItem(
            id="vis-practice-0",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    async def stub_run_with_retries(_label, _attempt, max_retries):
        _ = max_retries
        return ExecutorOutcome(ok=False, errors=["provider timeout"])

    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    captured: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    blocks = await execute_visual(
        order,
        emit,
        trace_id="trace",
        generation_id="gen",
    )

    assert len(blocks) == 1
    failed = blocks[0]
    assert failed.status == "failed"
    assert failed.error_message == "provider timeout"
    assert failed.parent_visual_id is None
    assert failed.component_id == "diagram-block"
    failure_payload = next(payload for event, payload in captured if event == "visual_failed")
    assert failure_payload["attaches_to"] == "practice"
    assert failure_payload["component_id"] == "diagram-block"
    assert failure_payload["mode"] == "diagram"
    assert failure_payload["frame_count"] == 1
    assert failure_payload["error_summary"] == "provider timeout"


@pytest.mark.asyncio
async def test_execute_visual_qc_accept_uploads_initial_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-qc-accept",
        visual=VisualPlanItem(
            id="vis-qc-accept",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    class StubClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate_image(self, *, prompt: str):
            self.prompts.append(prompt)
            return SimpleNamespace(bytes=b"accepted-image", format="png", mime_type="image/png")

    class StubStore:
        def __init__(self) -> None:
            self.uploads: list[bytes] = []

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.uploads.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

    client = StubClient()
    store = StubStore()

    async def accept_qc(**_kwargs):
        return VisualQCVerdict(verdict="accept")

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", accept_qc)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "ready"
    assert len(client.prompts) == 1
    assert store.uploads == [b"accepted-image"]


@pytest.mark.asyncio
async def test_execute_visual_cache_hit_skips_provider_and_copies_cached_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-cache-hit",
        visual=VisualPlanItem(
            id="vis-cache-hit",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
            must_show=["axis labels"],
        ),
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            raise AssertionError("provider should not run on cache hit")

    class StubStore:
        def __init__(self) -> None:
            self.copied: list[tuple[str, str]] = []
            self.destinations: set[str] = set()

        async def image_exists(self, *, key: str) -> bool:
            if key.startswith("images/cache/"):
                return True
            return key in self.destinations

        async def copy_image(self, *, source_key: str, destination_key: str):
            self.copied.append((source_key, destination_key))
            self.destinations.add(destination_key)
            return f"https://cdn.example/{destination_key}"

        async def store_image(self, *_args, **_kwargs):
            raise AssertionError("cache hit should not upload generated bytes")

    store = StubStore()

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].image_url == "https://cdn.example/gen/practice/vis-cache-hit.png"
    assert len(store.copied) == 1
    assert store.copied[0][0].startswith("images/cache/")
    assert store.copied[0][1] == "gen/practice/vis-cache-hit.png"


@pytest.mark.asyncio
async def test_execute_visual_stale_cache_copy_falls_back_to_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-cache-stale",
        visual=VisualPlanItem(
            id="vis-cache-stale",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
    )

    class StubClient:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_image(self, *, prompt: str):
            _ = prompt
            self.calls += 1
            return SimpleNamespace(bytes=b"fresh-image", format="png", mime_type="image/png")

    class StubStore:
        def __init__(self) -> None:
            self.copied: list[tuple[str, str]] = []
            self.generated_uploads: list[bytes] = []

        async def image_exists(self, *, key: str) -> bool:
            if key.startswith("images/cache/"):
                return True
            return False

        async def copy_image(self, *, source_key: str, destination_key: str):
            self.copied.append((source_key, destination_key))
            return f"https://cdn.example/{destination_key}"

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.generated_uploads.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

        async def store_image_key(self, *, key: str, image_bytes: bytes, content_type: str):
            _ = key, image_bytes, content_type
            return "https://cdn.example/cache.png"

    client = StubClient()
    store = StubStore()

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].image_url == "https://cdn.example/vis-cache-stale.png"
    assert client.calls == 1
    assert store.generated_uploads == [b"fresh-image"]
    assert len(store.copied) == 1
    assert store.copied[0][0].startswith("images/cache/")
    assert store.copied[0][1] == "gen/practice/vis-cache-stale.png"


@pytest.mark.asyncio
async def test_execute_visual_cache_miss_uploads_generation_and_cache_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-cache-miss",
        visual=VisualPlanItem(
            id="vis-cache-miss",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            return SimpleNamespace(bytes=b"image", format="png", mime_type="image/png")

    class StubStore:
        def __init__(self) -> None:
            self.generated_uploads: list[bytes] = []
            self.cache_uploads: list[tuple[str, bytes, str]] = []

        async def image_exists(self, *, key: str) -> bool:
            assert key.startswith("images/cache/")
            return False

        async def copy_image(self, *_args, **_kwargs):
            raise AssertionError("cache miss should not copy")

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.generated_uploads.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

        async def store_image_key(self, *, key: str, image_bytes: bytes, content_type: str):
            self.cache_uploads.append((key, image_bytes, content_type))
            return f"https://cdn.example/{key}"

    store = StubStore()

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert store.generated_uploads == [b"image"]
    assert len(store.cache_uploads) == 1
    cache_key, cache_bytes, content_type = store.cache_uploads[0]
    assert cache_key.startswith("images/cache/")
    assert cache_bytes == b"image"
    assert content_type == "image/png"


@pytest.mark.asyncio
async def test_execute_visual_qc_flag_uploads_original_with_metadata_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-qc-flag",
        visual=VisualPlanItem(
            id="vis-qc-flag",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    class StubClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate_image(self, *, prompt: str):
            self.prompts.append(prompt)
            return SimpleNamespace(
                bytes=f"image-{len(self.prompts)}".encode(),
                format="png",
                mime_type="image/png",
            )

    class StubStore:
        async def store_image(self, image_bytes, *_args, **kwargs):
            return f"https://cdn.example/{image_bytes.decode()}-{kwargs['filename']}"

    client = StubClient()
    qc_calls = 0

    async def flag_qc(**_kwargs):
        nonlocal qc_calls
        qc_calls += 1
        return VisualQCVerdict(
            verdict="flag",
            reasons=["label garbled"],
            correction_hint="make label legible",
        )

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", flag_qc)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "flagged_quality"
    assert "image-1" in (blocks[0].image_url or "")
    assert blocks[0].qc_reasons == ["label garbled"]
    assert blocks[0].qc_correction_hint == "make label legible"
    assert len(client.prompts) == 1
    assert qc_calls == 1


@pytest.mark.asyncio
async def test_execute_visual_qc_reject_omits_without_retry_or_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-qc-omit",
        visual=VisualPlanItem(
            id="vis-qc-omit",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            return SimpleNamespace(bytes=b"bad-image", format="png", mime_type="image/png")

    class StubStore:
        async def store_image(self, *_args, **_kwargs):
            raise AssertionError("quality-omitted images should not upload")

    qc_calls = 0

    async def reject_qc(**_kwargs):
        nonlocal qc_calls
        qc_calls += 1
        return VisualQCVerdict(
            verdict="reject",
            reasons=["unsafe content"],
            correction_hint="remove unsafe content",
        )

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", reject_qc)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "omitted_quality"
    assert blocks[0].image_url is None
    assert blocks[0].error_message == "unsafe content"
    assert qc_calls == 1


@pytest.mark.asyncio
async def test_execute_visual_qc_error_fails_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-qc-error",
        visual=VisualPlanItem(
            id="vis-qc-error",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            return SimpleNamespace(bytes=b"image", format="png", mime_type="image/png")

    class StubStore:
        async def store_image(self, image_bytes, *_args, **kwargs):
            _ = image_bytes
            return f"https://cdn.example/{kwargs['filename']}"

    async def qc_error(**_kwargs):
        raise RuntimeError("qc unavailable")

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", qc_error)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("v3_execution.executors.visual_executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "ready"
    assert blocks[0].image_url == "https://cdn.example/vis-qc-error.png"


@pytest.mark.asyncio
async def test_diagram_precision_composes_before_qc_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-compose",
        visual=VisualPlanItem(
            id="vis-compose",
            attaches_to="practice",
            mode="diagram",
            visual_style="diagram_precision",
            labels_required=[" Evaporation ", "Condensation"],
            purpose="show the cycle",
        ),
    )

    base = _png_bytes()
    captured: dict[str, bytes] = {}

    class Client:
        async def generate_image(self, *, prompt: str):
            assert "NO visible text" in prompt
            return SimpleNamespace(bytes=base, format="png", mime_type="image/png")

    class Store:
        def __init__(self) -> None:
            self.generated: list[bytes] = []
            self.cached: list[bytes] = []

        async def image_exists(self, *, key: str) -> bool:
            return False

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.generated.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

        async def store_image_key(self, *, key: str, image_bytes: bytes, content_type: str):
            self.cached.append(image_bytes)

    store = Store()

    async def qc(**kwargs):
        captured["qc"] = kwargs["image_bytes"]
        return VisualQCVerdict(verdict="accept")

    async def one_attempt(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", qc)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert blocks[0].status == "ready"
    assert store.generated[0] == captured["qc"]
    assert store.generated[0] != base
    assert store.cached == [captured["qc"]]


@pytest.mark.asyncio
async def test_diagram_precision_flagged_upload_skips_shared_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-compose-flag",
        visual=VisualPlanItem(
            id="vis-compose-flag",
            attaches_to="practice",
            mode="diagram",
            visual_style="diagram_precision",
            labels_required=["A"],
            purpose="show relation",
        ),
    )
    base = _png_bytes()

    class Store:
        def __init__(self) -> None:
            self.cached = 0
            self.generated: list[bytes] = []

        async def image_exists(self, *, key: str) -> bool:
            return False

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.generated.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

        async def store_image_key(self, **_kwargs):
            self.cached += 1

    store = Store()

    async def qc(**_kwargs):
        return VisualQCVerdict(verdict="flag", reasons=["bad"], correction_hint="fix")

    async def one_attempt(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", qc)
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.get_image_client",
        lambda: SimpleNamespace(generate_image=lambda **_: None),
    )

    class Client:
        async def generate_image(self, *, prompt: str):
            return SimpleNamespace(bytes=base, format="png", mime_type="image/png")

    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")
    assert blocks[0].status == "flagged_quality"
    assert store.generated and store.generated[0] != base
    assert store.cached == 0


@pytest.mark.asyncio
async def test_diagram_precision_qc_exception_fails_closed_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_IMAGE_CACHE_ENABLED", "true")
    order = VisualGeneratorWorkOrder(
        work_order_id="v-compose-qc-error",
        visual=VisualPlanItem(
            id="vis-compose-qc-error",
            attaches_to="practice",
            mode="diagram",
            visual_style="diagram_precision",
            labels_required=["A"],
            purpose="show relation",
        ),
    )
    base = _png_bytes()

    class Client:
        async def generate_image(self, *, prompt: str):
            return SimpleNamespace(bytes=base, format="png", mime_type="image/png")

    class Store:
        def __init__(self) -> None:
            self.generated: list[bytes] = []
            self.cache_writes = 0

        async def image_exists(self, *, key: str) -> bool:
            return False

        async def store_image(self, image_bytes, *_args, **kwargs):
            self.generated.append(image_bytes)
            return f"https://cdn.example/{kwargs['filename']}"

        async def store_image_key(self, **_kwargs):
            self.cache_writes += 1

    store = Store()

    async def qc_error(**_kwargs):
        raise RuntimeError("qc service down")

    async def one_attempt(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr("v3_execution.executors.visual_executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("v3_execution.executors.visual_executor.evaluate_visual_quality", qc_error)
    monkeypatch.setattr("v3_execution.executors.visual_executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("v3_execution.executors.visual_executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")
    assert blocks[0].status == "flagged_quality"
    assert "QC UNAVAILABLE" in (blocks[0].qc_reasons[0] if blocks[0].qc_reasons else "").upper()
    assert store.generated and store.generated[0] != base
    assert store.cache_writes == 0


@pytest.mark.asyncio
async def test_execute_visual_preserves_stage_and_exception_type_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="v-stage-fail",
        visual=VisualPlanItem(
            id="vis-practice-1",
            attaches_to="practice",
            component_id="diagram-block",
            mode="diagram",
            purpose="support question",
        ),
        source_of_truth=[],
    )

    class StubClient:
        async def generate_image(self, *, prompt: str):
            _ = prompt
            raise RuntimeError("provider timeout")

    class StubStore:
        async def store_image(self, *_args, **_kwargs):
            raise AssertionError("store_image should not run when provider fails")

    async def stub_run_with_retries(_label, attempt, max_retries):
        _ = max_retries
        return await attempt(False)

    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.get_image_client",
        lambda: StubClient(),
    )
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )
    monkeypatch.setattr(
        "v3_execution.executors.visual_executor.run_with_retries",
        stub_run_with_retries,
    )

    captured: list[tuple[str, dict]] = []

    async def emit(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    with caplog.at_level(logging.INFO):
        blocks = await execute_visual(
            order,
            emit,
            trace_id="trace",
            generation_id="gen",
        )

    assert len(blocks) == 1
    failed = blocks[0]
    assert failed.status == "failed"
    assert (
        failed.error_message
        == "image_generation_api_call failed (RuntimeError): provider timeout"
    )

    failure_payload = next(payload for event, payload in captured if event == "visual_failed")
    assert (
        failure_payload["error_summary"]
        == "image_generation_api_call failed (RuntimeError): provider timeout"
    )

    failure_log = next(
        record
        for record in caplog.records
        if record.message == "v3 visual failed block error_message set"
    )
    assert failure_log.visual_id == "vis-practice-1"
    assert failure_log.failure_stage == "image_generation_api_call"
    assert failure_log.original_exception_type == "RuntimeError"
    assert "provider timeout" in failure_log.original_exception_message
    assert "RuntimeError: provider timeout" in failure_log.traceback


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
            issues=[],
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
            issues=[issue],
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
            issues=[issue],
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

        async def record_visual_completed(self, **_kwargs):
            self.calls.append("record_visual_completed")

        async def record_visual_failed(self, **_kwargs):
            self.calls.append("record_visual_failed")

        async def record_draft_pack(self, **_kwargs):
            self.calls.append("record_draft_pack")

        async def record_booklet_status(self, **_kwargs):
            self.calls.append("record_booklet_status")

        async def record_review_summary(self, **_kwargs):
            self.calls.append("record_review_summary")

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
    assert "record_visual_completed" in writer.calls
    assert "record_execution_summary" in writer.calls
    assert "record_draft_pack" in writer.calls
    assert "record_booklet_status" in writer.calls
    assert "record_review_summary" in writer.calls
    assert "record_final_pack" in writer.calls
    assert writer.calls[-1] == "record_terminal"


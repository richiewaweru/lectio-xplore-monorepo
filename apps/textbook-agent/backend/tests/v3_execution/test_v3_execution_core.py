from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from contracts.lectio import get_section_field_for_component
from media.qc.visual_qc import VisualQCVerdict
from v3_blueprint.models import ProductionBlueprint
from media.generation.executor import _cache_key_for_visual, execute_visual
from v3_execution.models import (
    ExecutorOutcome,
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    QuestionWriterWorkOrder,
    VisualFrameSpec,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    WriterQuestion,
)
from v3_execution.runtime import validation as v
from v3_review.models import CoherenceReport, ReviewIssue


def _png_bytes(size: tuple[int, int] = (1024, 1024)) -> bytes:
    image = Image.new("RGB", size, "#dbeafe")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture(autouse=True)
def _disable_visual_qc_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "media.generation.executor.visual_qc_enabled",
        lambda: False,
    )


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _load_v3_fixture(filename: str) -> dict:
    raw = Path(__file__).resolve().parents[1] / "fixtures" / filename
    return json.loads(raw.read_text(encoding="utf-8"))






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

    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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

    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", accept_qc)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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

    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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
            return bool(key.startswith("images/cache/"))

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

    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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

    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", flag_qc)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: client)
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "ready_with_quality_warning", blocks[0].error_message
    assert "image-1" in (blocks[0].image_url or "")
    assert blocks[0].qc_reasons == ["label garbled"]
    assert blocks[0].qc_correction_hint == "make label legible"
    assert len(client.prompts) == 1
    assert qc_calls == 1


@pytest.mark.asyncio
async def test_execute_visual_qc_reject_keeps_rendered_asset_with_warning(
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
        async def store_image(self, image_bytes, *_args, **kwargs):
            return f"https://cdn.example/{image_bytes.decode()}-{kwargs['filename']}"

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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", reject_qc)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "ready_with_quality_warning", blocks[0].error_message
    assert blocks[0].image_url is not None
    assert blocks[0].qc_reasons == ["unsafe content"]
    assert blocks[0].qc_correction_hint == "remove unsafe content"
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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", qc_error)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: StubClient())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr("media.generation.executor.load_image_provider_spec", lambda: SimpleNamespace(provider="stub", model_name="stub-model"))
    monkeypatch.setattr("media.generation.executor.run_with_retries", stub_run_with_retries)

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")

    assert len(blocks) == 1
    assert blocks[0].status == "ready_with_quality_warning"
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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", qc)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "media.generation.executor.load_image_provider_spec",
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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", qc)
    monkeypatch.setattr(
        "media.generation.executor.get_image_client",
        lambda: SimpleNamespace(generate_image=lambda **_: None),
    )

    class Client:
        async def generate_image(self, *, prompt: str):
            return SimpleNamespace(bytes=base, format="png", mime_type="image/png")

    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "media.generation.executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")
    assert blocks[0].status == "ready_with_quality_warning"
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

    monkeypatch.setattr("media.generation.executor.visual_qc_enabled", lambda: True)
    monkeypatch.setattr("media.generation.executor.evaluate_visual_quality", qc_error)
    monkeypatch.setattr("media.generation.executor.get_image_client", lambda: Client())
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    monkeypatch.setattr("media.generation.executor.run_with_retries", one_attempt)
    monkeypatch.setattr(
        "media.generation.executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )

    async def emit(_event_type: str, _payload: dict) -> None:
        return None

    blocks = await execute_visual(order, emit, trace_id="trace", generation_id="gen")
    assert blocks[0].status == "ready_with_quality_warning"
    assert "QC UNAVAILABLE" in (blocks[0].qc_reasons[0] if blocks[0].qc_reasons else "").upper()
    assert store.generated and store.generated[0] != base
    assert store.cache_writes == 0


@pytest.mark.asyncio
async def test_execute_visual_preserves_stage_and_exception_type_on_failure(
    monkeypatch: pytest.MonkeyPatch,
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
        "media.generation.executor.get_image_client",
        lambda: StubClient(),
    )
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: StubStore())
    monkeypatch.setattr(
        "media.generation.executor.load_image_provider_spec",
        lambda: SimpleNamespace(provider="stub", model_name="stub-model"),
    )
    monkeypatch.setattr(
        "media.generation.executor.run_with_retries",
        stub_run_with_retries,
    )

    captured: list[tuple[str, dict]] = []
    log_records: list[SimpleNamespace] = []

    async def emit(event_type: str, payload: dict) -> None:
        captured.append((event_type, payload))

    def _capture_error(msg: object, *args: object, **kwargs: object) -> None:
        message = str(msg)
        if args:
            message = message % args
        extra = kwargs.get("extra") if isinstance(kwargs.get("extra"), dict) else {}
        entry = SimpleNamespace(message=message)
        for key, value in extra.items():
            setattr(entry, key, value)
        log_records.append(entry)

    monkeypatch.setattr(
        "media.generation.executor.logger.error",
        _capture_error,
    )

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
        for record in log_records
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








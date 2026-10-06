from __future__ import annotations


from document.shared_lesson.figure_executor_adapter import (
    RoutingFigureExecutor,
    SharedFigureExecutorAdapter,
    render_figures_mode,
)
from media.generation.contracts import (
    GeneratedVisualBlock,
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    validate_visual_block,
)
from media.render.contracts import PolygonAreaSpec, RenderSpecResult
from media.render.gallery import GALLERY
from media.storage.image_store import LocalImageStore

RUN_ID = "ec975a04-7adc-42b4-959b-79068ece697d"
FULL_TEXT = "The room is 9 m by 7 m with a 3 m by 2 m notch; sides 5 m and 6 m."


def make_order(text: str = FULL_TEXT, mode: str = "diagram") -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-1",
        visual=VisualPlanItem(
            id="v1",
            attaches_to="s1",
            mode=mode,
            purpose="Show the L-shaped room",
            must_show=["every side length"],
        ),
        source_of_truth=[SourceOfTruthEntry(key="caption", text=text)],
    )


def l_room() -> RenderSpecResult:
    spec = PolygonAreaSpec.model_validate(GALLERY["polygon_l_room"])
    return RenderSpecResult(family="polygon_area", spec=spec)


def bad_room() -> RenderSpecResult:
    data = dict(GALLERY["polygon_l_room"])
    data["edge_labels"] = [{"edge": 99}]
    return RenderSpecResult(family="polygon_area", spec=PolygonAreaSpec.model_validate(data))


class FakeBuilder:
    def __init__(self, built: RenderSpecResult) -> None:
        self.built = built
        self.build_calls = 0

    async def build(self, order):
        self.build_calls += 1
        return self.built

    async def repair(self, order, previous, errors):
        return self.built


def _make(monkeypatch, tmp_path, builder, mode="auto"):
    monkeypatch.setenv("LECTIO_RENDER_FIGURES", mode)
    store = LocalImageStore(tmp_path, "https://img.example.test")
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    delegate = SharedFigureExecutorAdapter(run_id=RUN_ID)
    delegated: list[VisualGeneratorWorkOrder] = []

    async def fake_execute(order):
        delegated.append(order)
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                mode=order.visual.mode,
                image_url="https://cdn.example.test/x.png",
                source_work_order_id=order.work_order_id,
            )
        ]

    object.__setattr__(delegate, "execute_figure", fake_execute)
    executor = RoutingFigureExecutor(delegate, builder_factory=lambda _t, _g: builder)
    return executor, delegated


def test_mode_parsing(monkeypatch):
    monkeypatch.delenv("LECTIO_RENDER_FIGURES", raising=False)
    assert render_figures_mode() == "off"
    monkeypatch.setenv("LECTIO_RENDER_FIGURES", "AUTO")
    assert render_figures_mode() == "auto"
    monkeypatch.setenv("LECTIO_RENDER_FIGURES", "bogus")
    assert render_figures_mode() == "off"


async def test_flag_off_delegates(monkeypatch, tmp_path):
    builder = FakeBuilder(l_room())
    executor, delegated = _make(monkeypatch, tmp_path, builder, mode="off")
    blocks = await executor.execute_figure(make_order())
    assert len(delegated) == 1 and builder.build_calls == 0
    assert blocks[0].image_url.endswith("x.png")


async def test_image_mode_delegates(monkeypatch, tmp_path):
    builder = FakeBuilder(l_room())
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    await executor.execute_figure(make_order(mode="image"))
    assert len(delegated) == 1 and builder.build_calls == 0


async def test_rendered_stores_svg_and_png(monkeypatch, tmp_path):
    builder = FakeBuilder(l_room())
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    order = make_order()
    blocks = await executor.execute_figure(order)
    assert not delegated and len(blocks) == 1
    block = blocks[0]
    stem = f"shared-document-{RUN_ID}/s1/v1"
    assert block.image_url == f"https://img.example.test/{stem}.svg"
    assert block.fallback_image_url == f"https://img.example.test/{stem}.png"
    assert (tmp_path / f"{stem}.svg").read_bytes().lstrip().startswith((b"<?xml", b"<svg"))
    assert (tmp_path / f"{stem}.png").read_bytes().startswith(b"\x89PNG")
    assert block.status == "ready" and block.qc_reasons == []
    assert block.mode == "diagram"
    assert block.provider_text == f"ALT: {block.alt_text}"
    assert validate_visual_block(block, order) == []


async def test_missing_number_warns(monkeypatch, tmp_path):
    builder = FakeBuilder(l_room())
    executor, _ = _make(monkeypatch, tmp_path, builder)
    blocks = await executor.execute_figure(make_order(text="An L-shaped room."))
    assert blocks[0].status == "ready_with_quality_warning"
    assert blocks[0].qc_reasons


async def test_fallback_delegates(monkeypatch, tmp_path):
    builder = FakeBuilder(RenderSpecResult(family="none", reason="no fit"))
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    await executor.execute_figure(make_order())
    assert len(delegated) == 1


async def test_unavailable_fails_block(monkeypatch, tmp_path):
    builder = FakeBuilder(bad_room())
    executor, delegated = _make(monkeypatch, tmp_path, builder)
    blocks = await executor.execute_figure(make_order())
    assert not delegated
    assert blocks[0].status == "failed"
    assert blocks[0].error_code == "render_spec_invalid"
    assert blocks[0].error_message
    assert blocks[0].image_url is None

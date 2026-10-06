from __future__ import annotations

import io

from PIL import Image

from media.diagram_compositor import (
    COMPOSITOR_VERSION,
    NUMBERED_COMPOSITOR_VERSION,
    NUMBERED_LAYOUT_VERSION,
    compose_diagram_numbered,
    compose_diagram_precision,
)
from media.generation.prompt import build_visual_prompt
from media.qc.visual_qc import _criteria_prompt
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem

LABELS = ["Petal", "Stamen", "Sepal", "Stem"]


def _order(labels: list[str] | None = None) -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="vis-n",
        visual=VisualPlanItem(
            id="vis-n",
            attaches_to="s",
            mode="diagram",
            visual_style="diagram_numbered",
            purpose="show parts of a flower",
            must_show=["a flower"],
            labels_required=LABELS if labels is None else labels,
        ),
    )


def _png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (640, 480), (250, 250, 240)).save(stream, format="PNG")
    return stream.getvalue()


def test_numbered_prompt_is_digits_only_for_every_provider() -> None:
    for gemini in (False, True):
        prompt = build_visual_prompt(_order(), provider_renders_labels=gemini)
        assert "digits 1..4" in prompt
        assert "1 = Petal" in prompt and "4 = Stem" in prompt
        assert "never write the words" in prompt
        assert "draw each label exactly as written" not in prompt
        assert ("ALT: " in prompt) is gemini
        assert "Write each label exactly once" not in prompt


def test_numbered_prompt_without_labels_forbids_all_text() -> None:
    prompt = build_visual_prompt(_order([]))
    assert "Render no words, letters, digits" in prompt
    assert "1 = " not in prompt


def test_numbered_band_grows_png_and_records_variant_metadata() -> None:
    composed = compose_diagram_numbered(_png(), LABELS)
    image = Image.open(io.BytesIO(composed.png_bytes))
    assert image.width == 640 and image.height == 480 + composed.metadata.band_height
    assert composed.metadata.labels == tuple(LABELS)
    assert composed.metadata.compositor_version == NUMBERED_COMPOSITOR_VERSION
    assert composed.metadata.layout_version == NUMBERED_LAYOUT_VERSION
    assert NUMBERED_COMPOSITOR_VERSION != COMPOSITOR_VERSION


def test_numbered_band_is_deterministic_and_differs_from_precision() -> None:
    a = compose_diagram_numbered(_png(), LABELS)
    b = compose_diagram_numbered(_png(), LABELS)
    assert a.png_bytes == b.png_bytes
    assert a.png_bytes != compose_diagram_precision(_png(), LABELS).png_bytes


def test_numbered_qc_prompt_expects_exactly_digits_and_excludes_key_band() -> None:
    prompt = _criteria_prompt(_order())
    assert "exactly the digits 1 to 4" in prompt
    assert "EXCLUDE it from the text check" in prompt
    assert "ANY words, letters" in prompt
    assert "Topology raster criteria" not in prompt


def test_numbered_qc_prompt_without_labels_expects_no_text() -> None:
    assert "no visible text at all" in _criteria_prompt(_order([]))

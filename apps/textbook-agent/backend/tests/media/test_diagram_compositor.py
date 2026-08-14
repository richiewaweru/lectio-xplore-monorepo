from __future__ import annotations

import hashlib
import io
import inspect

import pytest
from PIL import Image

from media.diagram_compositor import (
    COMPOSITOR_VERSION,
    FONT_VERSION,
    LAYOUT_VERSION,
    DiagramCompositionPreflightError,
    FONT_SHA256,
    compose_diagram_precision,
    normalize_labels,
    preflight_diagram_labels,
)


def _png(*, mode: str = "RGB", size: tuple[int, int] = (320, 100)) -> bytes:
    image = Image.new(mode, size, (20, 40, 60, 120) if mode == "RGBA" else (20, 40, 60))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_labels_trim_and_casefold_dedupe_preserves_first_spelling() -> None:
    assert normalize_labels([" Evaporation ", "evaporation", "", "  ", "Condensation", "CONDENSATION"]) == (
        "Evaporation",
        "Condensation",
    )


def test_composition_is_repeatable_and_exposes_hash_metadata() -> None:
    source = _png()
    first = compose_diagram_precision(source, [" Evaporation ", "CONDENSATION", "condensation"])
    second = compose_diagram_precision(source, [" Evaporation ", "CONDENSATION", "condensation"])
    assert first.png_bytes == second.png_bytes
    assert first.metadata == second.metadata
    assert first.metadata.base_sha256 == hashlib.sha256(source).hexdigest()
    assert first.metadata.composed_sha256 == hashlib.sha256(first.png_bytes).hexdigest()
    assert first.metadata.compositor_version == COMPOSITOR_VERSION
    assert first.metadata.font_version == FONT_VERSION
    assert first.metadata.layout_version == LAYOUT_VERSION
    assert first.metadata.labels == ("Evaporation", "CONDENSATION")
    assert first.metadata.band_height > 0
    assert first.metadata.selected_font_size >= 24


def test_bundled_font_is_versioned_licensed_and_hashed() -> None:
    from media import diagram_compositor

    font_path = diagram_compositor._FONT_PATH
    license_path = font_path.with_suffix(".LICENSE.txt")
    assert font_path.exists()
    assert license_path.exists()
    assert hashlib.sha256(font_path.read_bytes()).hexdigest() == FONT_SHA256


def test_m7_water_cycle_labels_keep_readable_font_and_fit() -> None:
    labels = ["evaporation", "condensation", "precipitation", "collection", "water cycle", "water vapor"]
    result = compose_diagram_precision(_png(size=(1024, 1024)), labels)
    assert result.metadata.selected_font_size >= 28
    image = Image.open(io.BytesIO(result.png_bytes))
    assert image.height == 1024 + result.metadata.band_height


def test_label_key_uses_neutral_spacing_without_directional_connectors() -> None:
    from media import diagram_compositor

    source = inspect.getsource(diagram_compositor)
    assert "_ARROW" not in source
    assert "polygon(" not in source
    result = compose_diagram_precision(_png(size=(320, 100)), ["first", "second"])
    assert result.metadata.labels == ("first", "second")


def test_rgb_and_rgba_inputs_receive_opaque_band_without_clipping() -> None:
    for mode in ("RGB", "RGBA"):
        result = compose_diagram_precision(_png(mode=mode, size=(180, 80)), ["A", "B", "C", "D"])
        image = Image.open(io.BytesIO(result.png_bytes))
        assert image.size[0] == 180
        assert image.size[1] > 80
        assert image.mode in {"RGB", "RGBA"}
        pixel = image.convert("RGBA").getpixel((0, image.height - 1))
        assert pixel == (255, 255, 255, 255)


def test_empty_labels_still_adds_reserved_opaque_band() -> None:
    result = compose_diagram_precision(_png(), [])
    image = Image.open(io.BytesIO(result.png_bytes)).convert("RGBA")
    assert result.metadata.labels == ()
    assert image.height > 100
    assert image.getpixel((0, image.height - 1)) == (255, 255, 255, 255)


def test_preflight_has_typed_failure_for_label_too_long_at_minimum_font() -> None:
    with pytest.raises(DiagramCompositionPreflightError) as exc_info:
        preflight_diagram_labels((80, 80), ["This label cannot fit at print size"])
    assert exc_info.value.code == "diagram_composition_preflight_failed"
    assert exc_info.value.image_width == 80
    assert "minimum print font" in str(exc_info.value)


def test_preflight_rejects_excessive_label_count_before_provider() -> None:
    labels = [f"Label {index}" for index in range(100)]
    with pytest.raises(DiagramCompositionPreflightError, match="capacity"):
        preflight_diagram_labels((320, 80), labels)

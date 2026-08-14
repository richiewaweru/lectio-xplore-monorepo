from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from media.storage.image_store import LocalImageStore
from media.topology_renderer import (
    TopologyAssetError,
    TopologyValidationError,
    render_topology,
    render_topology_from_store,
    transform_background,
)


def _source() -> bytes:
    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    # Dense, oversized pseudo-text and high-frequency marks simulate a provider
    # image containing garbled labels. The transform must destroy this content.
    for y in range(0, 600, 13):
        draw.text((4, y), "GARBLED_PROVIDER_TEXT_0123456789_" * 8, fill=(3, 8, 12))
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()


def _topology() -> dict:
    return {
        "layout": "cycle",
        "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}, {"id": "e2", "source": "n2", "target": "n3"}, {"id": "e3", "source": "n3", "target": "n1"}],
        "labels": [{"id": "l1", "text_key": "a", "target": "n1"}, {"id": "l2", "text_key": "b", "target": "n2"}, {"id": "l3", "text_key": "c", "target": "n3"}],
    }


def test_background_transform_is_irreversible_and_bounded() -> None:
    source = _source()
    background_bytes, background = transform_background(source, size=(1200, 800))
    assert background.size == (1200, 800)
    assert background_bytes
    # Heavy white blending bounds contrast; dense source glyphs cannot survive.
    extrema = background.getextrema()
    assert all((high - low) < 100 for low, high in extrema)
    assert background_bytes != source


def test_renderer_is_deterministic_and_owns_labels_geometry() -> None:
    source = _source()
    labels = {"a": "Evaporation", "b": "Condensation", "c": "Collection"}
    first = render_topology(_topology(), source, labels)
    second = render_topology(_topology(), source, labels)
    assert first.png_bytes == second.png_bytes
    assert first.metadata.final_sha256 == second.metadata.final_sha256
    assert first.metadata.source_sha256 != first.metadata.final_sha256
    assert first.metadata.renderer_version.startswith("topology-renderer/")
    assert first.metadata.labels == tuple(labels.values())


def test_renderer_rejects_unknown_labels_and_invalid_layout() -> None:
    with pytest.raises(TopologyValidationError):
        render_topology({**_topology(), "layout": "water-cycle"}, _source(), {"a": "A", "b": "B", "c": "C"})
    with pytest.raises(TopologyValidationError):
        render_topology(_topology(), _source(), {"a": "A", "b": "B"})


@pytest.mark.asyncio
async def test_store_renderer_reads_internal_key_only(tmp_path) -> None:
    store = LocalImageStore(tmp_path, "http://test.invalid/images")
    await store.store_image_key(key="generation/source.png", image_bytes=_source())
    result = await render_topology_from_store(_topology(), "generation/source.png", {"a": "A", "b": "B", "c": "C"}, store)
    assert result.png_bytes
    with pytest.raises(TopologyAssetError):
        await render_topology_from_store(_topology(), "https://provider.invalid/source.png", {}, store)
    with pytest.raises(TopologyAssetError):
        await render_topology_from_store(_topology(), "generation/missing.png", {}, store)


@pytest.mark.asyncio
async def test_local_image_store_rejects_path_escape_and_url(tmp_path) -> None:
    store = LocalImageStore(tmp_path, "http://test.invalid/images")
    with pytest.raises(ValueError):
        await store.read_image_key(key="../secret.png")
    with pytest.raises(ValueError):
        await store.read_image_key(key="https://example.test/a.png")

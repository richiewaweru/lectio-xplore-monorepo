"""Deterministic, provider-free topology visual renderer.

The renderer accepts only validated topology identifiers and a caller-owned
authoritative label map.  A source asset is an internal image-store key (or
already-read bytes); URLs and source prose are intentionally not accepted.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from media.storage.image_store import ImageStore


RENDERER_VERSION = "topology-renderer/1"
BACKGROUND_VERSION = "low-frequency-background/1"
FONT_VERSION = "dejavu-sans/2.37-1"
_FONT_PATH = __import__("pathlib").Path(__file__).with_name("assets") / "DejaVuSans.ttf"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")
_LAYOUTS = {"cycle", "flow", "comparison", "parts"}


class TopologyRenderError(ValueError):
    """Base typed failure for invalid topology or unavailable source assets."""


class TopologyAssetError(TopologyRenderError):
    code = "topology_asset_unavailable"


class TopologyValidationError(TopologyRenderError):
    code = "topology_validation_failed"


@dataclass(frozen=True)
class TopologyRenderMetadata:
    source_sha256: str
    background_sha256: str
    topology_sha256: str
    final_sha256: str
    renderer_version: str
    background_version: str
    font_version: str
    layout: str
    width: int
    height: int
    labels: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "background_sha256": self.background_sha256,
            "topology_sha256": self.topology_sha256,
            "final_sha256": self.final_sha256,
            "renderer_version": self.renderer_version,
            "background_version": self.background_version,
            "font_version": self.font_version,
            "layout": self.layout,
            "width": self.width,
            "height": self.height,
            "labels": list(self.labels),
        }

    to_dict = as_dict


@dataclass(frozen=True)
class TopologyRaster:
    png_bytes: bytes
    metadata: TopologyRenderMetadata

    @property
    def bytes(self) -> bytes:
        return self.png_bytes


class _Store(Protocol):
    async def read_image_key(self, *, key: str) -> bytes: ...


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    raise TopologyValidationError("topology must be a mapping or pydantic model")


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise TopologyValidationError(f"{field} must be a bounded topology identifier")
    return value


def _open_source(source: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(source, Image.Image):
        image = source.copy()
    else:
        try:
            image = Image.open(io.BytesIO(bytes(source)))
            image.load()
        except Exception as exc:  # noqa: BLE001
            raise TopologyAssetError("source asset is not a readable raster") from exc
    if image.width < 1 or image.height < 1:
        raise TopologyAssetError("source asset has no pixels")
    return image.convert("RGB")


def _canonical_png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.convert("RGBA").save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()


def transform_background(source: bytes | bytearray | Image.Image, *, size: tuple[int, int]) -> tuple[bytes, Image.Image]:
    """Destroy high-frequency source detail before using it as a backdrop.

    The source is reduced to at most 16x16 pixels, strongly blurred, enlarged,
    quantized to a restrained palette, and blended heavily with white.  Text or
    glyphs therefore cannot survive as legible content.
    """
    image = _open_source(source)
    thumbnail = image.copy()
    thumbnail.thumbnail((16, 16), Image.Resampling.BILINEAR)
    thumbnail = thumbnail.filter(ImageFilter.GaussianBlur(radius=3.5))
    # A tiny palette makes the operation irreversible and deterministic.
    thumbnail = thumbnail.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    background = thumbnail.resize(size, Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(radius=12))
    background = Image.blend(background, Image.new("RGB", size, "white"), 0.86)
    encoded = _canonical_png(background)
    return encoded, background


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(_FONT_PATH), size=size)
    except OSError as exc:  # pragma: no cover
        raise RuntimeError(f"bundled diagram font missing: {_FONT_PATH}") from exc


def _text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, font: ImageFont.FreeTypeFont) -> None:
    box = draw.textbbox((0, 0), value, font=font)
    draw.rounded_rectangle((xy[0] - 10, xy[1] - 6, xy[0] + box[2] - box[0] + 10, xy[1] + box[3] - box[1] + 6), radius=7, fill=(255, 255, 255, 238), outline=(82, 97, 115, 255), width=2)
    draw.text(xy, value, font=font, fill=(23, 36, 52, 255))


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float]) -> None:
    draw.line((*start, *end), fill=(54, 81, 111, 255), width=5)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    wing = 15
    points = [end, (end[0] - wing * math.cos(angle - 0.48), end[1] - wing * math.sin(angle - 0.48)), (end[0] - wing * math.cos(angle + 0.48), end[1] - wing * math.sin(angle + 0.48))]
    draw.polygon(points, fill=(54, 81, 111, 255))


def _layout_positions(layout: str, nodes: Sequence[Mapping[str, Any]], width: int, height: int) -> dict[str, tuple[float, float]]:
    import math

    ids = [_id(node.get("id"), "node.id") for node in nodes]
    n = len(ids)
    if not n:
        raise TopologyValidationError("topology must contain at least one node")
    if layout == "cycle":
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.31
        return {node_id: (cx + radius * math.cos(2 * math.pi * i / n - math.pi / 2), cy + radius * math.sin(2 * math.pi * i / n - math.pi / 2)) for i, node_id in enumerate(ids)}
    if layout == "comparison":
        left = width * 0.30
        right = width * 0.70
        return {node_id: (left if i % 2 == 0 else right, height * (0.30 + (i // 2) * 0.25)) for i, node_id in enumerate(ids)}
    if layout == "parts":
        center = ids[0]
        out = {center: (width / 2, height * 0.25)}
        for i, node_id in enumerate(ids[1:]):
            x = width * (0.18 + 0.64 * (i / max(1, n - 2))) if n > 2 else width * (0.30 + i * 0.40)
            out[node_id] = (x, height * 0.70)
        return out
    return {node_id: (width * (0.15 + 0.70 * i / max(1, n - 1)), height / 2) for i, node_id in enumerate(ids)}


def render_topology(topology: Any, source: bytes | bytearray | Image.Image, label_map: Mapping[str, str], *, width: int = 1200, height: int = 800) -> TopologyRaster:
    data = _mapping(topology)
    layout = data.get("layout", data.get("layout_id"))
    if layout not in _LAYOUTS:
        raise TopologyValidationError(f"layout must be one of {sorted(_LAYOUTS)}")
    if width < 320 or height < 240:
        raise TopologyValidationError("topology raster is too small for print-safe geometry")
    nodes_raw = data.get("nodes", [])
    edges_raw = data.get("edges", [])
    labels_raw = data.get("labels", [])
    if not isinstance(nodes_raw, Sequence) or not isinstance(edges_raw, Sequence) or not isinstance(labels_raw, Sequence):
        raise TopologyValidationError("nodes, edges, and labels must be arrays")
    nodes = [_mapping(node) for node in nodes_raw]
    positions = _layout_positions(layout, nodes, width, height)
    node_ids = set(positions)
    for edge in edges_raw:
        edge_map = _mapping(edge)
        src = _id(edge_map.get("source", edge_map.get("from_ref", edge_map.get("from"))), "edge.source")
        dst = _id(edge_map.get("target", edge_map.get("to_ref", edge_map.get("to"))), "edge.target")
        if src not in node_ids or dst not in node_ids:
            raise TopologyValidationError("edge endpoint is not a declared node")
    labels: list[tuple[str, str, str | None]] = []
    seen_label_ids: set[str] = set()
    for label in labels_raw:
        item = _mapping(label)
        label_id = _id(item.get("id", item.get("label_id")), "label.id")
        if label_id in seen_label_ids:
            raise TopologyValidationError("duplicate label id")
        seen_label_ids.add(label_id)
        key = item.get("text_key", item.get("label_ref", label_id))
        if not isinstance(key, str) or key not in label_map:
            raise TopologyValidationError(f"missing authoritative label for {label_id}")
        value = label_map[key]
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
            raise TopologyValidationError(f"authoritative label {key!r} is invalid")
        target = item.get("target", item.get("ref", item.get("node_id", item.get("edge_id"))))
        if target is not None and not isinstance(target, str):
            raise TopologyValidationError("label target must be an identifier")
        if target is not None and target not in node_ids and not any(_mapping(edge).get("id") == target for edge in edges_raw):
            raise TopologyValidationError("label target is unknown")
        labels.append((label_id, value.strip(), target))

    source_bytes = bytes(source) if not isinstance(source, Image.Image) else _canonical_png(source)
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    background_bytes, background = transform_background(source, size=(width, height))
    canvas = background.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    # Geometry is authored here; source artwork can only influence the faint backdrop.
    for edge in edges_raw:
        edge_map = _mapping(edge)
        src = edge_map.get("source", edge_map.get("from_ref", edge_map.get("from")))
        dst = edge_map.get("target", edge_map.get("to_ref", edge_map.get("to")))
        _arrow(draw, positions[src], positions[dst])
    for node_id, (x, y) in positions.items():
        draw.ellipse((x - 42, y - 42, x + 42, y + 42), fill=(236, 245, 252, 255), outline=(38, 81, 116, 255), width=5)
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(92, 155, 194, 255))
    font = _font(30)
    occupied = set()
    for _label_id, value, target in labels:
        if target in positions:
            x, y = positions[target]
            offset = (48, -18)
        else:
            # Center/edge labels are deterministic and do not duplicate node labels.
            x, y = width * 0.06, height * (0.08 + 0.075 * len(occupied))
            offset = (0, 0)
        while (round(x + offset[0]), round(y + offset[1])) in occupied:
            offset = (offset[0], offset[1] + 42)
        occupied.add((round(x + offset[0]), round(y + offset[1])))
        _text(draw, (x + offset[0], y + offset[1]), value, font)
    final_bytes = _canonical_png(canvas)
    topology_hash = hashlib.sha256(json.dumps(_canonical(data), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    metadata = TopologyRenderMetadata(source_hash, hashlib.sha256(background_bytes).hexdigest(), topology_hash, hashlib.sha256(final_bytes).hexdigest(), RENDERER_VERSION, BACKGROUND_VERSION, FONT_VERSION, layout, width, height, tuple(value for _, value, _ in labels))
    return TopologyRaster(final_bytes, metadata)


async def render_topology_from_store(topology: Any, image_key: str, label_map: Mapping[str, str], image_store: ImageStore | _Store, *, width: int = 1200, height: int = 800) -> TopologyRaster:
    if not isinstance(image_key, str) or not image_key.strip() or "://" in image_key or image_key.strip().startswith(("http:", "https:")):
        raise TopologyAssetError("topology source must be an internal image-store key")
    try:
        source = await image_store.read_image_key(key=image_key)
    except (FileNotFoundError, ValueError, NotImplementedError) as exc:
        raise TopologyAssetError(f"unable to read topology source asset {image_key!r}") from exc
    if not source:
        raise TopologyAssetError(f"topology source asset {image_key!r} is empty")
    return render_topology(topology, source, label_map, width=width, height=height)


deterministic_render = render_topology

__all__ = ["BACKGROUND_VERSION", "RENDERER_VERSION", "TopologyAssetError", "TopologyRaster", "TopologyRenderError", "TopologyRenderMetadata", "TopologyValidationError", "deterministic_render", "render_topology", "render_topology_from_store", "transform_background"]

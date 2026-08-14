"""Deterministic compositor for closed-label ``diagram_precision`` visuals.

The image provider remains responsible for the diagram artwork.  This module adds
the labels in a small, reserved key band after provider execution so that label
rendering is deterministic and never depends on provider text rendering.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


COMPOSITOR_VERSION = "diagram-compositor/4"
FONT_VERSION = "dejavu-sans/2.37-1"
FONT_SHA256 = "7da195a74c55be f988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954".replace(" ", "")
LAYOUT_VERSION = "ordered-key-band/4"
TARGET_FONT_SIZE = 32
MIN_FONT_SIZE = 24
_FONT_PATH = Path(__file__).with_name("assets") / "DejaVuSans.ttf"
_BAND_BACKGROUND = (255, 255, 255, 255)
_PILL_FILL = (240, 244, 248, 255)
_PILL_OUTLINE = (74, 85, 104, 255)
_TEXT_FILL = (20, 28, 38, 255)
_HORIZONTAL_PADDING = 24
_VERTICAL_PADDING = 16
_PILL_PADDING_X = 14
_PILL_PADDING_Y = 7
_PILL_GAP = 10
_ROW_GAP = 10
MAX_BAND_HEIGHT_RATIO = 3.0
MAX_BAND_HEIGHT_PX = 2048


class DiagramCompositionPreflightError(ValueError):
    """A typed, deterministic failure before an image provider is called."""

    code = "diagram_composition_preflight_failed"

    def __init__(
        self,
        message: str,
        *,
        labels: tuple[str, ...] = (),
        image_width: int | None = None,
        min_font_size: int = MIN_FONT_SIZE,
    ) -> None:
        self.labels = labels
        self.image_width = image_width
        self.min_font_size = min_font_size
        super().__init__(message)


@dataclass(frozen=True)
class CompositionMetadata:
    base_sha256: str
    composed_sha256: str
    compositor_version: str
    font_version: str
    layout_version: str
    labels_digest: str
    labels: tuple[str, ...]
    band_height: int
    width: int
    height: int
    selected_font_size: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_sha256": self.base_sha256,
            "composed_sha256": self.composed_sha256,
            "compositor_version": self.compositor_version,
            "font_version": self.font_version,
            "layout_version": self.layout_version,
            "labels_digest": self.labels_digest,
            "labels": list(self.labels),
            "band_height": self.band_height,
            "width": self.width,
            "height": self.height,
            "selected_font_size": self.selected_font_size,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.as_dict()


@dataclass(frozen=True)
class ComposedRaster:
    png_bytes: bytes
    metadata: CompositionMetadata

    @property
    def bytes(self) -> bytes:
        return self.png_bytes

    @property
    def image_bytes(self) -> bytes:
        return self.png_bytes


def normalize_labels(labels: Iterable[str] | None) -> tuple[str, ...]:
    """Trim labels and case-insensitively deduplicate, preserving first spelling."""

    result: list[str] = []
    seen: set[str] = set()
    for raw in labels or ():
        if not isinstance(raw, str):
            continue
        label = raw.strip()
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return tuple(result)


def labels_digest(labels: Iterable[str] | None) -> str:
    canonical = normalize_labels(labels)
    payload = "\x1f".join(canonical).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _open_image(image_bytes: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(image_bytes, Image.Image):
        image = image_bytes.copy()
    else:
        try:
            image = Image.open(io.BytesIO(bytes(image_bytes)))
            image.load()
        except Exception as exc:  # noqa: BLE001
            raise DiagramCompositionPreflightError(
                "diagram image bytes are not a readable raster"
            ) from exc
    if image.width <= 0 or image.height <= 0:
        raise DiagramCompositionPreflightError("diagram raster has no pixels")
    # Keep alpha when present; all other modes are converted to RGB before the
    # opaque band is appended.  Palette/transparency metadata must not leak into
    # the canonical PNG output.
    if image.mode == "RGBA":
        return image
    if image.mode == "LA":
        return image.convert("RGBA")
    return image.convert("RGB")


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size < 1:
        raise DiagramCompositionPreflightError("font size must be positive", min_font_size=size)
    try:
        return ImageFont.truetype(str(_FONT_PATH), size=size)
    except OSError as exc:  # pragma: no cover - packaged asset is tested in CI
        raise RuntimeError(f"bundled diagram font missing: {_FONT_PATH}") from exc


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return max(1, right - left), max(1, bottom - top)


def _layout(
    *,
    width: int,
    base_height: int,
    labels: tuple[str, ...],
    font_size: int,
) -> tuple[list[list[tuple[str, int, int]]], int, ImageFont.FreeTypeFont]:
    """Return wrapped rows and band height; entries are label, pill width, text height."""

    font = _font(font_size)
    probe = Image.new("RGB", (1, 1), "white")
    draw = ImageDraw.Draw(probe)
    entries: list[tuple[str, int, int]] = []
    max_pill_width = width - 2 * _HORIZONTAL_PADDING
    for label in labels:
        text_width, text_height = _text_size(draw, label, font)
        pill_width = text_width + 2 * _PILL_PADDING_X
        if pill_width > max_pill_width:
            raise DiagramCompositionPreflightError(
                f"label {label!r} cannot fit at minimum print font",
                labels=labels,
                image_width=width,
                min_font_size=font_size,
            )
        entries.append((label, pill_width, text_height))

    rows: list[list[tuple[str, int, int]]] = []
    row: list[tuple[str, int, int]] = []
    row_width = 0
    for entry in entries:
        required = entry[1] if not row else _PILL_GAP + entry[1]
        if row and row_width + required > width - 2 * _HORIZONTAL_PADDING:
            rows.append(row)
            row = []
            row_width = 0
            required = entry[1]
        row.append(entry)
        row_width += required
    if row:
        rows.append(row)
    row_height = max((height for row in rows for _, _, height in row), default=font_size)
    band_height = 2 * _VERTICAL_PADDING + len(rows) * (row_height + 2 * _PILL_PADDING_Y) + max(0, len(rows) - 1) * _ROW_GAP
    # Wrapping keeps ordinary label sets readable, while a pathological count
    # cannot silently produce an enormous image or wait for provider execution.
    max_band_height = min(MAX_BAND_HEIGHT_PX, max(128, int(base_height * MAX_BAND_HEIGHT_RATIO)))
    if band_height > max_band_height:
        raise DiagramCompositionPreflightError(
            "diagram labels exceed the reserved key-band capacity at minimum print font",
            labels=labels,
            image_width=width,
            min_font_size=font_size,
        )
    return rows, band_height, font


def _fit_layout(*, width: int, base_height: int, labels: tuple[str, ...], min_size: int = MIN_FONT_SIZE) -> tuple[list[list[tuple[str, int, int]]], int, ImageFont.FreeTypeFont, int]:
    last_error: DiagramCompositionPreflightError | None = None
    for size in range(TARGET_FONT_SIZE, min_size - 1, -1):
        try:
            rows, band_height, font = _layout(width=width, base_height=base_height, labels=labels, font_size=size)
            return rows, band_height, font, size
        except DiagramCompositionPreflightError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def preflight_diagram_labels(
    image_bytes_or_size: bytes | bytearray | Image.Image | tuple[int, int],
    labels: Iterable[str] | None,
    *,
    min_font_size: int = MIN_FONT_SIZE,
) -> tuple[str, ...]:
    """Validate labels can be printed and return their canonical ordered set."""

    if min_font_size < MIN_FONT_SIZE:
        raise DiagramCompositionPreflightError(
            f"minimum print font must be at least {MIN_FONT_SIZE}px",
            min_font_size=min_font_size,
        )
    canonical = normalize_labels(labels)
    if isinstance(image_bytes_or_size, tuple):
        width, height = image_bytes_or_size
        if width <= 0 or height <= 0:
            raise DiagramCompositionPreflightError("diagram raster has no pixels", labels=canonical)
    else:
        image = _open_image(image_bytes_or_size)
        width, height = image.size
    _fit_layout(width=width, base_height=height, labels=canonical, min_size=min_font_size)
    return canonical


def compose_diagram_precision(
    image_bytes: bytes | bytearray | Image.Image,
    labels: Iterable[str] | None,
    *,
    min_font_size: int = MIN_FONT_SIZE,
) -> ComposedRaster:
    """Append an opaque ordered key band and return canonical PNG bytes + metadata."""

    base = _open_image(image_bytes)
    if isinstance(image_bytes, Image.Image):
        base_sha = hashlib.sha256(_canonical_png(base)).hexdigest()
    else:
        base_sha = hashlib.sha256(bytes(image_bytes)).hexdigest()
    canonical = preflight_diagram_labels(base, labels, min_font_size=min_font_size)
    rows, band_height, font, selected_font_size = _fit_layout(width=base.width, base_height=base.height, labels=canonical)
    mode = "RGBA" if base.mode == "RGBA" else "RGB"
    canvas = Image.new(mode, (base.width, base.height + band_height), (255, 255, 255, 255) if mode == "RGBA" else (255, 255, 255))
    canvas.paste(base, (0, 0))
    draw = ImageDraw.Draw(canvas)
    y = base.height + _VERTICAL_PADDING
    for row in rows:
        row_height = max((entry[2] for entry in row), default=min_font_size)
        x = _HORIZONTAL_PADDING
        # Labels are an ordered key, not a topology: neutral pill spacing only.
        for label, pill_width, _text_height in row:
            pill_top = y
            pill_bottom = y + row_height + 2 * _PILL_PADDING_Y
            draw.rounded_rectangle((x, pill_top, x + pill_width, pill_bottom), radius=8, fill=_PILL_FILL, outline=_PILL_OUTLINE, width=1)
            text_width, _ = _text_size(draw, label, font)
            draw.text((x + (pill_width - text_width) // 2, pill_top + _PILL_PADDING_Y), label, font=font, fill=_TEXT_FILL)
            x += pill_width + _PILL_GAP
        y += row_height + 2 * _PILL_PADDING_Y + _ROW_GAP

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=False, compress_level=9)
    png_bytes = output.getvalue()
    metadata = CompositionMetadata(
        base_sha256=base_sha,
        composed_sha256=hashlib.sha256(png_bytes).hexdigest(),
        compositor_version=COMPOSITOR_VERSION,
        font_version=FONT_VERSION,
        layout_version=LAYOUT_VERSION,
        labels_digest=labels_digest(canonical),
        labels=canonical,
        band_height=band_height,
        width=canvas.width,
        height=canvas.height,
        selected_font_size=selected_font_size,
    )
    return ComposedRaster(png_bytes=png_bytes, metadata=metadata)


def _canonical_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


__all__ = [
    "COMPOSITOR_VERSION",
    "FONT_VERSION",
    "FONT_SHA256",
    "LAYOUT_VERSION",
    "MIN_FONT_SIZE",
    "MAX_BAND_HEIGHT_PX",
    "MAX_BAND_HEIGHT_RATIO",
    "CompositionMetadata",
    "ComposedRaster",
    "DiagramCompositionPreflightError",
    "compose_diagram_precision",
    "labels_digest",
    "normalize_labels",
    "preflight_diagram_labels",
]

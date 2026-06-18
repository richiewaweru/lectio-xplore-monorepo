from __future__ import annotations

import io

from PIL import Image


def normalise_image(
    image_bytes: bytes,
    *,
    target_w: int,
    target_h: int,
) -> bytes:
    """
    Normalise a raw image to exact target dimensions.

    Rules:
    - Never crop — all content is preserved
    - Never upscale — images smaller than target are padded, not stretched
    - Always white background — transparent PNGs get white fill
    - Always PNG output — consistent format for GCS regardless of input

    The image is scaled to fit within (target_w, target_h) preserving aspect ratio,
    then centred on a white canvas of exactly (target_w, target_h).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    src_w, src_h = img.size

    scale = min(target_w / src_w, target_h / src_h, 1.0)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)

    if scale < 1.0:
        img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 255))
    offset_x = (target_w - new_w) // 2
    offset_y = (target_h - new_h) // 2
    canvas.paste(img, (offset_x, offset_y))

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def normalise_image_for_frame(
    image_bytes: bytes,
    *,
    target_w: int | None,
    target_h: int | None,
) -> bytes:
    """
    None-safe wrapper around normalise_image.
    Returns bytes unchanged when either dimension is None.
    """
    if target_w is None or target_h is None:
        return image_bytes
    return normalise_image(image_bytes, target_w=target_w, target_h=target_h)

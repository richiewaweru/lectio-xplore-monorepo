"""Figure asset completion that preserves block identity and order."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class VisualCompletionError(ValueError):
    pass


def apply_figure_asset_update(
    document: dict[str, Any],
    *,
    block_id: str,
    asset: dict[str, Any],
) -> dict[str, Any]:
    """Update only the figure asset payload. Preserve id/intent/object/position/alt/caption/order."""
    updated = deepcopy(document)
    found = False
    for section in updated.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("id") != block_id:
                continue
            if block.get("object") != "figure":
                raise VisualCompletionError(f"block {block_id!r} is not a figure")
            content = dict(block.get("content") or {})
            stable_alt = content.get("alt_text")
            stable_caption = content.get("caption")
            content["asset"] = dict(asset)
            if stable_alt is not None:
                content["alt_text"] = stable_alt
            if stable_caption is not None:
                content["caption"] = stable_caption
            block["content"] = content
            found = True
            break
        if found:
            break
    if not found:
        raise VisualCompletionError(f"figure block {block_id!r} not found")
    return updated

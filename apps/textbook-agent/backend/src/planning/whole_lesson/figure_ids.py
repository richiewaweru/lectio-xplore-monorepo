"""Stable figure request identity for native page blocks."""

from __future__ import annotations

import hashlib

FIGURE_PROMPT_VERSION = "figure-brief-writer-v1"


def stable_figure_request_id(
    *,
    generation_id: str,
    block_id: str,
    figure_prompt_version: str = FIGURE_PROMPT_VERSION,
) -> str:
    digest = hashlib.sha256(
        f"{generation_id}:{block_id}:{figure_prompt_version}".encode("utf-8")
    ).hexdigest()
    return f"fig-req-{digest[:24]}"

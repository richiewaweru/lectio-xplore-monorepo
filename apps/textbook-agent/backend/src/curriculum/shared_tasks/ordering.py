"""Deterministic display scrambling for ordering tasks."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence
from typing import Any


def scramble_for_display(task_id: str, items: Sequence[Any], correct_order: Sequence[Any]) -> list[Any]:
    """Return ``items`` reordered so the display never equals ``correct_order``.

    Deterministic per task id (stable hash, not Python's salted ``hash``). The
    item multiset is unchanged. With fewer than two distinct items the input
    order is returned as-is.
    """
    shown = list(items)
    if len(set(map(repr, shown))) < 2:
        return shown
    seed = int.from_bytes(hashlib.sha256(str(task_id).encode("utf-8")).digest()[:8], "big")
    random.Random(seed).shuffle(shown)
    target = list(correct_order)
    for _ in range(len(shown)):
        if shown != target:
            return shown
        shown = shown[1:] + shown[:1]
    return shown

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


def derange_for_display(task_id: str, items: Sequence[Any]) -> list[Any]:
    """Return ``items`` reordered so no element stays at its original index.

    Used for the right-hand column of matching tasks, so no right item sits in
    its own row. Deterministic per task id (same stable hash as
    ``scramble_for_display``), so Learn and Print show the same order. With
    fewer than two items the input is returned as-is. For distinct items the
    result is always a derangement; with duplicate values fixed points are
    minimised on a best-effort basis.
    """
    original = list(items)
    count = len(original)
    if count < 2:
        return original
    seed = int.from_bytes(hashlib.sha256(str(task_id).encode("utf-8")).digest()[:8], "big")
    shown = list(original)
    random.Random(seed).shuffle(shown)

    def fixed_points(candidate: list[Any]) -> int:
        return sum(1 for index in range(count) if candidate[index] == original[index])

    best, best_fixed = shown, fixed_points(shown)
    for _ in range(count):
        if best_fixed == 0:
            return best
        shown = shown[1:] + shown[:1]
        fixed = fixed_points(shown)
        if fixed < best_fixed:
            best, best_fixed = shown, fixed
    if best_fixed == 0:
        return best
    rotated = original[1:] + original[:1]
    return rotated if fixed_points(rotated) <= best_fixed else best

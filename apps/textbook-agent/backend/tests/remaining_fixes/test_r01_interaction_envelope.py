"""R01: closed salvage removed; envelope survival covered by v2 interaction writer tests."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_r01_closed_learn_production_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src

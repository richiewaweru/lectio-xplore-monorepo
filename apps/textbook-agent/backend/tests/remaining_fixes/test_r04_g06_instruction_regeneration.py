"""R04-G06: closed salvage removed; instruction regeneration covered by v2 Builder tests."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_r04_g06_closed_learn_production_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production_async" not in src

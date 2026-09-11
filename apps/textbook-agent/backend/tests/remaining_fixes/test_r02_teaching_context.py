"""R02: closed salvage removed; teaching context wiring lives on v2 production."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_r02_closed_learn_production_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src

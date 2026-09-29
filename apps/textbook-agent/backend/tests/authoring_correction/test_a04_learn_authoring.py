"""A04: Learn authoring - closed salvage removed; v2 production is canonical."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_a04_closed_salvage_and_ordered_assemble_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src
    assert not (Path(native_production.__file__).parent / "ordered_assemble.py").exists()

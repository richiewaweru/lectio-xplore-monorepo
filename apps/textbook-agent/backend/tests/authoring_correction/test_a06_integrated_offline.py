"""A06: integrated offline — closed salvage removed."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_a06_closed_salvage_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src
    assert "assemble_ordered_learn_document" not in src

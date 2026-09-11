"""A00: brief must not be copied as finished content — covered by v2 writer; salvage gone."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_a00_closed_salvage_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src
    assert "assemble_ordered_learn_document" not in src

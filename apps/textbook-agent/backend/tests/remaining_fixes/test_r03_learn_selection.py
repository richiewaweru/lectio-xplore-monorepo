"""R03: closed-path model selection removed with v1 salvage; v2 modes are tested elsewhere."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_r03_closed_learn_production_removed() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production_async" not in src
    assert "assemble_ordered_learn_document" not in src

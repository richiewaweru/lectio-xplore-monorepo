"""R00: closed Learn salvage removed; preparation facts flow through v2 production."""

from __future__ import annotations

from pathlib import Path

from learn.generation import native_production


def test_r00_closed_learn_production_removed_from_source() -> None:
    src = Path(native_production.__file__).read_text(encoding="utf-8")
    assert "build_closed_learn_production" not in src
    assert "allowed_facts=[]" not in src or "produce_learn_document_from_teaching" in src

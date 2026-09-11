"""Phase C: residual v1 Learn salvage must be absent from active source."""

from __future__ import annotations

from pathlib import Path

_BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"
_FORBIDDEN = (
    "build_closed_learn_production",
    "build_closed_learn_production_async",
    "host_interaction_blocks_for_builder",
    "closed_learn_selection",
    "assemble_ordered_learn_document",
)


def test_no_v1_learn_salvage_in_active_source() -> None:
    hits: list[str] = []
    for path in _BACKEND_SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in _FORBIDDEN:
            if needle in text:
                hits.append(f"{path.relative_to(_BACKEND_SRC)}:{needle}")
    assert hits == [], "residual v1 Learn salvage still present:\n" + "\n".join(hits)


def test_ordered_assemble_module_deleted() -> None:
    path = _BACKEND_SRC / "learn" / "generation" / "ordered_assemble.py"
    assert not path.exists()

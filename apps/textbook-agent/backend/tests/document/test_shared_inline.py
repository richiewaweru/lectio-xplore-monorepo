import json
from pathlib import Path

from document.shared_lesson.inline import parse_inline_markup


_VECTORS = Path(__file__).parents[3] / "frontend/src/lib/learn/document/inline-vectors.json"


def test_inline_markup_matches_shared_vectors() -> None:
    vectors = json.loads(_VECTORS.read_text(encoding="utf-8"))
    for vector in vectors:
        assert parse_inline_markup(vector["input"]) == vector["expected"], vector["name"]

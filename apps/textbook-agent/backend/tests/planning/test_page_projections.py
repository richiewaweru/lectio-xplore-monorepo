"""RUN_08 projection/QC tests for v2 documents."""

from __future__ import annotations

import json
from pathlib import Path

from planning.page_projections import (
    qc_committed_document,
    project_blocks_by_intent,
    project_student_blocks,
    project_teacher_blocks,
)

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "lectio-page"
    / "valid-document.json"
)


def test_v2_projections_do_not_read_legacy_component_fields() -> None:
    source = Path(__file__).resolve().parents[2] / "src" / "planning" / "page_projections.py"
    text = source.read_text(encoding="utf-8")
    for forbidden in ("definition_family", "comparison_grid", "worked_examples", "pitfalls"):
        assert forbidden not in text


def test_intent_projection_and_qc() -> None:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    explain = project_blocks_by_intent(doc, {"explain-cause", "compare"})
    assert explain
    assert all(item["intent"] in {"explain-cause", "compare"} for item in explain)
    teacher = project_teacher_blocks(doc)
    student = project_student_blocks(doc)
    assert len(student) == len(teacher)
    assert qc_committed_document(doc) == []

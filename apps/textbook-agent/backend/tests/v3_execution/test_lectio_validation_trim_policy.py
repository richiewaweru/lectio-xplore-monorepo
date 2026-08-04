from __future__ import annotations

from v3_execution.runtime.lectio_validation import validate_section_content
from v3_review.deterministic_checks import check_lectio_schema_validity
from v3_execution.models import DraftPack


def test_trim_allowlist_trims_explanation_emphasis_without_review_issue() -> None:
    bucket = {
        "section_id": "s1",
        "template_id": "guided-concept-path",
        "explanation": {
            "body": "Area can be decomposed.",
            "emphasis": ["a", "b", "c", "d", "e", "f", "g"],
        },
    }

    validated, warnings = validate_section_content(bucket)

    assert validated is not None
    assert validated["explanation"]["emphasis"] == ["a", "b", "c"]
    assert warnings == ["trimmed: explanation.emphasis from 7 items to 3"]

    draft_pack = DraftPack(
        generation_id="g",
        blueprint_id="b",
        template_id="guided-concept-path",
        subject="Math",
        status="draft_ready",
        sections=[{**validated, "_schema_warnings": warnings}],
    )
    assert check_lectio_schema_validity(draft_pack) == []


def test_semantic_arrays_are_not_trimmed_by_default() -> None:
    steps = [
        {"label": str(idx), "content": f"Step {idx}"}
        for idx in range(6)
    ]
    bucket = {
        "section_id": "s1",
        "template_id": "guided-concept-path",
        "worked_example": {
            "title": "Area model",
            "setup": "Find the total area.",
            "steps": steps,
            "conclusion": "Add the parts.",
        },
    }

    validated, warnings = validate_section_content(bucket)

    assert validated is not None
    assert len(validated["worked_example"]["steps"]) == 6
    assert warnings == []

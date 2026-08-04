"""
v3_execution.runtime.lectio_validation

Pydantic-based validation gates for V3 section generation.

Trim policy: Would removing an item change what the content teaches? Yes -> render
as-is. No -> trimming may be allowlisted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from contracts.section_content import SectionContent

TRIM_ALLOWLIST: dict[str, int] = {
    "explanation.emphasis": 3,
    "definition.related_terms": 3,
}

_SECTION_VALIDATION_METADATA_KEYS = frozenset(
    {
        "_component_order",
        "_component_positions",
        "_schema_warnings",
    }
)

_FIELD_MODELS: dict[str, type] = {}


def _apply_trim_allowlist(bucket: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    trimmed = deepcopy(bucket)
    warnings: list[str] = []
    for path, cap in TRIM_ALLOWLIST.items():
        field_name, child_name = path.split(".", 1)
        field_payload = trimmed.get(field_name)
        if not isinstance(field_payload, dict):
            continue
        value = field_payload.get(child_name)
        if isinstance(value, list) and len(value) > cap:
            original_count = len(value)
            field_payload[child_name] = value[:cap]
            warnings.append(
                f"trimmed: {path} from {original_count} items to {cap}"
            )
    return trimmed, warnings


def _try_import_field_models() -> None:
    """
    Populate _FIELD_MODELS from the generated section_content module.
    """
    from contracts import section_content as sc

    field_model_candidates = {
        "header": "SectionHeaderContent",
        "hook": "HookHeroContent",
        "explanation": "ExplanationContent",
        "definition": "DefinitionContent",
        "worked_example": "WorkedExampleContent",
        "practice": "PracticeContent",
        "quiz": "QuizContent",
        "reflection": "ReflectionContent",
        "summary": "SummaryBlockContent",
        "comparison_grid": "ComparisonGridContent",
        "timeline": "TimelineContent",
        "fill_in_blank": "FillInBlankContent",
        "student_textbox": "StudentTextboxContent",
        "short_answer": "ShortAnswerContent",
        "what_next": "WhatNextContent",
        "prerequisites": "PrerequisiteContent",
        "key_fact": "KeyFactContent",
        "insight": "InsightStripContent",
        "pitfall": "PitfallContent",
        "callout": "CalloutBlockContent",
        "diagram": "DiagramContent",
        "diagram_compare": "DiagramCompareContent",
        "diagram_series": "DiagramSeriesContent",
        "simulation": "SimulationContent",
        "interview": "InterviewContent",
    }

    for field_name, class_name in field_model_candidates.items():
        model_cls = getattr(sc, class_name, None)
        if model_cls is not None:
            _FIELD_MODELS[field_name] = model_cls


_try_import_field_models()


def validate_lectio_field_payload(
    field_name: str,
    data: dict,
) -> tuple[dict, list[str]]:
    """
    Validate a single field payload against its generated Pydantic model.
    """
    model_cls = _FIELD_MODELS.get(field_name)
    if model_cls is None:
        return data, []
    data, trim_warnings = _apply_trim_allowlist({field_name: data})
    data = data[field_name]

    try:
        validated = model_cls.model_validate(data)
        return validated.model_dump(exclude_none=True), trim_warnings
    except ValidationError as exc:
        errors = [
            f"{field_name}.{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return data, [*trim_warnings, *errors]


def validate_section_content(bucket: dict) -> tuple[dict | None, list[str]]:
    """
    Validate a fully assembled section bucket against SectionContent.
    """
    trimmed_bucket, trim_warnings = _apply_trim_allowlist(bucket)
    validation_bucket = {
        key: value
        for key, value in trimmed_bucket.items()
        if key not in _SECTION_VALIDATION_METADATA_KEYS
    }
    try:
        validated = SectionContent.model_validate(validation_bucket)
        validated_bucket = validated.model_dump(exclude_none=True)
        for key in _SECTION_VALIDATION_METADATA_KEYS:
            if key in trimmed_bucket:
                validated_bucket[key] = trimmed_bucket[key]
        return validated_bucket, trim_warnings
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, [*trim_warnings, *errors]

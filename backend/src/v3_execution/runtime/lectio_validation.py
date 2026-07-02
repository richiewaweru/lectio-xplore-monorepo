"""
v3_execution.runtime.lectio_validation

Pydantic-based validation gates for V3 section generation.
"""

from __future__ import annotations

from pydantic import ValidationError

from contracts.section_content import SectionContent

_SECTION_VALIDATION_METADATA_KEYS = frozenset(
    {
        "_component_order",
        "_component_positions",
        "_schema_warnings",
    }
)

_FIELD_MODELS: dict[str, type] = {}


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

    try:
        validated = model_cls.model_validate(data)
        return validated.model_dump(exclude_none=True), []
    except ValidationError as exc:
        errors = [
            f"{field_name}.{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return data, errors


def validate_section_content(bucket: dict) -> tuple[dict | None, list[str]]:
    """
    Validate a fully assembled section bucket against SectionContent.
    """
    validation_bucket = {
        key: value
        for key, value in bucket.items()
        if key not in _SECTION_VALIDATION_METADATA_KEYS
    }
    try:
        validated = SectionContent.model_validate(validation_bucket)
        validated_bucket = validated.model_dump(exclude_none=True)
        for key in _SECTION_VALIDATION_METADATA_KEYS:
            if key in bucket:
                validated_bucket[key] = bucket[key]
        return validated_bucket, []
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, errors

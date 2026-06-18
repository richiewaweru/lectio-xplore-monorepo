from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from pipeline.contracts import build_section_generation_manifest, get_section_content_schema
from pipeline.state import PipelineError, TextbookPipelineState


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) > 0
    return True


def _path_from_error(path_parts: list[Any]) -> str:
    if not path_parts:
        return "<root>"
    return ".".join(str(part) for part in path_parts)


def _schema_failures(section_dict: dict, schema: dict) -> list[dict[str, str]]:
    validator = Draft202012Validator(schema)
    failures: list[dict[str, str]] = []
    for error in sorted(validator.iter_errors(section_dict), key=lambda e: list(e.path)):
        failures.append(
            {
                "field": _path_from_error(list(error.absolute_path)),
                "type": error.validator or "schema",
                "message": error.message,
            }
        )
    return failures


def _required_field_failures(section_dict: dict, manifest) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for field in manifest.required_fields:
        if field.external:
            continue
        if _has_content(section_dict.get(field.field_name)):
            continue
        failures.append(
            {
                "field": field.field_name,
                "type": "required_manifest",
                "message": f"Required field '{field.field_name}' is missing or empty.",
            }
        )
    return failures


async def schema_validator(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    _ = model_overrides
    typed = TextbookPipelineState.parse(state)
    section_id = typed.current_section_id
    node_name = "schema_validator"

    section = typed.generated_sections.get(section_id)
    if section is None:
        return {
            "errors": [
                PipelineError(
                    node=node_name,
                    section_id=section_id,
                    message="No generated section found for schema validation.",
                    recoverable=True,
                )
            ],
            "completed_nodes": [node_name],
        }

    schema = get_section_content_schema()
    section_dict = section.model_dump(exclude_none=True)
    manifest = build_section_generation_manifest(
        template_id=typed.contract.id,
        section_plan=typed.current_section_plan,
    )

    failures = [
        *_schema_failures(section_dict, schema),
        *_required_field_failures(section_dict, manifest),
    ]
    if failures:
        encoded = json.dumps(
            {"summary": "schema_validation_failed", "failures": failures},
            sort_keys=True,
        )
        return {
            "errors": [
                PipelineError(
                    node=node_name,
                    section_id=section_id,
                    message=encoded,
                    recoverable=True,
                )
            ],
            "completed_nodes": [node_name],
        }

    return {"completed_nodes": [node_name]}

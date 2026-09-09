from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from infra.authoring.models import AuthoringValidationError


def _path(parent: str, child: str | int) -> str:
    if parent == "":
        return str(child)
    if isinstance(child, int):
        return f"{parent}[{child}]"
    return f"{parent}.{child}"


def _json_type_matches(expected: str, value: Any) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _type_errors(
    schema: Mapping[str, Any],
    value: Any,
    path: str,
) -> list[AuthoringValidationError]:
    expected = schema.get("type")
    if expected is None:
        return []
    if isinstance(expected, str):
        if not _json_type_matches(expected, value):
            return [AuthoringValidationError(path, f"expected {expected}")]
        return []
    if isinstance(expected, list):
        if not any(_json_type_matches(str(item), value) for item in expected):
            return [AuthoringValidationError(path, f"expected one of {expected}")]
    return []


def validate_json_schema(
    schema: Mapping[str, Any],
    payload: Any,
    *,
    path: str = "",
) -> list[AuthoringValidationError]:
    """Small deterministic JSON Schema validator for package payload contracts."""
    if "$ref" in schema and len(schema) == 1:
        return []

    errors = _type_errors(schema, payload, path)
    if errors:
        return errors

    if "enum" in schema and payload not in schema.get("enum", []):
        errors.append(
            AuthoringValidationError(path, f"expected one of {schema.get('enum')}")
        )

    if isinstance(payload, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(payload) < min_length:
            errors.append(AuthoringValidationError(path, f"minLength {min_length}"))

    if isinstance(payload, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(payload) < min_items:
            errors.append(AuthoringValidationError(path, f"minItems {min_items}"))
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(payload) > max_items:
            errors.append(AuthoringValidationError(path, f"maxItems {max_items}"))
        if schema.get("uniqueItems") is True:
            seen: set[str] = set()
            for index, item in enumerate(payload):
                key = repr(item)
                if key in seen:
                    errors.append(AuthoringValidationError(_path(path, index), "duplicate item"))
                seen.add(key)
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(payload):
                errors.extend(
                    validate_json_schema(item_schema, item, path=_path(path, index))
                )

    if isinstance(payload, Mapping):
        required = schema.get("required")
        if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
            for key in required:
                if isinstance(key, str) and key not in payload:
                    errors.append(AuthoringValidationError(_path(path, key), "required"))

        properties = schema.get("properties")
        known = set(properties.keys()) if isinstance(properties, Mapping) else set()
        if schema.get("additionalProperties") is False:
            for key in payload:
                if key not in known:
                    errors.append(
                        AuthoringValidationError(_path(path, str(key)), "unexpected property")
                    )

        if isinstance(properties, Mapping):
            for key, child_schema in properties.items():
                if key in payload and isinstance(child_schema, Mapping):
                    errors.extend(
                        validate_json_schema(
                            child_schema,
                            payload[key],
                            path=_path(path, key),
                        )
                    )

    return errors

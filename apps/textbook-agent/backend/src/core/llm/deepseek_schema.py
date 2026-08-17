from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic_ai.profiles.openai import JsonSchema, OpenAIJsonSchemaTransformer

# Keywords DeepSeek strict mode does not support in provider projection.
_UNSUPPORTED_STRICT_KEYWORDS = frozenset({"minLength", "maxLength", "minItems", "maxItems"})


class DeepSeekStrictSchemaError(ValueError):
    """Raised when a canonical schema cannot be safely projected for DeepSeek strict mode."""


@dataclass(init=False)
class DeepSeekJsonSchemaTransformer(OpenAIJsonSchemaTransformer):
    """OpenAI strict normalization plus DeepSeek-specific keyword stripping."""

    def transform(self, schema: JsonSchema) -> JsonSchema:
        result = super().transform(schema)
        for key in list(result):
            if key in _UNSUPPORTED_STRICT_KEYWORDS:
                result.pop(key, None)
        return result


def to_deepseek_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical JSON Schema for DeepSeek strict tool output."""
    before = deepcopy(schema)
    transformer = DeepSeekJsonSchemaTransformer(schema, strict=True)
    provider_schema = transformer.walk()
    validate_deepseek_projection(provider_schema)
    assert before == schema, "canonical schema must not be mutated"
    return provider_schema


def validate_deepseek_projection(schema: dict[str, Any]) -> None:
    """Fail closed on constructs known to be unsafe for DeepSeek strict mode."""

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                walk(child)
            return
        if not isinstance(node, dict):
            return

        node_type = node.get("type")
        props = node.get("properties")
        if node_type == "object" or isinstance(props, dict):
            props = props or {}
            if node.get("additionalProperties") not in (False, None) and props:
                raise DeepSeekStrictSchemaError(
                    "object node missing additionalProperties=false after projection"
                )
            required = node.get("required")
            if props and (not isinstance(required, list) or set(required) != set(props)):
                raise DeepSeekStrictSchemaError(
                    "object node must require every property for DeepSeek strict mode"
                )

        for key in node:
            if key in _UNSUPPORTED_STRICT_KEYWORDS:
                raise DeepSeekStrictSchemaError(
                    f"unsupported keyword {key!r} survived DeepSeek projection"
                )
        for value in node.values():
            walk(value)

    walk(schema)


__all__ = [
    "DeepSeekJsonSchemaTransformer",
    "DeepSeekStrictSchemaError",
    "to_deepseek_strict_schema",
    "validate_deepseek_projection",
]

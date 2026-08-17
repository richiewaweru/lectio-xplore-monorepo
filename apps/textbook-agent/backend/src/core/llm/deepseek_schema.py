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

    def walk(self) -> JsonSchema:
        result = super().walk()
        _inline_anyof_refs(result, result)
        return result

    def transform(self, schema: JsonSchema) -> JsonSchema:
        result = super().transform(schema)
        for key in list(result):
            if key in _UNSUPPORTED_STRICT_KEYWORDS:
                result.pop(key, None)
        return result


def _resolve_local_ref(ref: str, root: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a local ``$defs`` reference used as an ``anyOf`` branch."""
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        return None
    node: Any = root.get("$defs")
    for part in ref.removeprefix(prefix).split("/"):
        if not isinstance(node, dict):
            return None
        node = node.get(part.replace("~1", "/").replace("~0", "~"))
    return node if isinstance(node, dict) else None


def _inline_anyof_refs(
    node: Any,
    root: dict[str, Any],
    *,
    active_refs: frozenset[str] = frozenset(),
) -> None:
    """Inline local refs directly under ``anyOf`` for DeepSeek strict mode.

    DeepSeek's strict validator accepts ``anyOf`` branches only when each
    branch carries its own schema type. Pydantic emits nullable nested models
    as ``anyOf: [{"$ref": ...}, {"type": "null"}]``; inline that one branch
    while preserving refs elsewhere in the schema.
    """
    if isinstance(node, list):
        for child in node:
            _inline_anyof_refs(child, root, active_refs=active_refs)
        return
    if not isinstance(node, dict):
        return

    branches = node.get("anyOf")
    if isinstance(branches, list):
        projected_branches: list[Any] = []
        for branch in branches:
            if isinstance(branch, dict) and isinstance(branch.get("$ref"), str):
                ref = branch["$ref"]
                target = None if ref in active_refs else _resolve_local_ref(ref, root)
                if target is not None:
                    replacement = deepcopy(target)
                    replacement.update(
                        {key: value for key, value in branch.items() if key != "$ref"}
                    )
                    _inline_anyof_refs(
                        replacement,
                        root,
                        active_refs=active_refs | {ref},
                    )
                    projected_branches.append(replacement)
                    continue
            projected_branches.append(branch)
        node["anyOf"] = projected_branches

    for value in node.values():
        _inline_anyof_refs(value, root, active_refs=active_refs)


def to_deepseek_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Project a canonical JSON Schema for DeepSeek strict tool output."""
    before = deepcopy(schema)
    transformer = DeepSeekJsonSchemaTransformer(schema, strict=True)
    provider_schema = transformer.walk()
    _inline_anyof_refs(provider_schema, provider_schema)
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
        any_of = node.get("anyOf")
        if isinstance(any_of, list):
            for branch in any_of:
                if isinstance(branch, dict) and "type" not in branch:
                    raise DeepSeekStrictSchemaError(
                        "anyOf branch must carry an inline type for DeepSeek strict mode"
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

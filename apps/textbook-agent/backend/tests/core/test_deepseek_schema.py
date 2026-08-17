from __future__ import annotations

from copy import deepcopy
from enum import Enum

import pytest
from pydantic import BaseModel, Field

from core.llm.deepseek_schema import (
    DeepSeekStrictSchemaError,
    to_deepseek_strict_schema,
)
from core.llm.schema import SchemaSource, schema_fingerprint


class Color(str, Enum):
    red = "red"
    blue = "blue"


class NestedModel(BaseModel):
    label: str = Field(min_length=1, max_length=40)


class RepresentativeModel(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    count: int = Field(default=3, ge=1, le=10)
    optional_note: str | None = None
    nested: NestedModel
    tags: list[str] = Field(default_factory=list, min_length=0, max_length=5)
    color: Color


def _object_node(schema: dict, *, path: tuple[str, ...] = ()) -> dict:
    node = schema
    for key in path:
        node = node["properties"][key]
        if node.get("type") == "array":
            node = node["items"]
    return node


def test_a1_basic_object_requires_all_properties() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    projected = to_deepseek_strict_schema(schema)
    root = projected
    assert root["additionalProperties"] is False
    assert set(root["required"]) == set(root["properties"])


def test_a2_nested_objects_are_strict() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    projected = to_deepseek_strict_schema(schema)
    nested = projected["$defs"]["NestedModel"]
    assert nested["additionalProperties"] is False
    assert set(nested["required"]) == set(nested["properties"])


def test_a3_arrays_items_are_transformed() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    projected = to_deepseek_strict_schema(schema)
    tags = projected["properties"]["tags"]
    assert tags["type"] == "array"
    assert "minItems" not in tags
    assert "maxItems" not in tags


def test_a4_enums_and_numeric_bounds_preserved() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    projected = to_deepseek_strict_schema(schema)
    count = projected["properties"]["count"]
    assert count["minimum"] == 1
    assert count["maximum"] == 10
    color = projected["$defs"]["Color"]
    assert color["enum"] == ["red", "blue"]


def test_a5_unsupported_length_keywords_removed() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    before = deepcopy(schema)
    projected = to_deepseek_strict_schema(schema)

    def assert_removed(node: object) -> None:
        if isinstance(node, dict):
            for key in ("minLength", "maxLength", "minItems", "maxItems"):
                assert key not in node
            for value in node.values():
                assert_removed(value)
        elif isinstance(node, list):
            for child in node:
                assert_removed(child)

    assert_removed(projected)
    assert schema == before


def test_a6_pydantic_defaults_and_optionals_post_validate() -> None:
    source = SchemaSource.from_type(RepresentativeModel)
    projected = to_deepseek_strict_schema(source.canonical_schema)

    def assert_no_length_keywords(node: object) -> None:
        if isinstance(node, dict):
            for key in ("minLength", "maxLength", "minItems", "maxItems"):
                assert key not in node
            for value in node.values():
                assert_no_length_keywords(value)
        elif isinstance(node, list):
            for child in node:
                assert_no_length_keywords(child)

    assert_no_length_keywords(projected)
    payload = {
        "title": "ok",
        "count": 3,
        "optional_note": None,
        "nested": {"label": "child"},
        "tags": [],
        "color": "red",
    }
    validated = RepresentativeModel.model_validate(payload)
    assert validated.count == 3


def test_a7_defs_and_refs_projection() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    projected = to_deepseek_strict_schema(schema)
    assert isinstance(projected, dict)
    assert "properties" in projected


def test_a8_immutability() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    before = deepcopy(schema)
    _ = to_deepseek_strict_schema(schema)
    assert schema == before


def test_a9_deterministic_fingerprint() -> None:
    schema = RepresentativeModel.model_json_schema(mode="validation")
    first = schema_fingerprint(schema)
    second = schema_fingerprint(deepcopy(schema))
    assert first == second
    schema["title"] = "changed"
    assert schema_fingerprint(schema) != first


def test_validate_projection_rejects_unsupported_survivors() -> None:
    from core.llm.deepseek_schema import validate_deepseek_projection

    with pytest.raises(DeepSeekStrictSchemaError):
        validate_deepseek_projection(
            {
                "type": "object",
                "properties": {"name": {"type": "string", "minLength": 1}},
                "required": ["name"],
                "additionalProperties": False,
            }
        )

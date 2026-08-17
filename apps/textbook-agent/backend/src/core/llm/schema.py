from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

SchemaSourceKind = Literal["pydantic", "json_schema"]


@dataclass(frozen=True)
class SchemaSource:
    """Canonical structured-output schema metadata."""

    canonical_schema: dict[str, Any]
    output_type: Any | None
    kind: SchemaSourceKind

    @classmethod
    def from_type(cls, output_type: Any) -> SchemaSource:
        if isinstance(output_type, type) and issubclass(output_type, BaseModel):
            schema = output_type.model_json_schema(mode="validation")
        else:
            schema = TypeAdapter(output_type).json_schema(mode="validation")
        return cls(deepcopy(schema), output_type, "pydantic")

    @classmethod
    def from_json_schema(cls, output_schema: dict[str, Any]) -> SchemaSource:
        return cls(deepcopy(output_schema), None, "json_schema")

    @property
    def fingerprint(self) -> str:
        return schema_fingerprint(self.canonical_schema)


def schema_source(
    *,
    output_type: Any | None = None,
    output_schema: dict[str, Any] | None = None,
) -> SchemaSource:
    """Build a canonical schema source from exactly one input."""
    if (output_type is None) == (output_schema is None):
        raise ValueError("provide exactly one of output_type or output_schema")
    if output_schema is not None:
        return SchemaSource.from_json_schema(output_schema)
    return SchemaSource.from_type(output_type)


def schema_fingerprint(schema: dict[str, Any]) -> str:
    payload = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_canonical_output(source: SchemaSource, payload: Any) -> Any:
    """Post-validate provider output against the original canonical contract."""
    if source.output_type is not None:
        if isinstance(source.output_type, type) and issubclass(source.output_type, BaseModel):
            if isinstance(payload, source.output_type):
                return payload
            return source.output_type.model_validate(payload)
        return TypeAdapter(source.output_type).validate_python(payload)
    return payload


__all__ = [
    "SchemaSource",
    "SchemaSourceKind",
    "schema_fingerprint",
    "schema_source",
    "validate_canonical_output",
]

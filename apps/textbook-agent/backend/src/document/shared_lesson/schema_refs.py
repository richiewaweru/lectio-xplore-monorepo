"""JSON-schema helper shared by the composer and writer provider output types."""

from __future__ import annotations

from typing import Any


def inline_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Return ``schema`` with every local ``$ref`` replaced by its definition."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {
                key: walk(value)
                for key, value in node.items()
                if key not in {"$defs", "discriminator"}
            }
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(schema)  # type: ignore[no-any-return]


__all__ = ["inline_json_schema_refs"]

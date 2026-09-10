"""Validation for ordered sequences of ordinary document nodes."""

from __future__ import annotations

from typing import Any, Sequence

from document.models import DOCUMENT_PRIMITIVE_KINDS, DocumentNode, document_node_adapter


class DocumentValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        ValueError.__init__(self, "; ".join(errors))


def validate_document_nodes(nodes: Sequence[Any]) -> list[DocumentNode]:
    """Validate and return an ordered list of document primitives.

    Rejects pagination, interaction scoring, media, and unknown kinds.
    """
    errors: list[str] = []
    if not isinstance(nodes, (list, tuple)):
        raise DocumentValidationError(["nodes must be a list"])

    seen_ids: set[str] = set()
    validated: list[DocumentNode] = []
    for index, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            errors.append(f"nodes[{index}] must be an object")
            continue
        kind = raw.get("kind")
        if kind not in DOCUMENT_PRIMITIVE_KINDS:
            errors.append(
                f"nodes[{index}] kind {kind!r} is not a document primitive "
                f"(allowed: {sorted(DOCUMENT_PRIMITIVE_KINDS)})"
            )
            continue
        forbidden = {"page_break", "ruled_lines", "component_id", "template_id", "media"}
        leaked = sorted(k for k in forbidden if k in raw)
        if leaked:
            errors.append(f"nodes[{index}] contains forbidden fields: {leaked}")
            continue
        try:
            node = document_node_adapter.validate_python(raw)
        except Exception as exc:  # noqa: BLE001 — collect all node errors
            errors.append(f"nodes[{index}]: {exc}")
            continue
        if node.id in seen_ids:
            errors.append(f"duplicate node id {node.id!r}")
            continue
        seen_ids.add(node.id)
        validated.append(node)

    if errors:
        raise DocumentValidationError(errors)
    return validated

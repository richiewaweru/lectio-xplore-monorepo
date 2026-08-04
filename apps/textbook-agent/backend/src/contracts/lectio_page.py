"""Lectio page (@lectio/page) contract loaders and validation facade."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from contracts.generated.lectio_page import (
    CATALOGUE_VERSION,
    CONTRACT_VERSION,
    INTENT_IDS,
    PAGE_OBJECT_IDS,
    SYNCED_FILE_HASHES,
    catalogue_snapshot,
    is_known_intent,
    is_known_object,
)

__all__ = [
    "CATALOGUE_VERSION",
    "CONTRACT_VERSION",
    "INTENT_IDS",
    "PAGE_OBJECT_IDS",
    "SYNCED_FILE_HASHES",
    "catalogue_snapshot",
    "get_document_schema",
    "get_intent_catalogue",
    "get_object_catalogue",
    "get_sync_manifest",
    "is_known_intent",
    "is_known_object",
    "lectio_page_contracts_dir",
    "validate_document",
    "verify_synced_hashes",
]


def _backend_root() -> Path:
    # src/contracts/lectio_page.py → backend/
    return Path(__file__).resolve().parents[2]


def lectio_page_contracts_dir() -> Path:
    return _backend_root() / "contracts" / "lectio-page"


def _read_json(name: str) -> dict[str, Any]:
    path = lectio_page_contracts_dir() / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing synced lectio-page contract '{name}'. "
            "Run: python apps/textbook-agent/tools/update_lectio_page_contracts.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_document_schema() -> dict[str, Any]:
    return _read_json("lectio-document-v2.schema.json")


@lru_cache(maxsize=1)
def get_object_catalogue() -> dict[str, Any]:
    return _read_json("object-catalogue.v1.json")


@lru_cache(maxsize=1)
def get_intent_catalogue() -> dict[str, Any]:
    return _read_json("intent-catalogue.v1.json")


@lru_cache(maxsize=1)
def get_sync_manifest() -> dict[str, Any]:
    return _read_json("sync-manifest.json")


def verify_synced_hashes() -> list[str]:
    """Return human-readable drift errors (empty when in sync)."""
    errors: list[str] = []
    contracts_dir = lectio_page_contracts_dir()
    for name, expected in SYNCED_FILE_HASHES.items():
        path = contracts_dir / name
        if not path.exists():
            errors.append(f"missing synced file: {name}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"hash drift for {name}: expected {expected}, got {actual}")
    return errors


def validate_document(document: dict[str, Any]) -> list[str]:
    """Validate a LectioDocumentV2 dict against the synced JSON Schema.

    Returns a list of error strings; empty means valid.
    """
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
    except ImportError:  # pragma: no cover - optional dependency path
        return _structural_validate(document)

    schema = get_document_schema()
    validator = Draft202012Validator(schema)
    return sorted(
        f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(document)
    )


def _structural_validate(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document must be an object"]
    for key in ("id", "title", "sections"):
        if key not in document:
            errors.append(f"missing required field: {key}")
    sections = document.get("sections")
    if sections is not None and not isinstance(sections, list):
        errors.append("sections must be an array")
    elif isinstance(sections, list):
        for i, section in enumerate(sections):
            if not isinstance(section, dict):
                errors.append(f"sections[{i}] must be an object")
                continue
            if "title" not in section:
                errors.append(f"sections[{i}].title is required")
            blocks = section.get("blocks", [])
            if not isinstance(blocks, list):
                errors.append(f"sections[{i}].blocks must be an array")
                continue
            for j, block in enumerate(blocks):
                if not isinstance(block, dict):
                    errors.append(f"sections[{i}].blocks[{j}] must be an object")
                    continue
                obj = block.get("object")
                if obj and not is_known_object(str(obj)):
                    errors.append(f"sections[{i}].blocks[{j}].object unknown: {obj}")
                intent = block.get("intent")
                if intent and obj != "heading" and not is_known_intent(str(intent)):
                    errors.append(f"sections[{i}].blocks[{j}].intent unknown: {intent}")
                if block.get("position") != j:
                    errors.append(
                        f"sections[{i}].blocks[{j}].position must equal array index {j}"
                    )
    return errors

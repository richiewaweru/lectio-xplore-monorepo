"""Tests for synced @lectio/page contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


from contracts.lectio_page import (
    CATALOGUE_VERSION,
    PAGE_OBJECT_IDS,
    get_document_schema,
    validate_document,
    verify_synced_hashes,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "lectio-page"
MONOREPO_ROOT = BACKEND_ROOT.parent.parent.parent
PAGE_CONTRACTS = MONOREPO_ROOT / "packages" / "lectio-page" / "contracts"
SYNCED = BACKEND_ROOT / "contracts" / "lectio-page"


def test_catalogue_version_and_objects() -> None:
    assert CATALOGUE_VERSION == "1.1.0"
    assert "prose" in PAGE_OBJECT_IDS
    assert "heading" in PAGE_OBJECT_IDS
    assert len(PAGE_OBJECT_IDS) == 10


def test_synced_hashes_match_generated_manifest() -> None:
    assert verify_synced_hashes() == []


def test_synced_files_match_package_sources() -> None:
    for name in (
        "lectio-document-v2.schema.json",
        "intent-catalogue.v1.json",
        "object-catalogue.v1.json",
        "manifest.json",
    ):
        source = PAGE_CONTRACTS / name
        target = SYNCED / name
        assert source.exists(), source
        assert target.exists(), target
        assert hashlib.sha256(source.read_bytes()).hexdigest() == hashlib.sha256(
            target.read_bytes()
        ).hexdigest()


def test_valid_fixture_validates() -> None:
    doc = json.loads((FIXTURES / "valid-document.json").read_text(encoding="utf-8"))
    errors = validate_document(doc)
    assert errors == [], errors


def test_invalid_fixture_rejected() -> None:
    doc = json.loads((FIXTURES / "invalid-document.json").read_text(encoding="utf-8"))
    errors = validate_document(doc)
    assert errors, "expected validation errors for invalid document"


def test_document_schema_loads() -> None:
    schema = get_document_schema()
    assert schema.get("$schema") or schema.get("type") or schema.get("$id")

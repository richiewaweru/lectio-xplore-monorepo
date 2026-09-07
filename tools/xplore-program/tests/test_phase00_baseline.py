"""Tests for Phase 00 domain-boundary guard and baseline program artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools" / "xplore-program"
PROGRAM_DIR = REPO_ROOT / "docs" / "xplore-program"

sys.path.insert(0, str(TOOLS_DIR))

from check_domain_boundaries import find_violations  # noqa: E402


REQUIRED_ARTIFACTS = (
    "PROGRAM_STATE.md",
    "BASELINE_REUSE_MANIFEST.json",
    "BASELINE_REUSE_MANIFEST_SCHEMA.json",
    "CURRENT_ARCHITECTURE.md",
    "reports/phase-00/PHASE_REPORT.md",
)


def test_required_program_artifacts_exist() -> None:
    missing = [name for name in REQUIRED_ARTIFACTS if not (PROGRAM_DIR / name).exists()]
    assert not missing, f"Missing Phase 00 artifacts: {missing}"


def test_baseline_reuse_manifest_validates_against_schema() -> None:
    schema_path = PROGRAM_DIR / "BASELINE_REUSE_MANIFEST_SCHEMA.json"
    manifest_path = PROGRAM_DIR / "BASELINE_REUSE_MANIFEST.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for key in schema["required"]:
        assert key in manifest, f"manifest missing required key: {key}"

    assert isinstance(manifest["repos"], list) and len(manifest["repos"]) >= 3
    for repo in manifest["repos"]:
        for key in ("name", "path", "branch", "sha", "dirty"):
            assert key in repo, f"repo entry missing {key}: {repo}"

    assert isinstance(manifest["subsystems"], list) and len(manifest["subsystems"]) >= 5
    allowed = {"REUSE_AS_IS", "EXTEND", "REFACTOR", "REMOVE", "NEW"}
    for subsystem in manifest["subsystems"]:
        for key in ("name", "classification", "canonical_path", "evidence"):
            assert key in subsystem, f"subsystem missing {key}: {subsystem}"
        assert subsystem["classification"] in allowed

    assert isinstance(manifest["golden_paths"], list) and len(manifest["golden_paths"]) >= 2
    for path in manifest["golden_paths"]:
        for key in ("name", "steps", "commands", "status"):
            assert key in path, f"golden_path missing {key}: {path}"


def test_domain_boundaries_clean_in_current_checkout() -> None:
    violations = find_violations(REPO_ROOT)
    assert violations == [], (
        "Print/Learn domain boundary violations:\n"
        + "\n".join(f"{v.file_path}:{v.line} [{v.rule}] {v.snippet}" for v in violations)
    )


def test_page_package_must_not_import_learn(tmp_path: Path) -> None:
    page_src = tmp_path / "packages" / "lectio-page" / "src"
    page_src.mkdir(parents=True)
    bad = page_src / "bad.ts"
    bad.write_text("import { x } from 'lectio';\n", encoding="utf-8")
    violations = find_violations(tmp_path)
    assert any(v.rule == "page-must-not-import-learn" for v in violations)


def test_learn_package_must_not_import_page(tmp_path: Path) -> None:
    learn_src = tmp_path / "packages" / "lectio" / "src"
    learn_src.mkdir(parents=True)
    bad = learn_src / "bad.ts"
    bad.write_text("import type { LectioDocument } from '@lectio/page/contract';\n", encoding="utf-8")
    violations = find_violations(tmp_path)
    assert any(v.rule == "learn-must-not-import-page" for v in violations)

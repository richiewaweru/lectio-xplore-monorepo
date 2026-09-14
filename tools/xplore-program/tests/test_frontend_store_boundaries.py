"""Tests for frontend Unit/Print/Learn store boundary guard (P05 G19)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools" / "xplore-program"
sys.path.insert(0, str(TOOLS_DIR))

from check_frontend_store_boundaries import find_violations  # noqa: E402


def test_no_sibling_store_boundary_violations() -> None:
    violations = find_violations()
    assert violations == [], (
        "Frontend store boundary violations:\n"
        + "\n".join(f"{v.file_path}:{v.line} [{v.rule}] {v.snippet}" for v in violations)
    )


def test_guard_script_exists() -> None:
    assert (TOOLS_DIR / "check_frontend_store_boundaries.py").is_file()

"""Tests for backend domain-boundary guard (refactor R7)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "tools" / "xplore-program"
sys.path.insert(0, str(TOOLS_DIR))

from check_backend_domain_boundaries import find_violations  # noqa: E402


def test_backend_domain_boundaries_clean_in_current_checkout() -> None:
    violations = find_violations()
    assert violations == [], (
        "Backend domain boundary violations:\n"
        + "\n".join(f"{v.file_path}:{v.line} [{v.rule}] {v.snippet}" for v in violations)
    )

"""CLI safety for the whole-lesson evidence capture script.

The ``--run`` slug names a directory under the evidence root. It used to be a
hard-coded ``choices`` list, which rejected ad-hoc runs such as
``browser-smoke-science``. Widening it means the value now has to be validated
rather than enumerated, so traversal must be impossible.

The script is not an importable package (``scripts/`` has no ``__init__.py``), so
it is loaded by path, following ``tests/test_smoke_test_script.py``.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


def _load_capture_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "capture_whole_lesson_evidence.py"
    spec = importlib.util.spec_from_file_location("capture_whole_lesson_evidence", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPTURE = _load_capture_module()


@pytest.mark.parametrize(
    "slug",
    [
        # The four official runs must keep working.
        "run-01-science",
        "run-02-mathematics",
        "run-03-economics",
        "run-04-english",
        # The browser-smoke slugs that the old choices list rejected.
        "browser-smoke-science",
        "browser-smoke-economics",
        "a",
        "0",
        "a" * 64,
    ],
)
def test_accepts_safe_slugs(slug: str) -> None:
    assert CAPTURE.run_slug(slug) == slug


@pytest.mark.parametrize(
    "slug",
    [
        "",
        "..",
        "../outside",
        "run/../../etc",
        "run-01/nested",
        "run-01\\nested",
        "/absolute",
        "C:/absolute",
        "-leading-hyphen",
        "Run-01-Science",  # uppercase
        "run 01 science",  # spaces
        "run_01_science",  # underscore is not in the convention
        "a" * 65,  # too long
        ".hidden",
    ],
)
def test_rejects_unsafe_slugs(slug: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        CAPTURE.run_slug(slug)


def test_resolved_run_dir_stays_under_the_evidence_root() -> None:
    root = CAPTURE.EVIDENCE_ROOT.resolve()
    resolved = CAPTURE.resolve_run_dir("browser-smoke-science")
    assert resolved.parent == root
    assert resolved.name == "browser-smoke-science"


def test_argparse_rejects_a_traversal_slug() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=CAPTURE.run_slug)
    with pytest.raises(SystemExit):
        parser.parse_args(["--run", "../outside"])

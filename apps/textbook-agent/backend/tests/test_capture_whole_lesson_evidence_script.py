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
from planning.prompts import LESSON_APPROACH_PROMPT_V2_SHA256


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


def test_manifest_records_active_prompt_v2_and_frozen_form() -> None:
    assert CAPTURE.PROMPT_RESOURCES == (
        Path(__file__).resolve().parents[1] / "resources"
    )
    assert CAPTURE.PROMPT_MANIFEST["lesson_approach"] == {
        "id": "lesson-approach-planner",
        "file": "lesson-approach-planner-v2.txt",
        "version": 2,
    }
    assert CAPTURE.PROMPT_MANIFEST["form_planner"]["file"] == "form-planner-v1.txt"
    assert CAPTURE._prompt_sha256("lesson-approach-planner-v2.txt") == (
        LESSON_APPROACH_PROMPT_V2_SHA256
    )


def test_cli_accepts_browser_artifact_paths() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("generation_id")
    parser.add_argument("--run", required=True, type=CAPTURE.run_slug)
    parser.add_argument("--generation-page", type=Path, default=None)
    parser.add_argument("--teacher-pdf", type=Path, default=None)
    parser.add_argument("--student-pdf", type=Path, default=None)
    args = parser.parse_args(
        [
            "gen-1",
            "--run",
            "run-01-science",
            "--generation-page",
            "page.png",
            "--teacher-pdf",
            "teacher.pdf",
            "--student-pdf",
            "student.pdf",
        ]
    )
    assert args.generation_page == Path("page.png")
    assert args.teacher_pdf == Path("teacher.pdf")
    assert args.student_pdf == Path("student.pdf")


def test_sanitize_redacts_secrets_and_tokens() -> None:
    payload = CAPTURE.sanitize(
        {
            "generation_id": "g1",
            "access_token": "secret-token",
            "api_key": "sk-live",
            "nested": {"authorization": "Bearer abc", "stage": "ready"},
        }
    )
    assert payload["generation_id"] == "g1"
    assert payload["access_token"] == "[redacted]"
    assert payload["api_key"] == "[redacted]"
    assert payload["nested"]["authorization"] == "[redacted]"
    assert payload["nested"]["stage"] == "ready"


def test_ingest_browser_artifact_copies_and_hashes(tmp_path: Path) -> None:
    source = tmp_path / "shot.png"
    source.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    dest = tmp_path / "run" / "34-generation-page.png"
    info = CAPTURE.ingest_browser_artifact(source, dest, expected_suffix=".png")
    assert info is not None
    assert dest.is_file()
    assert info["sha256"] == CAPTURE._sha256_file(source)
    assert CAPTURE.ingest_browser_artifact(None, dest, expected_suffix=".png") is None


def test_ingest_missing_browser_artifact_does_not_fabricate(tmp_path: Path) -> None:
    dest = tmp_path / "35-teacher.pdf"
    with pytest.raises(FileNotFoundError):
        CAPTURE.ingest_browser_artifact(tmp_path / "missing.pdf", dest, expected_suffix=".pdf")
    assert not dest.exists()

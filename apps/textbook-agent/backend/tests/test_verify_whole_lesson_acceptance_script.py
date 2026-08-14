"""Acceptance verifier for captured whole-lesson evidence folders."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas


def _load_verify_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_whole_lesson_acceptance.py"
    spec = importlib.util.spec_from_file_location("verify_whole_lesson_acceptance", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = _load_verify_module()

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
    b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_pdf(path: Path, text: str) -> None:
    canvas = Canvas(str(path), pagesize=letter)
    canvas.drawString(72, 720, text)
    canvas.save()


def _complete_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run-01-science"
    run_dir.mkdir()
    (run_dir / "22-writer-prompts").mkdir()
    (run_dir / "23-writer-responses-raw").mkdir()
    (run_dir / "22-writer-prompts" / "explain.txt").write_text("prompt", encoding="utf-8")
    (run_dir / "23-writer-responses-raw" / "explain.txt").write_text("raw", encoding="utf-8")
    digest = "a" * 64
    manifest = {
        "generation_id": "gen-1",
        "native_whole_lesson": True,
        "contract_version": 2,
        "stage": "ready",
        "document_sha256": digest,
        "reloaded_sha256": digest,
        "reload_verified": True,
        "missing": [],
    }
    (run_dir / "00-manifest.yaml").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name in VERIFY.PROTOCOL_ARTIFACTS:
        path = run_dir / name
        if name in {"00-manifest.yaml", "22-writer-prompts", "23-writer-responses-raw"}:
            continue
        if name.endswith(".json"):
            path.write_text("{}\n", encoding="utf-8")
        elif name.endswith(".jsonl"):
            path.write_text("{}\n", encoding="utf-8")
        elif name.endswith(".md") or name.endswith(".txt") or name.endswith(".csv"):
            path.write_text("captured\n", encoding="utf-8")
    (run_dir / "29-persisted-generation-record.json").write_text(
        json.dumps(
            {
                "id": "gen-1",
                "status": "ready",
                "native_whole_lesson": True,
                "contract_version": 2,
                "document_sha256": digest,
                "reloaded_sha256": digest,
                "reload_verified": True,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "27-visual-work-orders.json").write_text(
        json.dumps(
            [
                {
                    "request_id": "req-fig-1",
                    "status": "ready",
                    "asset": {"status": "ready", "src": "/images/fig.png"},
                    "visual_qc": {"status": "accepted"},
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "34-generation-page.png").write_bytes(_MIN_PNG)
    _write_pdf(run_dir / "35-teacher.pdf", "Lesson Answer Key")
    _write_pdf(run_dir / "36-student.pdf", "Lesson Student Edition")
    (run_dir / "40-telemetry-ledger.json").write_text(
        json.dumps(
            [
                {
                    "id": "call-1",
                    "trace_id": "tr-1",
                    "generation_id": "gen-1",
                    "caller": "form_planner",
                    "node": "planning_forms",
                    "status": "ok",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run_dir / "41-legacy-audit.json").write_text(
        json.dumps(
            {
                "editable_lessons": [],
                "builder_or_stage2_requests": [],
                "zero_current_legacy": True,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "43-native-identity.json").write_text(
        json.dumps({"native_whole_lesson": True, "contract_version": 2, "stage": "ready"}),
        encoding="utf-8",
    )
    return run_dir


def test_complete_pass(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    assert VERIFY.verify_run_dir(run_dir) == []


@pytest.mark.parametrize("artifact", VERIFY.PROTOCOL_ARTIFACTS)
def test_missing_required_artifact_fails(tmp_path: Path, artifact: str) -> None:
    run_dir = _complete_run(tmp_path)
    target = run_dir / artifact
    if target.is_dir():
        for child in target.iterdir():
            child.unlink()
        target.rmdir()
    elif target.is_file():
        target.unlink()
    failures = VERIFY.verify_run_dir(run_dir)
    assert any(artifact in item for item in failures)


def test_native_identity_false_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    (run_dir / "29-persisted-generation-record.json").write_text(
        json.dumps(
            {
                "id": "gen-1",
                "status": "ready",
                "native_whole_lesson": False,
                "contract_version": 2,
                "document_sha256": "a" * 64,
                "reloaded_sha256": "a" * 64,
                "reload_verified": True,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "00-manifest.yaml").write_text(
        json.dumps({"native_whole_lesson": False, "contract_version": 2, "stage": "ready"}),
        encoding="utf-8",
    )
    (run_dir / "43-native-identity.json").write_text(
        json.dumps({"native_whole_lesson": False}),
        encoding="utf-8",
    )
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("native identity" in item for item in failures)


def test_hash_mismatch_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    record = json.loads((run_dir / "29-persisted-generation-record.json").read_text(encoding="utf-8"))
    record["reloaded_sha256"] = "b" * 64
    (run_dir / "29-persisted-generation-record.json").write_text(json.dumps(record), encoding="utf-8")
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("unequal" in item for item in failures)


def test_telemetry_gap_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    (run_dir / "40-telemetry-ledger.json").write_text(
        json.dumps([{"id": "call-1", "generation_id": None, "caller": "form"}]),
        encoding="utf-8",
    )
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("telemetry" in item for item in failures)


def test_pdf_answer_mismatch_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    _write_pdf(run_dir / "35-teacher.pdf", "Lesson without answers")
    _write_pdf(run_dir / "36-student.pdf", "Student Answer Key")
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("teacher PDF" in item for item in failures)
    assert any("student PDF" in item for item in failures)


def test_legacy_leakage_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    (run_dir / "41-legacy-audit.json").write_text(
        json.dumps(
            {
                "editable_lessons": [{"id": "ed-1", "source_generation_id": "gen-1"}],
                "builder_or_stage2_requests": ["/api/v1/builder/lessons"],
                "zero_current_legacy": False,
            }
        ),
        encoding="utf-8",
    )
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("legacy" in item for item in failures)


def test_flagged_visual_qc_fails(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    (run_dir / "27-visual-work-orders.json").write_text(
        json.dumps(
            [
                {
                    "request_id": "req-fig-1",
                    "visual_qc": {"status": "flagged_quality"},
                    "asset": {"status": "failed"},
                }
            ]
        ),
        encoding="utf-8",
    )
    failures = VERIFY.verify_run_dir(run_dir)
    assert any("QC" in item for item in failures)


def test_malformed_manifest_is_error(tmp_path: Path) -> None:
    run_dir = _complete_run(tmp_path)
    (run_dir / "00-manifest.yaml").write_text("{", encoding="utf-8")
    with pytest.raises(VERIFY.EvidenceError):
        VERIFY.verify_run_dir(run_dir)

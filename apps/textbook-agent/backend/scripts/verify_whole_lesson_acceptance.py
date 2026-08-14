"""Verify a captured whole-lesson evidence folder against final acceptance gates.

Exit codes:
  0 — all represented final gates pass
  2 — evidence incomplete or a gate fails
  1 — malformed/unreadable evidence
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_ARTIFACTS = [
    "00-manifest.yaml",
    "01-unit-input.json",
    "02-scope-contract.json",
    "03-path-plan-raw.txt",
    "04-path-plan.json",
    "05-path-approval.json",
    "06-lesson-packet.json",
    "07-teaching-guidance.json",
    "08-lesson-approach-prompt.txt",
    "09-lesson-approach-response-raw.txt",
    "10-teaching-plan.json",
    "11-teaching-validation.json",
    "12-teaching-qc.json",
    "13-teacher-plan-review.json",
    "14-teaching-plan-approval.json",
    "15-form-guidance.json",
    "16-form-planner-prompt.txt",
    "17-form-planner-response-raw.txt",
    "18-form-plan.json",
    "19-form-validation.json",
    "20-form-qc.json",
    "21-writer-call-ledger.csv",
    "22-writer-prompts",
    "23-writer-responses-raw",
    "24-writer-results.json",
    "25-approved-item-records.json",
    "26-question-assembly.json",
    "27-visual-work-orders.json",
    "28-event-stream.jsonl",
    "29-persisted-generation-record.json",
    "30-reloaded-lectio-document.json",
    "31-document-validation.json",
    "32-input-output-trace.md",
    "33-quality-scorecard.md",
    "34-generation-page.png",
    "35-teacher.pdf",
    "36-student.pdf",
    "37-timing-and-cost.json",
    "38-run-log.txt",
    "39-conclusion.md",
]


class EvidenceError(RuntimeError):
    """Malformed or unreadable evidence."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidenceError(f"missing file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"unreadable JSON: {path.name}") from exc


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceError("missing file: 00-manifest.yaml")
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
        if isinstance(payload, Mapping):
            return dict(payload)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore[import-untyped]

        payload = yaml.safe_load(text)
    except Exception as exc:
        raise EvidenceError("unreadable manifest: 00-manifest.yaml") from exc
    if not isinstance(payload, Mapping):
        raise EvidenceError("unreadable manifest: 00-manifest.yaml")
    return dict(payload)


def _pdf_answer_key_count(path: Path) -> int:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.casefold().count("answer key")


def _artifact_exists(run_dir: Path, name: str) -> bool:
    path = run_dir / name
    if name in {"22-writer-prompts", "23-writer-responses-raw"}:
        return path.is_dir()
    return path.is_file() and path.stat().st_size > 0


def verify_run_dir(run_dir: Path) -> list[str]:
    """Return fail reasons. Empty list means all gates pass."""
    if not run_dir.is_dir():
        raise EvidenceError(f"run directory does not exist: {run_dir}")
    failures: list[str] = []
    for name in PROTOCOL_ARTIFACTS:
        if not _artifact_exists(run_dir, name):
            failures.append(f"required protocol artifact absent: {name}")

    manifest_path = run_dir / "00-manifest.yaml"
    record_path = run_dir / "29-persisted-generation-record.json"
    if not manifest_path.is_file() or not record_path.is_file():
        return failures

    manifest = _load_manifest(manifest_path)
    record = _load_json(record_path)
    if not isinstance(record, Mapping):
        raise EvidenceError("29-persisted-generation-record.json is not an object")
    identity = run_dir / "43-native-identity.json"
    identity_payload = _load_json(identity) if identity.is_file() else {}
    native = bool(
        manifest.get("native_whole_lesson")
        or record.get("native_whole_lesson")
        or (identity_payload.get("native_whole_lesson") if isinstance(identity_payload, Mapping) else False)
    )
    if not native:
        failures.append("native identity is missing or false")
    contract = record.get("contract_version") or manifest.get("contract_version")
    try:
        contract_n = int(contract)
    except (TypeError, ValueError):
        contract_n = 0
    if contract_n < 2:
        failures.append("native contract version is missing or not v2")

    stage = str(record.get("status") or record.get("stage") or manifest.get("stage") or "")
    if stage != "ready":
        failures.append(f"final stage is {stage!r}, expected ready")

    document_sha256 = str(record.get("document_sha256") or manifest.get("document_sha256") or "")
    reloaded_sha256 = str(record.get("reloaded_sha256") or manifest.get("reloaded_sha256") or "")
    reload_verified = bool(record.get("reload_verified") if "reload_verified" in record else manifest.get("reload_verified"))
    if not document_sha256 or not reloaded_sha256:
        failures.append("document hashes are empty")
    elif document_sha256 != reloaded_sha256:
        failures.append("document hashes are unequal")
    if not reload_verified:
        failures.append("reload_verified is false")

    visuals_path = run_dir / "27-visual-work-orders.json"
    if visuals_path.is_file():
        visuals = _load_json(visuals_path)
        visual_rows: list[Mapping[str, Any]] = []
        if isinstance(visuals, list):
            visual_rows = [row for row in visuals if isinstance(row, Mapping) and row.get("request_id")]
        elif isinstance(visuals, Mapping):
            orders = visuals.get("orders")
            if isinstance(orders, list):
                visual_rows = [row for row in orders if isinstance(row, Mapping) and row.get("request_id")]
        for row in visual_rows:
            qc = row.get("visual_qc") if isinstance(row.get("visual_qc"), Mapping) else {}
            status = str(qc.get("status") or "").casefold()
            asset = row.get("asset") if isinstance(row.get("asset"), Mapping) else {}
            if status in {"flag", "flagged_quality", "reject", "rejected", ""}:
                failures.append(
                    f"required visual {row.get('request_id')} QC is flagged, rejected, or missing"
                )
            elif str(asset.get("status") or "") != "ready":
                failures.append(f"required visual {row.get('request_id')} is not ready")

    teacher_pdf = run_dir / "35-teacher.pdf"
    student_pdf = run_dir / "36-student.pdf"
    if teacher_pdf.is_file() and teacher_pdf.stat().st_size > 0:
        teacher_keys = _pdf_answer_key_count(teacher_pdf)
        if teacher_keys != 1:
            failures.append(f"teacher PDF answer-key count is {teacher_keys}, expected 1")
    else:
        failures.append("teacher PDF evidence is absent")
    if student_pdf.is_file() and student_pdf.stat().st_size > 0:
        student_keys = _pdf_answer_key_count(student_pdf)
        if student_keys != 0:
            failures.append(f"student PDF answer-key count is {student_keys}, expected 0")
    else:
        failures.append("student PDF evidence is absent")

    telemetry_path = run_dir / "40-telemetry-ledger.json"
    if telemetry_path.is_file():
        telemetry = _load_json(telemetry_path)
        if not isinstance(telemetry, list):
            raise EvidenceError("40-telemetry-ledger.json is not a list")
        for row in telemetry:
            if not isinstance(row, Mapping):
                failures.append("telemetry row is not an object")
                continue
            if not row.get("generation_id"):
                failures.append("telemetry rows lack generation attribution for current-path calls")
                break
    else:
        failures.append("telemetry ledger is absent")

    legacy_path = run_dir / "41-legacy-audit.json"
    if legacy_path.is_file():
        legacy = _load_json(legacy_path)
        if not isinstance(legacy, Mapping):
            raise EvidenceError("41-legacy-audit.json is not an object")
        lessons = legacy.get("editable_lessons") or []
        requests = legacy.get("builder_or_stage2_requests") or []
        if lessons or requests or legacy.get("zero_current_legacy") is False:
            failures.append("legacy current-generation records or requests exist")
    else:
        failures.append("legacy audit is absent")

    screenshot = run_dir / "34-generation-page.png"
    if not screenshot.is_file() or screenshot.stat().st_size == 0:
        failures.append("authenticated generation-page screenshot is absent")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        failures = verify_run_dir(args.run_dir)
    except EvidenceError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    payload = {"ok": not failures, "failures": failures, "run_dir": str(args.run_dir)}
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Phase 02 Commit E — four official native end-to-end lesson runs (API driver).

Freeze prompts: do not edit planner/writer prompts between subjects.
Requires a running Textbook Agent API and auth token.

Usage:
  set PHASE02_API_BASE=http://localhost:8000
  set PHASE02_AUTH_TOKEN=...
  uv run python tools/phase02_four_runs_driver.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SUBJECTS = (
    ("Science", "Explain why plants need light to make food."),
    ("Mathematics", "Explain why multiplying by ten shifts place value."),
    ("Economics", "Explain opportunity cost with a classroom choice."),
    ("English", "Explain how a thesis guides a short argument paragraph."),
)

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "evidence"
    / "whole-lesson-runs"
    / "phase-02"
    / "four-runs"
)


def _request(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return int(resp.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"detail": str(exc)}
        except json.JSONDecodeError:
            payload = {"detail": raw or str(exc)}
        return int(exc.code), payload


def main() -> int:
    base = os.environ.get("PHASE02_API_BASE", "http://localhost:8000").rstrip("/")
    token = os.environ.get("PHASE02_AUTH_TOKEN", "").strip()
    if not token:
        print("PHASE02_AUTH_TOKEN is required", file=sys.stderr)
        return 2
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for subject, objective in SUBJECTS:
        entry = {
            "subject": subject,
            "objective": objective,
            "generation_id": None,
            "approve_status": None,
            "terminal_status": None,
            "legacy_invoked": False,
            "error": None,
        }
        print(f"=== {subject} ===")
        # Driver expects an already-created generation id via env map, or
        # PHASE02_GENERATION_IDS=Science:<id>,Mathematics:<id>,...
        mapping = {}
        for part in os.environ.get("PHASE02_GENERATION_IDS", "").split(","):
            part = part.strip()
            if ":" in part:
                k, v = part.split(":", 1)
                mapping[k.strip()] = v.strip()
        gid = mapping.get(subject)
        if not gid:
            entry["error"] = "missing generation id in PHASE02_GENERATION_IDS"
            results.append(entry)
            continue
        entry["generation_id"] = gid
        code, approve = _request(
            "POST",
            f"{base}/api/v1/v3/generations/{gid}/lesson-approach/approve",
            token,
            {"expected_revision": 1, "teacher_note": "Phase 02 official run"},
        )
        entry["approve_http"] = code
        entry["approve_status"] = approve.get("status")
        if code != 202:
            entry["error"] = f"approve expected 202, got {code}: {approve}"
            results.append(entry)
            continue
        terminal = None
        for _ in range(180):
            scode, status = _request(
                "GET",
                f"{base}/api/v1/v3/chunked/{gid}/status",
                token,
            )
            if scode != 200:
                time.sleep(2)
                continue
            stage = status.get("stage")
            if stage in {"ready", "awaiting_visuals", "completed", "failed_terminal", "failed_recoverable"}:
                terminal = stage
                break
            time.sleep(2)
        entry["terminal_status"] = terminal
        results.append(entry)
        (EVIDENCE_DIR / f"{subject.lower()}-run.json").write_text(
            json.dumps(entry, indent=2), encoding="utf-8"
        )
    summary_path = EVIDENCE_DIR / "SUMMARY.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    ok = all(r.get("approve_http") == 202 and r.get("terminal_status") in {"ready", "awaiting_visuals"} for r in results)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

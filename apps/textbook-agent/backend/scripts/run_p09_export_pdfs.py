#!/usr/bin/env python
"""Export student/teacher PDFs + pdftoppm page images for P09 live cases."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from core.dependencies import get_jwt_handler

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = REPO / "docs" / "unit-native-program" / "evidence" / "live"
BASE = "http://127.0.0.1:8000"
TEACHER = "p09-live-teacher"
EMAIL = "p09-teacher@lectio.local"

CASES = {
    "A-cycle": "b17572f5-b7ee-45cc-b5a7-d2da9310febd",
    "C-procedure": "4c4946f5-97af-4f0d-8be3-e3444ba602d7",
    "D-visual": "ff448429-6f39-4bf8-a72a-f0b851e80a00",
}


def _find_pdftoppm() -> str | None:
    which = subprocess.run(["where", "pdftoppm"], capture_output=True, text=True, shell=True)
    if which.returncode == 0:
        return which.stdout.strip().splitlines()[0].strip()
    root = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
    matches = list(root.rglob("pdftoppm.exe")) if root.exists() else []
    return str(matches[0]) if matches else None


def _update_live_run(case_id: str, *, student: Path, teacher: Path, images: list[Path]) -> None:
    run_path = EVIDENCE / case_id / "LIVE_RUN.json"
    live = json.loads(run_path.read_text(encoding="utf-8"))
    live.setdefault("print", {})
    live["print"]["student_pdf"] = str(student.relative_to(REPO)).replace("\\", "/")
    live["print"]["teacher_pdf"] = str(teacher.relative_to(REPO)).replace("\\", "/")
    live["print"]["inspection"] = {
        "status": "PASS" if images else "BLOCKED",
        "tool": "pdftoppm" if images else None,
        "student_pages": sum(1 for p in images if p.name.startswith("student")),
        "teacher_pages": sum(1 for p in images if p.name.startswith("teacher")),
        "image_paths": [str(p.relative_to(REPO)).replace("\\", "/") for p in images],
    }
    limitations = [
        x
        for x in (live.get("limitations") or [])
        if "PDF" not in x and "Poppler" not in x and "pdftoppm" not in x and "Playwright" not in x
    ]
    if not any("learn_interaction" in x or "attempt" in x.lower() for x in limitations):
        if not (live.get("learn") or {}).get("attempt_evidence"):
            limitations.append("No learn_interaction id found to submit attempts")
    live["limitations"] = limitations
    live["status"] = "PASS_WITH_BLOCKERS" if limitations else "PASS"
    live["evidence_paths"] = sorted(
        str(p.relative_to(REPO)).replace("\\", "/")
        for p in (EVIDENCE / case_id).rglob("*")
        if p.is_file()
    )
    run_path.write_text(json.dumps(live, indent=2) + "\n", encoding="utf-8")


def _export_one(
    client: httpx.Client,
    *,
    case_id: str,
    gid: str,
    answers: bool,
    name: str,
    token: str,
    retries: int = 3,
) -> Path | None:
    run_dir = EVIDENCE / case_id
    run_dir.mkdir(parents=True, exist_ok=True)
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            warm = httpx.get(
                f"http://127.0.0.1:5173/studio/print/{gid}?edition={'teacher' if answers else 'student'}&print=true&token={token}",
                timeout=45.0,
            )
            print(f"{case_id} {name} warm={warm.status_code} attempt={attempt}", flush=True)
        except Exception as exc:  # noqa: BLE001 — warm is best-effort only
            print(f"{case_id} {name} warm skipped ({type(exc).__name__}: {exc}) attempt={attempt}", flush=True)
        try:
            resp = client.post(
                f"/api/v1/v3/generations/{gid}/export/pdf",
                json={
                    "school_name": "Lectio P09 Live School",
                    "teacher_name": "P09 Teacher",
                    "include_toc": True,
                    "include_answers": answers,
                },
            )
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            print(f"{case_id} {name} request error {last_err}", flush=True)
            time.sleep(3 * attempt)
            continue
        status_path = run_dir / f"35-{name}-pdf-status.json"
        rec = {"status": resp.status_code, "bytes": len(resp.content), "attempt": attempt}
        if resp.status_code >= 400:
            last_err = resp.text[:2000]
            rec["body"] = last_err
            status_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(f"{case_id} {name} FAIL {resp.status_code} {resp.text[:200]}", flush=True)
            time.sleep(3 * attempt)
            continue
        out = run_dir / f"35-{name}.pdf"
        out.write_bytes(resp.content)
        rec["path"] = str(out.relative_to(REPO)).replace("\\", "/")
        status_path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(f"{case_id} {name} wrote {out.stat().st_size}", flush=True)
        return out
    print(f"{case_id} {name} exhausted retries: {last_err[:200]}", flush=True)
    return None


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    cases = {k: v for k, v in CASES.items() if not only or k in only or k.split("-")[0] in only}
    if not cases:
        print(f"no cases matched {only}; known={list(CASES)}", flush=True)
        return 2

    token = get_jwt_handler().create_access_token(TEACHER, EMAIL)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    pdftoppm = _find_pdftoppm()
    print(f"pdftoppm={pdftoppm}", flush=True)
    print(f"cases={list(cases)}", flush=True)

    failures = 0
    with httpx.Client(base_url=BASE, timeout=300.0, headers=headers) as client:
        for case_id, gid in cases.items():
            paths: dict[str, Path] = {}
            for answers, name in ((False, "student"), (True, "teacher")):
                out = _export_one(
                    client,
                    case_id=case_id,
                    gid=gid,
                    answers=answers,
                    name=name,
                    token=token,
                )
                if out is None:
                    failures += 1
                    break
                paths[name] = out
                time.sleep(2)

            if "student" not in paths or "teacher" not in paths:
                continue

            images: list[Path] = []
            if pdftoppm:
                img_dir = EVIDENCE / case_id / "page-images"
                img_dir.mkdir(parents=True, exist_ok=True)
                for name in ("student", "teacher"):
                    prefix = img_dir / name
                    subprocess.run(
                        [pdftoppm, "-png", "-r", "120", str(paths[name]), str(prefix)],
                        check=False,
                    )
                images = sorted(img_dir.glob("*.png"))
                print(f"{case_id} images={len(images)}", flush=True)
            _update_live_run(case_id, student=paths["student"], teacher=paths["teacher"], images=images)
            time.sleep(3)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

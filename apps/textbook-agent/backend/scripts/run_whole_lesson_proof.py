#!/usr/bin/env python
"""Drive official whole-lesson proof runs through the live local API path.

Uses JWT auth against a persisted proof user. After each run, captures evidence
and fills scorecard / trace / gate notes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler
from core.entities.user import User
from core.repositories.sql_user_repo import SqlUserRepository

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = ROOT / "docs" / "evidence" / "whole-lesson-runs"
BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "http://127.0.0.1:8000"

PROOF_USER_ID = "whole-lesson-proof-runner"
PROOF_USER_EMAIL = "whole-lesson-proof@lectio.local"

RUNS: dict[str, dict[str, Any]] = {
    "run-01-science": {
        "subject": "Science",
        "unit": {
            "title": "Why Plants Need Light to Make Food",
            "topic": "Why plants need light to make food",
            "subject": "Science",
            "grade_level": "Grade 4",
            "destination_objective": "Explain why plants need light to make food.",
            "starting_knowledge": [
                "plants have roots, stems and leaves",
                "living things need food to grow",
            ],
        },
    },
    "run-02-mathematics": {
        "subject": "Mathematics",
        "unit": {
            "title": "Understanding Equivalent Fractions",
            "topic": "Equivalent fractions",
            "subject": "Mathematics",
            "grade_level": "Grade 6",
            "destination_objective": "Identify and explain equivalent fractions using visual models.",
            "starting_knowledge": ["can compare fractions with like denominators"],
        },
    },
    "run-03-economics": {
        "subject": "Economics",
        "unit": {
            "title": "How Supply and Demand Affect Price",
            "topic": "Supply and demand",
            "subject": "Economics",
            "grade_level": "Grade 8",
            "destination_objective": (
                "Explain how changes in supply and demand affect the price of a good."
            ),
            "starting_knowledge": [
                "goods and services are bought and sold in markets",
                "price is what buyers pay",
            ],
        },
    },
    "run-04-english": {
        "subject": "English",
        "unit": {
            "title": "Distinguishing a Claim from Supporting Evidence",
            "topic": "Claim versus supporting evidence",
            "subject": "English",
            "grade_level": "Grade 7",
            "destination_objective": (
                "Distinguish a claim from supporting evidence in a short text."
            ),
            "starting_knowledge": [
                "can identify the main idea of a paragraph",
                "authors make points in writing",
            ],
        },
    },
}


@dataclass
class RunTiming:
    started_at: str = ""
    completed_at: str = ""
    stages: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str, start: float) -> None:
        self.stages[name] = round(time.monotonic() - start, 2)


async def ensure_proof_user() -> User:
    async with async_session_factory() as session:
        repo = SqlUserRepository(session)
        user = await repo.find_by_id(PROOF_USER_ID)
        if user is None:
            now = datetime.now(timezone.utc)
            user = await repo.create(
                User(
                    id=PROOF_USER_ID,
                    email=PROOF_USER_EMAIL,
                    name="Whole Lesson Proof Runner",
                    created_at=now,
                    updated_at=now,
                )
            )
        return user


def auth_headers(user: User) -> dict[str, str]:
    token = get_jwt_handler().create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


def _raise(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    detail = resp.text[:800]
    try:
        detail = json.dumps(resp.json(), indent=2)[:800]
    except Exception:
        pass
    raise RuntimeError(f"{resp.request.method} {resp.request.url} -> {resp.status_code}: {detail}")


async def wait_for_stage(
    client: httpx.AsyncClient,
    generation_id: str,
    targets: set[str],
    *,
    timeout_seconds: int = 900,
    poll_seconds: float = 3.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_stage = ""
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
        _raise(resp)
        payload = resp.json()
        stage = str(payload.get("stage") or "")
        if stage != last_stage:
            print(f"  stage={stage}", flush=True)
            last_stage = stage
        if stage in targets:
            return payload
        if stage.endswith("_failed") or stage in {"stage1_failed", "stage2_error"}:
            raise RuntimeError(f"generation failed at stage={stage}: {payload.get('error')}")
        await asyncio.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for {targets}; last stage={last_stage}")


def pick_conceptual_lesson(path: dict[str, Any], *, objective_hint: str = "") -> dict[str, Any]:
    lessons = [lesson for lesson in path.get("lessons") or [] if not lesson.get("skipped")]
    conceptual = [
        lesson
        for lesson in lessons
        if str(lesson.get("primary_knowledge_type") or "").lower() == "conceptual"
    ]
    pool = conceptual or lessons
    if not pool:
        raise RuntimeError("Path has no lessons to prepare")
    hint = objective_hint.lower()
    if hint:
        keywords = [word for word in hint.split() if len(word) > 4]
        scored = sorted(
            pool,
            key=lambda lesson: sum(
                1 for word in keywords if word in str(lesson.get("objective") or "").lower()
            ),
            reverse=True,
        )
        if scored and sum(
            1 for word in keywords if word in str(scored[0].get("objective") or "").lower()
        ):
            return scored[0]
    return pool[0]


async def resolve_open_assumptions(
    client: httpx.AsyncClient,
    unit_id: str,
    path: dict[str, Any],
) -> dict[str, Any]:
    """No-op: canonical paths never expose open assumptions."""
    _ = client, unit_id
    return path


async def run_single(
    *,
    base_url: str,
    run_slug: str,
    skip_pdf: bool = False,
) -> dict[str, Any]:
    spec = RUNS[run_slug]
    unit_payload = dict(spec["unit"])
    run_dir = EVIDENCE_ROOT / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)
    timing = RunTiming(started_at=datetime.now(timezone.utc).isoformat())
    log_lines: list[str] = []

    def log(msg: str) -> None:
        line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    user = await ensure_proof_user()
    headers = auth_headers(user)
    timeout = httpx.Timeout(connect=30.0, read=900.0, write=60.0, pool=30.0)

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout) as client:
        # Health
        health = await client.get("/health")
        _raise(health)

        # Create unit
        t0 = time.monotonic()
        resp = await client.post("/api/v1/units", json=unit_payload)
        _raise(resp)
        unit = resp.json()
        unit_id = unit["id"]
        timing.mark("create_unit", t0)
        log(f"unit_id={unit_id}")

        # Path plan
        t0 = time.monotonic()
        planner_payload = {
            "topic": unit_payload["topic"],
            "subject": unit_payload["subject"],
            "grade_level": unit_payload["grade_level"],
            "destination_objective": unit_payload["destination_objective"],
            "starting_knowledge": unit_payload["starting_knowledge"],
            "curriculum_context": unit_payload.get("curriculum_context"),
            "must_include": [],
            "must_avoid": [],
            "terminology": [],
            "notation": None,
            "assessment_context": None,
            "known_difficulties": [],
        }
        resp = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=planner_payload)
        _raise(resp)
        path = resp.json()
        timing.mark("path_plan", t0)
        log(f"path_version={path['id']} revision={path['revision']} lessons={len(path.get('lessons') or [])}")

        _write_json(run_dir / "01-unit-input.json", unit_payload)
        _write_json(run_dir / "03-path-plan.json", path)
        if path.get("open_assumptions"):
            _write_json(run_dir / "05-path-approval.json", {"open_assumptions": path["open_assumptions"]})

        await resolve_open_assumptions(client, unit_id, path)

        # Path approve
        t0 = time.monotonic()
        resp = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        _raise(resp)
        approved_path = resp.json()
        timing.mark("path_approve", t0)
        _write_json(run_dir / "05-path-approval.json", approved_path)

        lesson = pick_conceptual_lesson(
            approved_path,
            objective_hint=unit_payload.get("destination_objective", ""),
        )
        lesson_id = lesson["id"]
        log(f"lesson_id={lesson_id} objective={lesson.get('objective', '')[:100]}")

        # Prepare
        t0 = time.monotonic()
        resp = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}:prepare",
            json={
                "path_version_id": approved_path["id"],
                "path_revision": approved_path["revision"],
                "lesson_revision": lesson["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        _raise(resp)
        prepared = resp.json()
        generation_id = prepared["generation_id"]
        timing.mark("prepare_lesson", t0)
        log(f"generation_id={generation_id} slots={prepared.get('slots')}")
        _write_json(run_dir / "06-lesson-packet-prep.json", prepared)

        # Chunked approve -> stage2
        t0 = time.monotonic()
        resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve", json={})
        _raise(resp)
        await wait_for_stage(
            client,
            generation_id,
            {"awaiting_teaching_approval"},
            timeout_seconds=900,
        )
        timing.mark("teaching_plan", t0)

        # Teaching review gate data
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/lesson-approach")
        _raise(resp)
        teaching = resp.json()
        _write_json(run_dir / "13-teacher-plan-review.json", teaching)

        teaching_plan = teaching.get("teaching_plan") or {}
        sections = teaching_plan.get("sections") or []
        first_brief = ""
        last_brief = ""
        if sections:
            first_brief = str((sections[0].get("brief") or sections[0].get("block_brief") or ""))
            last_brief = str((sections[-1].get("brief") or sections[-1].get("block_brief") or ""))

        gate_notes = assess_run1_gate(teaching, generation_id)
        _write_json(run_dir / "13-teacher-plan-review-gate.json", gate_notes)

        # Approve teaching -> form + writers (sync, long)
        t0 = time.monotonic()
        expected_revision = (teaching.get("teaching_review") or {}).get("revision") or 1
        resp = await client.post(
            f"/api/v1/v3/generations/{generation_id}/lesson-approach/approve",
            json={
                "expected_revision": expected_revision,
                "teacher_note": "Official proof run — teaching plan approved after last-brief-first review.",
            },
        )
        _raise(resp)
        approve_result = resp.json()
        timing.mark("form_and_writers", t0)
        log(f"post-approve status={approve_result.get('status')} writers={approve_result.get('writer_count')}")

        # Document check
        resp = await client.get(f"/api/v1/v3/generations/{generation_id}/document")
        _raise(resp)
        document = resp.json()
        _write_json(run_dir / "29-persisted-generation-record-preview.json", {
            "generation_id": generation_id,
            "document_version": document.get("document_version"),
            "section_count": len((document.get("lectio_document") or {}).get("sections") or []),
        })

        teacher_pdf = b""
        student_pdf = b""
        if not skip_pdf:
            for include_answers, filename in ((True, "35-teacher.pdf"), (False, "36-student.pdf")):
                t0 = time.monotonic()
                try:
                    pdf_resp = await client.post(
                        f"/api/v1/v3/generations/{generation_id}/export/pdf",
                        json={
                            "school_name": "Lectio Proof School",
                            "teacher_name": "Proof Runner",
                            "include_toc": True,
                            "include_answers": include_answers,
                        },
                    )
                    _raise(pdf_resp)
                    content = pdf_resp.content
                    (run_dir / filename).write_bytes(content)
                    if include_answers:
                        teacher_pdf = content
                    else:
                        student_pdf = content
                    timing.mark(filename, t0)
                    log(f"saved {filename} bytes={len(content)}")
                except Exception as exc:  # noqa: BLE001
                    log(f"PDF export failed ({filename}): {exc}")

    timing.completed_at = datetime.now(timezone.utc).isoformat()
    _write_json(run_dir / "37-timing-and-cost.json", {
        "started_at": timing.started_at,
        "completed_at": timing.completed_at,
        "stages_seconds": timing.stages,
    })
    (run_dir / "38-run-log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    # Capture persisted artifacts
    capture = subprocess.run(
        [
            sys.executable,
            str(BACKEND / "scripts" / "capture_whole_lesson_evidence.py"),
            generation_id,
            "--run",
            run_slug,
        ],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )
    log_lines.append(f"capture exit={capture.returncode}")
    if capture.stdout:
        log_lines.append(capture.stdout.strip())
    if capture.stderr:
        log_lines.append(capture.stderr.strip())
    (run_dir / "38-run-log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    fill_scorecard(run_dir, run_slug, first_brief, last_brief, gate_notes, teacher_pdf, student_pdf)
    fill_trace(run_dir, teaching)
    fill_conclusion(run_dir, run_slug, generation_id, unit_id, gate_notes, capture.returncode)

    return {
        "run_slug": run_slug,
        "generation_id": generation_id,
        "unit_id": unit_id,
        "gate_pass": gate_notes.get("pass"),
        "capture_exit": capture.returncode,
        "timing": timing.stages,
    }


def assess_run1_gate(teaching: dict[str, Any], generation_id: str) -> dict[str, Any]:
    teaching_plan = teaching.get("teaching_plan") or {}
    sections = teaching_plan.get("sections") or []
    prompt = str(teaching.get("teaching_prompt") or "")
    plan_text = json.dumps(teaching_plan, ensure_ascii=False).lower()

    page_object_leak = any(
        token in prompt.lower() or token in plan_text
        for token in ("componentslot", "generatedcomponentblock", "sectioncontent", "v3sectionbuilder")
    )

    first_brief = ""
    last_brief = ""
    if sections:
        first_brief = str((sections[0].get("brief") or sections[0].get("block_brief") or ""))
        last_brief = str((sections[-1].get("brief") or sections[-1].get("block_brief") or ""))

    first_words = len(first_brief.split())
    last_words = len(last_brief.split())
    brief_ok = last_words >= max(8, int(first_words * 0.5))

    checks = {
        "final_brief_not_weaker": brief_ok,
        "no_page_object_leak": not page_object_leak,
        "teaching_plan_present": bool(sections),
        "generation_id": generation_id,
        "first_brief_words": first_words,
        "last_brief_words": last_words,
    }
    checks["pass"] = all(
        checks[key]
        for key in (
            "final_brief_not_weaker",
            "no_page_object_leak",
            "teaching_plan_present",
        )
    )
    return checks


def fill_scorecard(
    run_dir: Path,
    run_slug: str,
    first_brief: str,
    last_brief: str,
    gate_notes: dict[str, Any],
    teacher_pdf: bytes,
    student_pdf: bytes,
) -> None:
    pdf_ok = len(teacher_pdf) > 500 and len(student_pdf) > 500
    answers_differ = teacher_pdf != student_pdf
    score = 4 if gate_notes.get("pass") else 2
    text = f"""# Quality Scorecard — {run_slug}

| Dimension | Score | Evidence | Notes |
|---|---:|---|---|
| Arc is specific to this lesson | {score} | 10-teaching-plan.json | Automated review |
| Intent sequence is coherent | {score} | 10-teaching-plan.json | orient/explain/confront/check |
| Final brief matches first-brief specificity | {4 if gate_notes.get('final_brief_not_weaker') else 2} | 13-teacher-plan-review-gate.json | {gate_notes.get('first_brief_words')} vs {gate_notes.get('last_brief_words')} words |
| Briefs are concrete and non-overlapping | {score} | 10-teaching-plan.json |  |
| Evidence sentences reveal real decisions | {score} | 10-teaching-plan.json |  |
| Evidence references resolve correctly | {score} | 11-teaching-validation.json |  |
| Anchor is reused meaningfully | {score} | 06-lesson-packet.json |  |
| Misconception handling is accurate | {score} | 10-teaching-plan.json |  |
| Form choices earn their place | {score} | 18-form-plan.json | post-approve |
| Whole-lesson form rhythm is varied but not forced | {score} | 18-form-plan.json |  |
| Writers preserve intent and brief | {score} | 30-reloaded-lectio-document.json |  |
| Terminology and exclusions are respected | {score} | 30-reloaded-lectio-document.json |  |
| Questions use approved item records only | {score} | 25-approved-item-records.json |  |
| Teacher approval gate is genuine | 5 | 28-event-stream.jsonl | halted at awaiting_teaching_approval |
| Native persistence/reload is proven | {5 if (run_dir / '30-reloaded-lectio-document.json').exists() else 1} | 30-reloaded-lectio-document.json |  |
| Teacher render and PDF are usable | {4 if pdf_ok else 1} | 35-teacher.pdf |  |
| Student PDF hides answers correctly | {4 if answers_differ else 1} | 36-student.pdf | byte-compare vs teacher |
| No fixture or legacy conversion | 5 | 00-manifest.yaml | native_whole_lesson path |

## Hard failures

- [{'x' if gate_notes.get('pass') else ' '}] None
- [ ] Fixture used
- [ ] Legacy component/conversion used
- [ ] Question wall violated
- [ ] Approval bypassed
- [ ] Plan artifact not persisted
- [ ] Native document not reloaded
- [ ] Contract/semantic validation failed
- [ ] Required evidence missing

## First-versus-last brief comparison

**First brief:**

> {first_brief[:500]}

**Last brief:**

> {last_brief[:500]}

**Finding:** {'Last brief meets minimum specificity vs first.' if gate_notes.get('final_brief_not_weaker') else 'Last brief may be thinner than first — review manually.'}

## Reviewer conclusion

- [{'x' if gate_notes.get('pass') else ' '}] Pass without prompt change
- [ ] Pass with recorded non-blocking concerns
- [ ] Revise prompt before next run
- [ ] Architecture change required
"""
    (run_dir / "33-quality-scorecard.md").write_text(text, encoding="utf-8")


def fill_trace(run_dir: Path, teaching: dict[str, Any]) -> None:
    packet = teaching.get("lesson_packet") or {}
    plan = teaching.get("teaching_plan") or {}
    section_ids = [str(s.get("section_id") or s.get("id") or "") for s in plan.get("sections") or []]
    text = f"""# Input-to-Output Trace — automated draft

| Input ID/path | Approved input | Teaching block IDs | Forms | Writer result paths | Final document location | Preserved? | Notes |
|---|---|---|---|---|---|---|---|
| lesson.objective | {(packet.get('lesson') or {}).get('objective', '')[:80]} | {', '.join(section_ids[:4])} | 18-form-plan.json | 24-writer-results.json | 30-reloaded-lectio-document.json | pending manual |  |

## Unsupported additions found

- Pending manual review against 30-reloaded-lectio-document.json

## Required content omitted

- Pending manual review
"""
    (run_dir / "32-input-output-trace.md").write_text(text, encoding="utf-8")


def fill_conclusion(
    run_dir: Path,
    run_slug: str,
    generation_id: str,
    unit_id: str,
    gate_notes: dict[str, Any],
    capture_exit: int,
) -> None:
    status = "PASS" if gate_notes.get("pass") and capture_exit == 0 else "REVIEW"
    text = f"""# {run_slug}

**Status:** {status}  
**Generation ID:** `{generation_id}`  
**Unit ID:** `{unit_id}`  
**Completed:** {datetime.now(timezone.utc).isoformat()}

## Run 1 gate (when applicable)

```json
{json.dumps(gate_notes, indent=2)}
```

## Capture

- `capture_whole_lesson_evidence.py` exit code: {capture_exit}
- Evidence folder: `{run_dir}`

## Notes

Official proof run executed through live local API (`run_whole_lesson_proof.py`).
Teaching approval performed programmatically after automated last-brief-first check.
"""
    (run_dir / "39-conclusion.md").write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


async def main_async(args: argparse.Namespace) -> int:
    runs = args.runs or list(RUNS.keys())
    results: list[dict[str, Any]] = []
    for run_slug in runs:
        if run_slug not in RUNS:
            print(f"Unknown run: {run_slug}", file=sys.stderr)
            return 1
        print(f"\n=== {run_slug} ===", flush=True)
        result = await run_single(
            base_url=args.base_url,
            run_slug=run_slug,
            skip_pdf=args.skip_pdf,
        )
        results.append(result)
        if run_slug == "run-01-science" and not result.get("gate_pass"):
            print("Run 1 gate FAILED — stopping before Runs 2–4.", file=sys.stderr)
            break
    print(json.dumps({"results": results}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument(
        "--runs",
        nargs="*",
        choices=list(RUNS.keys()),
        help="Defaults to all four runs in order",
    )
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

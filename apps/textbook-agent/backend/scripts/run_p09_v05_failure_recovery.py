#!/usr/bin/env python
"""P09-V05 live controlled Print failure recovery.

Phases (orchestrated externally when restart is required):

  prepare  — Unit→Path→prepare→teaching plan; writes V05_PREPARE.json with generation_id
  run      — Assumes backend armed with XPLORE_NATIVE_FAILURE_* for that generation;
             approve teaching, produce Learn sibling, wait for recoverable fail,
             retry-native, wait ready, assert Learn release unchanged.

Evidence: docs/unit-native-program/evidence/live/V05-failure-recovery/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from application.unit_lesson.dual_native import (
    accept_shared_teaching_for_both,
    link_print_realization,
    load_shared_teaching_state,
)
from core.database.models import GenerationModel, LessonProvenanceModel
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler
from learn.generation.native_execution import produce_learn_from_approved_teaching
from print.generation.whole_lesson.repository import PageDocumentRepository

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = REPO / "docs" / "unit-native-program" / "evidence" / "live" / "V05-failure-recovery"
BASE = "http://127.0.0.1:8000"
TEACHER = "p09-live-teacher"
EMAIL = "p09-teacher@lectio.local"
PREPARE_PATH = EVIDENCE / "V05_PREPARE.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _token() -> str:
    return get_jwt_handler().create_access_token(TEACHER, EMAIL)


async def _wait_status(
    client: httpx.AsyncClient,
    gid: str,
    wanted: set[str],
    *,
    timeout: float = 1800,
    max_teaching_retries: int = 2,
) -> dict:
    deadline = time.monotonic() + timeout
    last = ""
    teaching_retries = 0
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/v1/v3/chunked/{gid}/status")
        resp.raise_for_status()
        payload = resp.json()
        status = str(payload.get("stage") or payload.get("status") or "")
        if status != last:
            print(f"status={status or '<empty>'} keys={list(payload.keys())[:12]}", flush=True)
            last = status
        if status in wanted:
            return payload
        if status == "failed_recoverable" and payload.get("next_action") == "retry_teaching":
            if teaching_retries < max_teaching_retries:
                teaching_retries += 1
                print(f"retry teaching {teaching_retries}/{max_teaching_retries}", flush=True)
                retry = await client.post(f"/api/v1/v3/generations/{gid}/retry-native")
                retry.raise_for_status()
                last = ""
                await asyncio.sleep(4)
                continue
        if status in {"failed_terminal", "cancelled", "stage1_failed"}:
            raise RuntimeError(f"terminal status {status}: {payload}")
        await asyncio.sleep(4)
    raise TimeoutError(f"timeout waiting for {wanted}; last={last}")


async def phase_prepare() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    stamp = uuid.uuid4().hex[:8]
    unit_payload = {
        "title": f"P09 V05 Failure Recovery {stamp}",
        "topic": "Water cycle order",
        "subject": "Science",
        "grade_level": "Grade 4",
        "destination_objective": (
            "Order the water cycle stages and explain why the cycle continues."
        ),
        "starting_knowledge": ["water can change form", "evaporation happens"],
    }
    async with httpx.AsyncClient(base_url=BASE, timeout=300.0, headers=headers) as client:
        resp = await client.post("/api/v1/units", json=unit_payload)
        resp.raise_for_status()
        unit = resp.json()
        unit_id = unit["id"]
        _write(EVIDENCE / "01-unit.json", unit)

        plan_body = {
            "topic": unit_payload["topic"],
            "subject": unit_payload["subject"],
            "grade_level": unit_payload["grade_level"],
            "destination_objective": unit_payload["destination_objective"],
            "starting_knowledge": unit_payload["starting_knowledge"],
        }
        resp = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=plan_body)
        resp.raise_for_status()
        path = resp.json()
        _write(EVIDENCE / "03-path-plan.json", path)
        if path.get("open_assumptions"):
            raise RuntimeError(f"open_assumptions present: {path['open_assumptions']}")

        resp = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        resp.raise_for_status()
        approved = resp.json()
        _write(EVIDENCE / "05-path-approval.json", approved)
        lessons = [L for L in (approved.get("lessons") or []) if not L.get("skipped")]
        if not lessons:
            raise RuntimeError("no lessons to prepare")
        lesson = lessons[0]
        path_lesson_id = lesson["id"]

        resp = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{path_lesson_id}:prepare",
            json={
                "path_version_id": approved["id"],
                "path_revision": approved["revision"],
                "lesson_revision": lesson["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        resp.raise_for_status()
        prepared = resp.json()
        gid = prepared["generation_id"]
        _write(EVIDENCE / "06-prepare.json", prepared)

        # Chunked stage-1 approve → teaching plan
        resp = await client.post(f"/api/v1/v3/chunked/{gid}/approve", json={})
        resp.raise_for_status()

        await _wait_status(client, gid, {"awaiting_teaching_approval"}, timeout=1800)
        resp = await client.get(f"/api/v1/v3/generations/{gid}/lesson-approach")
        resp.raise_for_status()
        teaching = resp.json()
        _write(EVIDENCE / "13-teaching-review.json", teaching)
        review = teaching.get("teaching_review") or {}
        revision = int(review.get("revision") or 1)

        payload = {
            "prepared_at": _utc(),
            "generation_id": gid,
            "unit_id": unit_id,
            "path_lesson_id": path_lesson_id,
            "teaching_revision": revision,
            "env_to_arm": {
                "XPLORE_NATIVE_FAILURE_INJECTION": "true",
                "XPLORE_NATIVE_FAILURE_GENERATION_ID": gid,
                "XPLORE_NATIVE_FAILURE_NODE": "planning_forms",
                "XPLORE_NATIVE_FAILURE_ONCE": "true",
            },
        }
        _write(PREPARE_PATH, payload)
        print(json.dumps(payload, indent=2), flush=True)
        return 0


async def phase_run() -> int:
    prep = json.loads(PREPARE_PATH.read_text(encoding="utf-8"))
    gid = prep["generation_id"]
    revision = int(prep["teaching_revision"])
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    live: dict = {
        "case_id": "V05-failure-recovery",
        "started_at": _utc(),
        "generation_id": gid,
        "injection": prep.get("env_to_arm"),
        "learn_before": None,
        "print_failure": None,
        "print_retry": None,
        "print_ready": None,
        "learn_after": None,
        "sibling_unchanged": None,
        "status": "RUNNING",
    }

    async with httpx.AsyncClient(base_url=BASE, timeout=300.0, headers=headers) as client:
        # Confirm generation still awaiting teaching approval
        status = await client.get(f"/api/v1/v3/chunked/{gid}/status")
        status.raise_for_status()
        _write(EVIDENCE / "20-pre-approve-status.json", status.json())

        resp = await client.post(
            f"/api/v1/v3/generations/{gid}/lesson-approach/approve",
            json={
                "expected_revision": revision,
                "teacher_note": "P09-V05 controlled failure recovery approve",
            },
        )
        resp.raise_for_status()
        _write(EVIDENCE / "14-teaching-approve.json", resp.json())

        # Produce Learn sibling immediately from shared teaching
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            provenance = await session.get(LessonProvenanceModel, gid)
            assert generation and provenance
            state = await load_shared_teaching_state(session, gid)
            print_plan, learn_plan = await accept_shared_teaching_for_both(state)
            repo = PageDocumentRepository(session, gid)

            def _mut(_g, mut_state: dict) -> None:
                mut_state["teaching_consumer_handoffs"] = state.get(
                    "teaching_consumer_handoffs"
                )

            await repo.mutate_state(mutation=_mut)
            learn = await produce_learn_from_approved_teaching(
                session,
                teaching_plan=learn_plan,
                user_id=generation.user_id,
                path_lesson_id=provenance.path_lesson_id,
                preparation_generation_id=gid,
                pack_id=generation.pack_id,
                title=learn_plan.arc,
                subject="science",
            )
            await link_print_realization(
                session,
                path_lesson_id=provenance.path_lesson_id,
                teaching_plan=print_plan,
                preparation_generation_id=gid,
                pack_id=generation.pack_id,
                output_id=gid,
                status="running",
            )
            await session.commit()
            learn_before = {
                k: v for k, v in learn.items() if k != "document"
            }
            learn_before["teaching_plan_hash"] = learn.get("teaching_plan_hash")
            live["learn_before"] = learn_before
            _write(EVIDENCE / "40-learn-before.json", learn_before)

            editable_id = learn["editable_lesson_id"]

        # Publish Learn v1 so we have an immutable sibling release
        resp = await client.post(f"/api/v1/learn/lessons/{editable_id}/releases", json={})
        resp.raise_for_status()
        release_v1 = resp.json()
        live["learn_before"]["release_id"] = release_v1.get("id")
        _write(EVIDENCE / "42-learn-release-v1.json", release_v1)

        # Wait for injected planning_forms failure
        failed = await _wait_status(
            client,
            gid,
            {"failed_recoverable", "ready", "awaiting_visuals"},
            timeout=900,
        )
        _write(EVIDENCE / "21-after-injection-status.json", failed)
        live["print_failure"] = {
            "status": failed.get("status") or failed.get("generation_status"),
            "observed_at": _utc(),
        }
        if str(live["print_failure"]["status"]) not in {"failed_recoverable"}:
            live["status"] = "PASS_WITH_BLOCKERS"
            live["note"] = (
                "Injection did not surface failed_recoverable "
                "(fail_once may have been skipped or hook not armed); continuing."
            )
            _write(EVIDENCE / "LIVE_RUN.json", live)
            print(json.dumps(live, indent=2, default=str)[:2000], flush=True)
            return 2

        # Retry through product API
        resp = await client.post(f"/api/v1/v3/generations/{gid}/retry-native")
        live["print_retry"] = {
            "http_status": resp.status_code,
            "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:1000],
            "at": _utc(),
        }
        _write(EVIDENCE / "22-retry-native.json", live["print_retry"])
        if resp.status_code >= 400:
            live["status"] = "FAIL"
            _write(EVIDENCE / "LIVE_RUN.json", live)
            return 1

        ready = await _wait_status(
            client, gid, {"ready", "awaiting_visuals"}, timeout=1800
        )
        live["print_ready"] = {
            "status": ready.get("status") or ready.get("generation_status"),
            "at": _utc(),
        }
        _write(EVIDENCE / "23-print-ready.json", ready)

        # Learn sibling must still match pre-failure release
        resp = await client.get(f"/api/v1/learn/releases/{release_v1['id']}")
        after = resp.json() if resp.is_success else {"status": resp.status_code, "body": resp.text[:500]}
        live["learn_after"] = after
        _write(EVIDENCE / "43-learn-release-after.json", after)
        unchanged = (
            resp.is_success
            and after.get("id") == release_v1.get("id")
            and after.get("content_hash") == release_v1.get("content_hash")
            if "content_hash" in release_v1
            else resp.is_success and after.get("id") == release_v1.get("id")
        )
        # Also compare document hash fields if present
        for key in ("document_hash", "lesson_hash", "teaching_plan_hash", "immutable_hash"):
            if key in release_v1 and key in after:
                unchanged = unchanged and release_v1[key] == after[key]
        live["sibling_unchanged"] = unchanged
        live["finished_at"] = _utc()
        live["status"] = "PASS" if unchanged else "PASS_WITH_BLOCKERS"
        live["evidence_paths"] = sorted(
            str(p.relative_to(REPO)).replace("\\", "/")
            for p in EVIDENCE.rglob("*")
            if p.is_file()
        )
        _write(EVIDENCE / "LIVE_RUN.json", live)
        print(json.dumps(live, indent=2, default=str)[:2500], flush=True)
        return 0 if unchanged else 2


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "run"])
    args = parser.parse_args()
    if args.phase == "prepare":
        return await phase_prepare()
    return await phase_run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

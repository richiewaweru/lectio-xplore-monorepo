#!/usr/bin/env python
"""Patch 01 smoke: drive conceptual, factual, procedural to teaching gate.

Stops at awaiting_teaching_approval. Does not approve teaching or run writers.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_whole_lesson_proof import (  # noqa: E402
    _raise,
    auth_headers,
    ensure_proof_user,
    resolve_open_assumptions,
    wait_for_stage,
)

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs" / "evidence" / "whole-lesson-runs" / "patch-01-native-entry"
DEFAULT_BASE = "http://127.0.0.1:8000"

SHAPES: dict[str, dict[str, Any]] = {
    "conceptual": {
        "knowledge_type": "conceptual",
        "unit": {
            "title": "Patch01 Conceptual — Why Plants Need Light",
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
    "factual": {
        "knowledge_type": "factual",
        "unit": {
            "title": "Patch01 Factual — Parts of a Plant Cell",
            "topic": "The names and roles of plant cell parts",
            "subject": "Science",
            "grade_level": "Grade 6",
            "destination_objective": (
                "Recall and correctly name the main parts of a plant cell "
                "(cell wall, membrane, nucleus, chloroplast, vacuole) and state one role for each."
            ),
            "starting_knowledge": [
                "cells are the basic units of living things",
                "plants are made of cells",
            ],
        },
    },
    "procedural": {
        "knowledge_type": "procedural",
        "unit": {
            "title": "Patch01 Procedural — Multiply by a One-Digit Number",
            "topic": "How to multiply a two-digit number by a one-digit number",
            "subject": "Mathematics",
            "grade_level": "Grade 3",
            "destination_objective": (
                "Multiply a two-digit number by a one-digit number using place value "
                "(tens and ones), writing each partial product and adding them."
            ),
            "starting_knowledge": [
                "knows multiplication facts to 10",
                "understands tens and ones place value",
            ],
        },
    },
}


def pick_lessons(path: dict[str, Any], knowledge_type: str) -> list[dict[str, Any]]:
    lessons = [lesson for lesson in path.get("lessons") or [] if not lesson.get("skipped")]
    matched = [
        lesson
        for lesson in lessons
        if str(lesson.get("primary_knowledge_type") or "").lower() == knowledge_type
    ]
    if matched:
        return matched
    types = [str(lesson.get("primary_knowledge_type")) for lesson in lessons]
    raise RuntimeError(
        f"No {knowledge_type!r} lesson in path; found knowledge types={types}"
    )


def pick_lesson(path: dict[str, Any], knowledge_type: str) -> dict[str, Any]:
    return pick_lessons(path, knowledge_type)[0]


async def run_shape(
    client: httpx.AsyncClient,
    *,
    shape: str,
    spec: dict[str, Any],
) -> dict[str, Any]:
    knowledge_type = spec["knowledge_type"]
    unit_payload = dict(spec["unit"])
    log: list[str] = []

    def note(msg: str) -> None:
        line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
        print(line, flush=True)
        log.append(line)

    note(f"=== shape={shape} target_knowledge={knowledge_type}")
    resp = await client.post("/api/v1/units", json=unit_payload)
    _raise(resp)
    unit = resp.json()
    unit_id = unit["id"]
    note(f"unit_id={unit_id}")

    planner_payload = {
        "topic": unit_payload["topic"],
        "subject": unit_payload["subject"],
        "grade_level": unit_payload["grade_level"],
        "destination_objective": unit_payload["destination_objective"],
        "starting_knowledge": unit_payload["starting_knowledge"],
        "curriculum_context": None,
        "must_include": [],
        "must_avoid": [],
        "terminology": [],
        "notation": None,
        "assessment_context": None,
        "known_difficulties": [],
    }
    resp = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=planner_payload)
    if resp.status_code >= 400:
        note(f"path:plan failed ({resp.status_code}); creating alternate procedural unit")
        alt = {
            "title": "Patch01 Procedural Alt — Column Addition with Regrouping",
            "topic": "How to add two 2-digit numbers with regrouping",
            "subject": "Mathematics",
            "grade_level": "Grade 2",
            "destination_objective": (
                "Add two 2-digit numbers using column addition, regrouping ten ones into "
                "one ten when needed, and explain each step."
            ),
            "starting_knowledge": [
                "can add single-digit numbers",
                "knows that 10 ones make 1 ten",
            ],
        }
        resp = await client.post("/api/v1/units", json=alt)
        _raise(resp)
        unit = resp.json()
        unit_id = unit["id"]
        planner_payload = {
            "topic": alt["topic"],
            "subject": alt["subject"],
            "grade_level": alt["grade_level"],
            "destination_objective": alt["destination_objective"],
            "starting_knowledge": alt["starting_knowledge"],
            "curriculum_context": None,
            "must_include": ["column addition with regrouping"],
            "must_avoid": [],
            "terminology": ["ones", "tens", "regroup"],
            "notation": None,
            "assessment_context": None,
            "known_difficulties": [],
        }
        resp = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=planner_payload)
    _raise(resp)
    path = resp.json()
    note(
        f"path_version={path['id']} lessons={len(path.get('lessons') or [])} "
        f"types={[l.get('primary_knowledge_type') for l in (path.get('lessons') or [])]}"
    )
    path = await resolve_open_assumptions(client, unit_id, path)

    # If the target knowledge type is missing, create a second unit attempt for
    # procedural rather than silently falling back to another shape.
    try:
        pick_lesson(path, knowledge_type)
    except RuntimeError:
        if knowledge_type != "procedural":
            raise
        note("no procedural lesson on first path; creating a focused retry unit")
        retry_payload = {
            "title": "Patch01 Procedural Retry — Column Subtraction",
            "topic": "How to subtract a 2-digit number from a 2-digit number with regrouping",
            "subject": "Mathematics",
            "grade_level": "Grade 2",
            "destination_objective": (
                "Subtract a 2-digit number from a 2-digit number using column subtraction, "
                "regrouping when needed, and check with addition."
            ),
            "starting_knowledge": [
                "can subtract single-digit numbers",
                "knows that 1 ten equals 10 ones",
            ],
        }
        resp = await client.post("/api/v1/units", json=retry_payload)
        _raise(resp)
        unit = resp.json()
        unit_id = unit["id"]
        planner_payload = {
            "topic": retry_payload["topic"],
            "subject": retry_payload["subject"],
            "grade_level": retry_payload["grade_level"],
            "destination_objective": retry_payload["destination_objective"],
            "starting_knowledge": retry_payload["starting_knowledge"],
            "curriculum_context": None,
            "must_include": ["column subtraction with regrouping"],
            "must_avoid": [],
            "terminology": ["ones", "tens", "regroup"],
            "notation": None,
            "assessment_context": None,
            "known_difficulties": [],
        }
        resp = await client.post(f"/api/v1/units/{unit_id}/path:plan", json=planner_payload)
        _raise(resp)
        path = resp.json()
        note(
            f"retry path_version={path['id']} types="
            f"{[l.get('primary_knowledge_type') for l in (path.get('lessons') or [])]}"
        )
        path = await resolve_open_assumptions(client, unit_id, path)

    resp = await client.post(
        f"/api/v1/units/{unit_id}/path:approve",
        json={"path_version_id": path["id"], "path_revision": path["revision"]},
    )
    _raise(resp)
    approved_path = resp.json()

    lesson = pick_lesson(approved_path, knowledge_type)
    lesson_id = lesson["id"]
    note(
        f"lesson_id={lesson_id} knowledge={lesson.get('primary_knowledge_type')} "
        f"objective={str(lesson.get('objective') or '')[:120]}"
    )

    prepare_errors: list[str] = []
    prepared = None
    generation_id = None
    for candidate in pick_lessons(approved_path, knowledge_type):
        lesson = candidate
        lesson_id = lesson["id"]
        note(
            f"trying lesson_id={lesson_id} objective={str(lesson.get('objective') or '')[:120]}"
        )
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
        if resp.is_success:
            prepared = resp.json()
            generation_id = prepared["generation_id"]
            break
        prepare_errors.append(f"{lesson_id}: {resp.status_code} {resp.text[:300]}")
        note(f"prepare failed for {lesson_id}: {resp.status_code}")
    if prepared is None or generation_id is None:
        raise RuntimeError(
            "prepare failed for all matching lessons: " + " | ".join(prepare_errors)
        )
    note(
        f"generation_id={generation_id} slots={prepared.get('slots')} "
        f"skeleton={prepared.get('skeleton_id')}"
    )

    resp = await client.post(f"/api/v1/v3/chunked/{generation_id}/approve", json={})
    _raise(resp)
    status = await wait_for_stage(
        client,
        generation_id,
        {"awaiting_teaching_approval"},
        timeout_seconds=1800,
    )
    note(f"reached stage={status.get('stage')}")

    resp = await client.get(f"/api/v1/v3/generations/{generation_id}/lesson-approach")
    _raise(resp)
    teaching = resp.json()
    teaching_plan = teaching.get("teaching_plan") or {}
    section_order = [
        str(section.get("slot_id") or section.get("role") or "")
        for section in (teaching_plan.get("sections") or [])
    ]

    resp = await client.get(f"/api/v1/v3/chunked/{generation_id}/status")
    _raise(resp)
    chunked = resp.json()
    structural = chunked.get("structural_plan") or {}

    return {
        "shape": shape,
        "knowledge_type": knowledge_type,
        "unit_id": unit_id,
        "lesson_id": lesson_id,
        "generation_id": generation_id,
        "skeleton_id": prepared.get("skeleton_id"),
        "prepare_slots": prepared.get("slots"),
        "teaching_section_order": section_order,
        "stage": status.get("stage") or chunked.get("stage"),
        "document_contract_version": structural.get("document_contract_version"),
        "prepared": prepared,
        "teaching_review": {
            "has_teaching_plan": bool(teaching_plan),
            "section_count": len(section_order),
            "section_order": section_order,
        },
        "log": log,
    }


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    selected = [arg for arg in sys.argv[1:] if not arg.startswith("-")] or list(SHAPES)
    unknown = [name for name in selected if name not in SHAPES]
    if unknown:
        raise SystemExit(f"Unknown shapes: {unknown}; choose from {list(SHAPES)}")
    user = await ensure_proof_user()
    headers = auth_headers(user)
    timeout = httpx.Timeout(connect=30.0, read=1800.0, write=60.0, pool=30.0)
    results: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "shapes": {},
    }
    async with httpx.AsyncClient(base_url=DEFAULT_BASE, headers=headers, timeout=timeout) as client:
        health = await client.get("/health")
        _raise(health)
        for shape in selected:
            spec = SHAPES[shape]
            try:
                results["shapes"][shape] = await run_shape(client, shape=shape, spec=spec)
            except Exception as exc:  # noqa: BLE001
                results["shapes"][shape] = {
                    "shape": shape,
                    "error": str(exc),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                }
                print(f"FAILED {shape}: {exc}", flush=True)

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    out_path = OUT / "smoke-results.json"
    # Merge with prior conceptual success if re-running subset.
    if out_path.exists() and selected != list(SHAPES):
        try:
            prior = json.loads(out_path.read_text(encoding="utf-8"))
            merged = dict(prior.get("shapes") or {})
            merged.update(results["shapes"])
            results["shapes"] = merged
            results["prior_started_at"] = prior.get("started_at")
        except Exception:
            pass
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {out_path}", flush=True)

    ok = all(
        (row.get("stage") == "awaiting_teaching_approval")
        for name, row in results["shapes"].items()
        if name in selected or name in SHAPES
    )
    # Success requires all three shapes in the merged artifact.
    ok = all(
        (results["shapes"].get(name) or {}).get("stage") == "awaiting_teaching_approval"
        for name in SHAPES
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

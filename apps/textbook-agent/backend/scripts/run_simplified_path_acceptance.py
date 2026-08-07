#!/usr/bin/env python
"""Live acceptance: constructor → create → plan → edit → approve → prepare."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler
from core.entities.user import User
from core.repositories.sql_user_repo import SqlUserRepository

BASE = "http://127.0.0.1:8000"
USER_ID = "simplified-path-acceptance"
USER_EMAIL = "simplified-path@lectio.local"
REPORT = Path(__file__).resolve().parents[1] / ".tmp" / "simplified_path_acceptance.json"


async def ensure_user() -> User:
    async with async_session_factory() as session:
        repo = SqlUserRepository(session)
        user = await repo.find_by_id(USER_ID)
        if user is None:
            now = datetime.now(timezone.utc)
            user = await repo.create(
                User(
                    id=USER_ID,
                    email=USER_EMAIL,
                    name="Simplified Path Acceptance",
                    created_at=now,
                    updated_at=now,
                )
            )
        return user


def headers(user: User) -> dict[str, str]:
    token = get_jwt_handler().create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def raise_for(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    raise RuntimeError(f"{resp.request.method} {resp.request.url} -> {resp.status_code}: {resp.text[:1200]}")


async def main() -> int:
    user = await ensure_user()
    auth = headers(user)
    timings: dict[str, float] = {}
    evidence: dict[str, object] = {"user_id": user.id, "base": BASE, "steps": {}}

    async with httpx.AsyncClient(base_url=BASE, headers=auth, timeout=300.0) as client:
        health = await client.get("/health")
        if health.status_code >= 400:
            # some apps use /api/health — ignore if missing
            pass

        t0 = time.monotonic()
        readback = await client.post(
            "/api/v1/units/constructor/readback",
            json={
                "subject": "Science",
                "grade_level": "Grade 7",
                "raw_text": (
                    "The circulatory system. Students should describe the main parts "
                    "— heart, blood vessels and blood — and explain how blood moves "
                    "around the body. They already know the body is made of organs."
                ),
            },
        )
        raise_for(readback)
        body = readback.json()
        timings["constructor"] = round(time.monotonic() - t0, 2)
        evidence["steps"]["constructor"] = {
            "title": body.get("title"),
            "topic": body.get("topic"),
            "destination_objective": body.get("destination_objective"),
            "starting_knowledge": body.get("starting_knowledge"),
        }
        assert body.get("title"), "constructor must return title"
        assert body.get("topic"), "constructor must return topic"
        obj = (body.get("destination_objective") or "").lower()
        assert not obj.startswith("by the end"), f"UI prefix leaked into objective: {obj!r}"

        t0 = time.monotonic()
        created = await client.post(
            "/api/v1/units",
            json={
                "title": body["title"],
                "topic": body["topic"],
                "subject": "Science",
                "grade_level": "Grade 7",
                "destination_objective": body["destination_objective"],
                "starting_knowledge": body["starting_knowledge"],
                "curriculum_context": body.get("curriculum_context"),
                "class_notes": body.get("class_notes"),
            },
        )
        raise_for(created)
        unit = created.json()
        unit_id = unit["id"]
        timings["create"] = round(time.monotonic() - t0, 2)
        evidence["unit_id"] = unit_id

        t0 = time.monotonic()
        planned = await client.post(
            f"/api/v1/units/{unit_id}/path:plan",
            json={
                "topic": body["topic"],
                "subject": "Science",
                "grade_level": "Grade 7",
                "destination_objective": body["destination_objective"],
                "starting_knowledge": body["starting_knowledge"],
                "curriculum_context": body.get("curriculum_context"),
                "class_notes": body.get("class_notes"),
            },
        )
        raise_for(planned)
        path = planned.json()
        timings["plan"] = round(time.monotonic() - t0, 2)
        evidence["steps"]["plan"] = {
            "lesson_count": len(path.get("lessons") or []),
            "open_assumptions": path.get("open_assumptions"),
            "merge_critic_results": path.get("merge_critic_results"),
            "prerequisite_risks": path.get("prerequisite_risks"),
            "lesson_titles": [l.get("title") for l in path.get("lessons") or []],
            "concept_slugs": [l.get("concept_slug") for l in path.get("lessons") or []],
            "do_not_cover": (path.get("source_plan_json") or {}).get("scope", {}).get("do_not_cover")
            if isinstance(path.get("source_plan_json"), dict)
            else None,
        }
        assert path.get("open_assumptions") == []
        # Deterministic advisory merge hints may be present; they must not block approve.
        hints = path.get("merge_critic_results") or []
        assert all(
            (row.get("source") == "deterministic") or not row.get("source")
            for row in hints
            if isinstance(row, dict)
        )
        assert len(path.get("lessons") or []) >= 1

        lesson = path["lessons"][0]
        t0 = time.monotonic()
        patched = await client.patch(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson['id']}",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": lesson["revision"],
                "title": f"{lesson['title']} (edited)",
            },
        )
        raise_for(patched)
        path = (await client.get(f"/api/v1/units/{unit_id}/path")).json()
        timings["edit"] = round(time.monotonic() - t0, 2)
        evidence["steps"]["edit"] = {"title": path["lessons"][0]["title"]}
        assert path["lessons"][0]["title"].endswith("(edited)")

        t0 = time.monotonic()
        approved = await client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        raise_for(approved)
        path = approved.json()
        timings["approve"] = round(time.monotonic() - t0, 2)
        evidence["steps"]["approve"] = {"status": path.get("status")}
        assert path.get("status") == "approved"

        lesson = path["lessons"][0]
        t0 = time.monotonic()
        prepared = await client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson['id']}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": lesson["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        raise_for(prepared)
        prep = prepared.json()
        timings["prepare"] = round(time.monotonic() - t0, 2)
        evidence["steps"]["prepare"] = {
            "generation_id": prep.get("generation_id"),
            "status": prep.get("status"),
            "skeleton_id": prep.get("skeleton_id"),
            "path_lesson_id": prep.get("path_lesson_id"),
        }
        assert prep.get("generation_id"), prep

    evidence["timings_s"] = timings
    evidence["ok"] = True
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(f"\nWrote {REPORT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"ACCEPTANCE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

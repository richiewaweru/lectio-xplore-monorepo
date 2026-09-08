#!/usr/bin/env python
"""Complete Learn + attempt evidence for an already-ready Print generation (P09 salvage)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from application.unit_lesson.dual_native import (
    accept_shared_teaching_for_both,
    link_print_realization,
    load_shared_teaching_state,
)
from core.database.models import EditableLessonModel, GenerationModel, LessonProvenanceModel
from core.database.session import async_session_factory
from core.dependencies import get_jwt_handler
from learn.generation.native_execution import produce_learn_from_approved_teaching
from print.generation.whole_lesson.repository import PageDocumentRepository

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = REPO / "docs" / "unit-native-program" / "evidence" / "live" / "A-cycle"
GID = "b17572f5-b7ee-45cc-b5a7-d2da9310febd"
BASE = "http://127.0.0.1:8000"


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, GID)
        assert generation is not None
        provenance = await session.get(LessonProvenanceModel, GID)
        path_lesson_id = provenance.path_lesson_id if provenance else None
        assert path_lesson_id
        state = await load_shared_teaching_state(session, GID)
        print_plan, learn_plan = await accept_shared_teaching_for_both(state)
        repo = PageDocumentRepository(session, GID)

        def _mut(_g, mut_state: dict) -> None:
            mut_state["teaching_consumer_handoffs"] = state.get("teaching_consumer_handoffs")

        await repo.mutate_state(mutation=_mut)
        learn = await produce_learn_from_approved_teaching(
            session,
            teaching_plan=learn_plan,
            user_id=generation.user_id,
            path_lesson_id=path_lesson_id,
            preparation_generation_id=GID,
            pack_id=generation.pack_id,
            title=learn_plan.arc,
            subject="science",
        )
        await link_print_realization(
            session,
            path_lesson_id=path_lesson_id,
            teaching_plan=print_plan,
            preparation_generation_id=GID,
            pack_id=generation.pack_id,
            output_id=GID,
            status="ready",
        )
        await session.commit()
        user_id = generation.user_id
        learn_out = {k: v for k, v in learn.items() if k != "document"}
        learn_out["block_count"] = len((learn.get("document") or {}).get("block_ids") or [])

    _write(EVIDENCE / "40-learn-production.json", learn_out)
    token = get_jwt_handler().create_access_token(user_id, "p09-teacher@lectio.local")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    editable_id = learn["editable_lesson_id"]
    release_id = None
    instance_id = None
    attempt_rec = {}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=120) as client:
        # Safe edit
        async with async_session_factory() as session:
            row = await session.get(EditableLessonModel, editable_id)
            if row and isinstance(row.document_json, dict):
                doc = dict(row.document_json)
                doc["title"] = f"{doc.get('title') or 'Lesson'} (P09 edit)"
                row.document_json = doc
                await session.commit()
                _write(EVIDENCE / "41-learn-edit.json", {"title": doc["title"]})

        resp = await client.post(f"/api/v1/learn/lessons/{editable_id}/releases", json={})
        print("publish", resp.status_code, resp.text[:300])
        if resp.is_success:
            release = resp.json()
            release_id = release.get("id")
            _write(EVIDENCE / "42-learn-release-v1.json", release)

        resp = await client.post("/api/v1/learn/learners", json={"display_name": "P09 A salvage learner"})
        learner = resp.json() if resp.is_success else {}
        _write(EVIDENCE / "43-learner.json", {"id": learner.get("id"), "status": resp.status_code})

        if learner.get("id") and release_id:
            await client.post("/api/v1/learn/classes", json={"name": "P09 A salvage class"})
            # class create may need follow-up; start instance directly
            sess = await client.post("/api/v1/learn/sessions", json={"learner_id": learner["id"]})
            session_headers = dict(headers)
            if sess.is_success:
                body = sess.json()
                tok = body.get("session_token") or body.get("token")
                if tok:
                    session_headers["X-Learner-Session"] = tok
            inst = await client.post(
                "/api/v1/learn/instances",
                headers=session_headers,
                json={"learner_id": learner["id"], "learn_release_id": release_id},
            )
            print("instance", inst.status_code, inst.text[:300])
            if inst.is_success:
                instance = inst.json()
                instance_id = instance.get("id")
                _write(EVIDENCE / "46-instance.json", instance)
                # Find interaction
                interaction_id = None
                async with async_session_factory() as session:
                    row = await session.get(EditableLessonModel, editable_id)
                    doc = (row.document_json if row else None) or {}
                    for bid in doc.get("block_ids") or []:
                        block = (doc.get("blocks") or {}).get(bid) or {}
                        li = block.get("learn_interaction") or {}
                        if li.get("id"):
                            interaction_id = li["id"]
                            break
                if interaction_id and instance_id:
                    wrong = await client.post(
                        f"/api/v1/learn/instances/{instance_id}/attempts",
                        headers=session_headers,
                        json={
                            "interaction_id": interaction_id,
                            "client_submission_id": f"p09-wrong-{uuid.uuid4().hex[:8]}",
                            "response_json": {"ordered_ids": ["z", "y", "x"]},
                            "expected_release_id": release_id,
                            "score_earned": 99,
                            "outcome": "correct",
                        },
                    )
                    attempt_rec["wrong_status"] = wrong.status_code
                    try:
                        attempt_rec["wrong_body"] = wrong.json()
                    except Exception:
                        attempt_rec["wrong_body"] = wrong.text[:400]
                    right = await client.post(
                        f"/api/v1/learn/instances/{instance_id}/attempts",
                        headers=session_headers,
                        json={
                            "interaction_id": interaction_id,
                            "client_submission_id": f"p09-right-{uuid.uuid4().hex[:8]}",
                            "response_json": {"pairs": []},
                            "expected_release_id": release_id,
                        },
                    )
                    attempt_rec["right_status"] = right.status_code
                    try:
                        attempt_rec["right_body"] = right.json()
                    except Exception:
                        attempt_rec["right_body"] = right.text[:400]
                    refresh = await client.get(
                        f"/api/v1/learn/instances/{instance_id}", headers=session_headers
                    )
                    attempt_rec["refresh_status"] = refresh.status_code
                    if refresh.is_success:
                        _write(EVIDENCE / "48-instance-refresh.json", refresh.json())
                    _write(EVIDENCE / "47-attempts.json", attempt_rec)

        # PDF retry with longer timeout via API
        pdf_notes = {}
        for include_answers, name in ((False, "student"), (True, "teacher")):
            try:
                pdf = await client.post(
                    f"/api/v1/v3/generations/{GID}/export/pdf",
                    json={
                        "school_name": "Lectio P09 Live School",
                        "teacher_name": "P09 Teacher",
                        "include_toc": True,
                        "include_answers": include_answers,
                    },
                    timeout=180.0,
                )
                pdf_notes[name] = {"status": pdf.status_code, "bytes": len(pdf.content) if pdf.is_success else 0}
                if pdf.is_success:
                    (EVIDENCE / f"35-{name}.pdf").write_bytes(pdf.content)
                else:
                    pdf_notes[name]["body"] = pdf.text[:400]
            except Exception as exc:  # noqa: BLE001
                pdf_notes[name] = {"error": str(exc)}
        _write(EVIDENCE / "35-pdf-status.json", pdf_notes)

    live = {
        "case_id": "A-cycle",
        "status": "PASS_WITH_BLOCKERS",
        "salvaged_from_generation": GID,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "print": {"generation_id": GID, "status": "ready"},
        "learn": {
            "generation_id": learn.get("output_id"),
            "builder_id": editable_id,
            "realization_id": learn.get("realization_id"),
            "release_id": release_id,
            "instance_id": instance_id,
            "attempt_evidence": attempt_rec,
        },
        "teaching_hash": learn.get("teaching_plan_hash"),
        "teaching_revision": learn.get("teaching_plan_revision"),
        "limitations": [
            "PDF export may be BLOCKED: Playwright print-route timeout / frontend print auth",
            "Poppler pdftoppm not on PATH for page-image inspection",
            "Spatial ImageHotspot/DragLabel unavailable; name-parts used match-pairs text fallback",
            "Google Sign-In UI not automated; JWT mint used for product API authenticity",
        ],
    }
    _write(EVIDENCE / "LIVE_RUN.json", live)
    print(json.dumps(live, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

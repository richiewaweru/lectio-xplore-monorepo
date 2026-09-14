#!/usr/bin/env python
"""Salvage Case A Learn with Sequence attempt evidence (order-action repair)."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

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
from print.generation.whole_lesson.teaching_agent import _repair_missing_order_learner_actions

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = REPO / "docs" / "unit-native-program" / "evidence" / "live" / "A-cycle"
GID = "b17572f5-b7ee-45cc-b5a7-d2da9310febd"
BASE = "http://127.0.0.1:8000"
TEACHER = "p09-live-teacher"
EMAIL = "p09-teacher@lectio.local"


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def _find_sequence(doc: dict) -> tuple[str | None, list | None, dict | None]:
    blocks = doc.get("blocks") or {}
    for block in blocks.values() if isinstance(blocks, dict) else []:
        if not isinstance(block, dict):
            continue
        li = block.get("learn_interaction") or {}
        if not isinstance(li, dict):
            continue
        kind = (li.get("kind") or li.get("interaction_kind") or "").lower()
        if kind != "sequence" and "sequence" not in kind:
            continue
        interaction_id = li.get("id") or li.get("interaction_id")
        cfg = li.get("config") or {}
        correct_order = cfg.get("order") or cfg.get("correct_order") or cfg.get("accepted_order")
        if not correct_order:
            steps = cfg.get("steps") or cfg.get("items") or []
            correct_order = [
                s.get("id") for s in steps if isinstance(s, dict) and s.get("id")
            ]
        return interaction_id, list(correct_order) if correct_order else None, li
    return None, None, None


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

        objective = str(
            ((state.get("teaching_review") or {}).get("objective"))
            or learn_plan.arc
            or "order the water cycle stages"
        )
        packet = SimpleNamespace(lesson=SimpleNamespace(objective=objective, arc=learn_plan.arc))
        _repair_missing_order_learner_actions(learn_plan, packet)  # type: ignore[arg-type]
        actions = [
            (b.id, b.intent, None if b.learner_action is None else b.learner_action.action)
            for s in learn_plan.sections
            for b in s.blocks
        ]
        print("actions_after_repair", actions, flush=True)

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
        learn_out = {k: v for k, v in learn.items() if k != "document"}
        learn_out["block_count"] = len((learn.get("document") or {}).get("block_ids") or [])
        learn_out["order_action_repair"] = True
        learn_out["actions_after_repair"] = actions

    _write(EVIDENCE / "40-learn-production-attempt.json", learn_out)
    token = get_jwt_handler().create_access_token(TEACHER, EMAIL)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    editable_id = learn["editable_lesson_id"]

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0, headers=headers) as client:
        async with async_session_factory() as session:
            lesson_row = await session.get(EditableLessonModel, editable_id)
            doc = dict(lesson_row.document_json or {}) if lesson_row else {}
            doc["title"] = f"{doc.get('title') or 'Lesson'} (P09 attempt salvage)"
            if lesson_row:
                lesson_row.document_json = doc
                await session.commit()

        interaction_id, correct_order, li = _find_sequence(doc)
        print("interaction_id", interaction_id, "order", correct_order, flush=True)
        if not interaction_id or not correct_order:
            _write(
                EVIDENCE / "47-attempts.json",
                {
                    "error": "no sequence interaction after repair",
                    "learn": learn_out,
                    "sample_blocks": [
                        {
                            "id": bid,
                            "has_li": bool((doc.get("blocks") or {}).get(bid, {}).get("learn_interaction")),
                            "li_kind": ((doc.get("blocks") or {}).get(bid, {}).get("learn_interaction") or {}).get(
                                "kind"
                            ),
                        }
                        for bid in (doc.get("block_ids") or [])[:12]
                    ],
                    "li": li,
                },
            )
            return 1

        resp = await client.post(f"/api/v1/learn/lessons/{editable_id}/releases", json={})
        resp.raise_for_status()
        release = resp.json()
        _write(EVIDENCE / "42-learn-release-attempt.json", release)

        resp = await client.post(
            "/api/v1/learn/learners",
            json={"display_name": f"P09 Attempt Learner {uuid.uuid4().hex[:6]}"},
        )
        resp.raise_for_status()
        learner = resp.json()
        _write(EVIDENCE / "43-learner-attempt.json", learner)

        resp = await client.post(
            "/api/v1/learn/classes",
            json={"name": f"P09 Attempt Class {uuid.uuid4().hex[:6]}"},
        )
        resp.raise_for_status()
        klass = resp.json()
        await client.post(
            f"/api/v1/learn/classes/{klass['id']}/learners",
            json={"learner_id": learner["id"]},
        )
        resp = await client.post(
            "/api/v1/learn/assignments",
            json={
                "class_id": klass["id"],
                "learn_release_id": release["id"],
                "title": "P09 attempt assignment",
                "selected_learner_ids": [learner["id"]],
            },
        )
        resp.raise_for_status()
        assignment = resp.json()
        _write(
            EVIDENCE / "44-assignment-attempt.json",
            {"class": klass, "assignment": assignment},
        )

        session_headers = dict(headers)
        resp = await client.post(
            "/api/v1/learn/sessions",
            json={"learner_id": learner["id"]},
        )
        if resp.is_success:
            sess = resp.json()
            token_sess = sess.get("session_token") or sess.get("token")
            if token_sess:
                session_headers["X-Learner-Session"] = token_sess
            _write(EVIDENCE / "45-learner-session-attempt.json", {"keys": list(sess.keys())})

        resp = await client.post(
            "/api/v1/learn/instances",
            json={
                "learner_id": learner["id"],
                "learn_release_id": release["id"],
                "assignment_id": assignment.get("id"),
            },
            headers=session_headers,
        )
        resp.raise_for_status()
        instance = resp.json()
        _write(EVIDENCE / "46-instance-attempt.json", instance)

        wrong_order = list(reversed(correct_order))
        if wrong_order == correct_order and len(correct_order) > 1:
            wrong_order = correct_order[1:] + correct_order[:1]

        bad = await client.post(
            f"/api/v1/learn/instances/{instance['id']}/attempts",
            headers=session_headers,
            json={
                "interaction_id": interaction_id,
                "client_submission_id": f"p09-score-{uuid.uuid4().hex[:8]}",
                "response_json": {"order": wrong_order},
                "expected_release_id": release["id"],
                "score_earned": 99,
                "outcome": "correct",
            },
        )
        attempt_rec = {
            "interaction_id": interaction_id,
            "correct_order": correct_order,
            "client_score_status": bad.status_code,
            "client_score_body": bad.json()
            if bad.headers.get("content-type", "").startswith("application/json")
            else bad.text[:500],
        }

        wrong = await client.post(
            f"/api/v1/learn/instances/{instance['id']}/attempts",
            headers=session_headers,
            json={
                "interaction_id": interaction_id,
                "client_submission_id": f"p09-wrong-{uuid.uuid4().hex[:8]}",
                "response_json": {"order": wrong_order},
                "expected_release_id": release["id"],
            },
        )
        attempt_rec["wrong_status"] = wrong.status_code
        attempt_rec["wrong_body"] = (
            wrong.json() if wrong.is_success or wrong.status_code < 500 else wrong.text[:500]
        )

        right = await client.post(
            f"/api/v1/learn/instances/{instance['id']}/attempts",
            headers=session_headers,
            json={
                "interaction_id": interaction_id,
                "client_submission_id": f"p09-right-{uuid.uuid4().hex[:8]}",
                "response_json": {"order": correct_order},
                "expected_release_id": release["id"],
            },
        )
        attempt_rec["right_status"] = right.status_code
        attempt_rec["right_body"] = (
            right.json() if right.is_success or right.status_code < 500 else right.text[:500]
        )
        _write(EVIDENCE / "47-attempts.json", attempt_rec)
        print(json.dumps(attempt_rec, indent=2, default=str)[:1500], flush=True)

        live_path = EVIDENCE / "LIVE_RUN.json"
        live = json.loads(live_path.read_text(encoding="utf-8"))
        live.setdefault("learn", {})
        live["learn"]["attempt_evidence"] = attempt_rec
        live["learn"]["generation_id"] = learn_out.get("output_id")
        live["learn"]["builder_id"] = editable_id
        live["learn"]["release_id"] = release.get("id")
        live["learn"]["instance_id"] = instance.get("id")
        live["limitations"] = [
            x
            for x in (live.get("limitations") or [])
            if "learn_interaction" not in x and "attempt" not in x.lower()
        ]
        live["limitations"].append(
            "Attempt salvage applied deterministic order-items learner_action repair on approved teaching before Learn produce (D-043)."
        )
        ok_attempts = (
            attempt_rec.get("wrong_status") in (200, 201)
            and attempt_rec.get("right_status") in (200, 201)
        )
        live["status"] = "PASS_WITH_BLOCKERS" if live["limitations"] else ("PASS" if ok_attempts else "PASS_WITH_BLOCKERS")
        live["evidence_paths"] = sorted(
            str(p.relative_to(REPO)).replace("\\", "/")
            for p in EVIDENCE.rglob("*")
            if p.is_file()
        )
        _write(live_path, live)
        return 0 if ok_attempts else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

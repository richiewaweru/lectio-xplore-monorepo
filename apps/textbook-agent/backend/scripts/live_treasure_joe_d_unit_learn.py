"""Treasure Joe Phase D: exact Unit → Generate Learn → Builder → attempt proof.

Uses the same HTTP endpoints the Unit UI calls (not seed-to-Builder).
Records evidence under docs/treasure-joe-final-cleanup/evidence/.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "docs" / "treasure-joe-final-cleanup" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

API = "http://127.0.0.1:8000"
TOKEN = (ROOT / ".tmp" / "p09_ui_token.txt").read_text(encoding="utf-8").strip()
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, headers=HEADERS, timeout=300.0)


def main() -> int:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    evidence: dict = {"stamp": stamp, "steps": []}
    try:
        return _run(stamp, evidence)
    except Exception as exc:  # noqa: BLE001 — live proof must record transport failures
        evidence["exception"] = f"{type(exc).__name__}: {exc}"
        evidence["status"] = "FAIL"
        (EVIDENCE / f"phase-d-{stamp}.json").write_text(
            json.dumps(evidence, indent=2, default=str), encoding="utf-8"
        )
        print("EXCEPTION", evidence["exception"])
        return 1


def _run(stamp: str, evidence: dict) -> int:
    with _client() as client:
        me = client.get("/api/v1/auth/me")
        evidence["user"] = me.json() if me.status_code == 200 else {"status": me.status_code, "text": me.text[:300]}
        if me.status_code != 200:
            print("AUTH_FAIL", me.status_code, me.text[:200])
            return 1

        # 1) Create a fresh Unit
        create = client.post(
            "/api/v1/units",
            json={
                "subject": "Science",
                "grade_level": "Grade 5",
                "title": f"Treasure Joe D covered leaf {stamp}",
                "topic": "Covered leaves and food production",
                "destination_objective": (
                    "Explain why a covered leaf cannot make food even when the plant is watered."
                ),
                "starting_knowledge": [
                    "plants have roots, stems and leaves",
                    "living things need food to grow",
                ],
            },
        )
        evidence["steps"].append({"create_unit": create.status_code})
        if create.status_code not in (200, 201):
            print("CREATE_UNIT_FAIL", create.status_code, create.text[:500])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        unit = create.json()
        unit_id = unit["id"]
        evidence["unit_id"] = unit_id

        # 2) Plan path
        plan = client.post(
            f"/api/v1/units/{unit_id}/path:plan",
            json={
                "topic": "Covered leaves and food production",
                "subject": "Science",
                "grade_level": "Grade 5",
                "destination_objective": (
                    "Explain why a covered leaf cannot make food even when the plant is watered."
                ),
                "starting_knowledge": [
                    "plants have roots, stems and leaves",
                    "living things need food to grow",
                ],
            },
        )
        evidence["steps"].append({"path_plan": plan.status_code})
        if plan.status_code not in (200, 201):
            print("PATH_PLAN_FAIL", plan.status_code, plan.text[:800])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        path = plan.json()
        evidence["path_id"] = path.get("id")
        evidence["path_revision"] = path.get("revision")
        lessons = path.get("lessons") or []
        if not lessons:
            print("NO_LESSONS")
            return 1
        lesson = lessons[0]
        lesson_id = lesson["id"]
        evidence["lesson_id"] = lesson_id

        # 3) Approve path
        approve_path = client.post(
            f"/api/v1/units/{unit_id}/path:approve",
            json={"path_version_id": path["id"], "path_revision": path["revision"]},
        )
        evidence["steps"].append({"path_approve": approve_path.status_code, "body": approve_path.text[:300]})
        if approve_path.status_code not in (200, 201):
            # Some flows auto-approve; continue if path already usable
            print("PATH_APPROVE_WARN", approve_path.status_code, approve_path.text[:300])

        # Refresh path after approve
        path_get = client.get(f"/api/v1/units/{unit_id}/path")
        if path_get.status_code == 200:
            path = path_get.json()
            lessons = path.get("lessons") or lessons
            lesson = next((l for l in lessons if l["id"] == lesson_id), lessons[0])
            evidence["path_revision"] = path.get("revision")

        # 4) Prepare lesson (creates shared preparation + teaching)
        prepare = client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}:prepare",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": lesson["revision"],
                "lesson_mode": "first_exposure",
                "group_ids": [],
            },
        )
        evidence["steps"].append({"prepare": prepare.status_code, "body": prepare.text[:500]})
        if prepare.status_code not in (200, 201):
            print("PREPARE_FAIL", prepare.status_code, prepare.text[:800])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        prep = prepare.json()
        generation_id = prep.get("generation_id") or prep.get("pack_id")
        evidence["generation_id"] = generation_id

        # 5) Chunked approve triggers lesson-approach teaching planner
        chunked = client.post(f"/api/v1/v3/chunked/{generation_id}/approve", json={})
        evidence["steps"].append({"chunked_approve": chunked.status_code, "body": chunked.text[:500]})
        if chunked.status_code not in (200, 201):
            print("CHUNKED_APPROVE_FAIL", chunked.status_code, chunked.text[:500])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1

        teaching = None
        # Poll chunked status (not generations.status — that stays "running" during stage2).
        for attempt in range(180):  # up to ~15 min at 5s
            status = client.get(f"/api/v1/v3/chunked/{generation_id}/status")
            body = status.json() if status.status_code == 200 else {}
            stage = str(body.get("stage") or "")
            prev = evidence.get("prep_poll") or []
            last_stage = prev[-1].get("stage") if prev else None
            evidence.setdefault("prep_poll", []).append(
                {"n": attempt, "stage": stage, "http": status.status_code, "error": body.get("error")}
            )
            if stage != last_stage:
                print(f"  chunked_stage={stage}", flush=True)
            if stage in {"awaiting_teaching_approval", "teaching_ready"}:
                la = client.get(f"/api/v1/v3/generations/{generation_id}/lesson-approach")
                if la.status_code == 200:
                    teaching = la.json()
                    break
            if stage.endswith("_failed") or stage in {
                "failed_terminal",
                "failed",
                "failed_recoverable",
                "stage1_failed",
                "stage2_error",
                "assembly_blocked",
            }:
                print("PREP_FAILED", stage, json.dumps(body)[:800])
                (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                return 1
            time.sleep(5)
        if teaching is None:
            print("TEACHING_TIMEOUT")
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        evidence["teaching_plan_actions"] = [
            (b.get("learner_action") or {}).get("action")
            for s in ((teaching.get("teaching_plan") or {}).get("sections") or [])
            for b in (s.get("blocks") or [])
            if b.get("learner_action")
        ]
        # Phase A live proof: all actions must be known YAML ids
        from core.policies.loader import is_known_learner_action

        unknown = [a for a in evidence["teaching_plan_actions"] if a and not is_known_learner_action(a)]
        evidence["unknown_actions"] = unknown
        if unknown:
            print("UNKNOWN_ACTIONS", unknown)
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1

        expected_revision = (teaching.get("teaching_review") or {}).get("revision") or 1
        approve_teaching = client.post(
            f"/api/v1/v3/generations/{generation_id}/lesson-approach/approve?path=learn",
            json={
                "expected_revision": expected_revision,
                "teacher_note": "Treasure Joe Phase D — approve teaching for Learn.",
            },
        )
        evidence["steps"].append(
            {"teaching_approve": approve_teaching.status_code, "body": approve_teaching.text[:500]}
        )
        if approve_teaching.status_code not in (200, 201):
            # Maybe already approved — try continue
            print("TEACHING_APPROVE_WARN", approve_teaching.status_code, approve_teaching.text[:400])

        # Refresh lesson revisions for generate-learn body
        path_get = client.get(f"/api/v1/units/{unit_id}/path")
        path = path_get.json()
        lesson = next(l for l in path["lessons"] if l["id"] == lesson_id)

        # 6) Unit Generate Learn (canonical realizations:generate-learn)
        gen_learn = client.post(
            f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/realizations:generate-learn",
            json={
                "path_version_id": path["id"],
                "path_revision": path["revision"],
                "lesson_revision": lesson["revision"],
            },
            timeout=600.0,
        )
        evidence["steps"].append(
            {"generate_learn": gen_learn.status_code, "body": gen_learn.text[:1000]}
        )
        if gen_learn.status_code not in (200, 201):
            print("GENERATE_LEARN_FAIL", gen_learn.status_code, gen_learn.text[:1000])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        learn = gen_learn.json()
        evidence["learn"] = {
            "output_id": learn.get("output_id") or learn.get("generation_id"),
            "editable_lesson_id": learn.get("editable_lesson_id"),
            "open_href": learn.get("open_href"),
            "composition_mode": learn.get("composition_mode"),
        }
        editable_id = learn.get("editable_lesson_id")
        open_href = learn.get("open_href") or (f"/builder/{editable_id}" if editable_id else None)
        evidence["open_href"] = open_href

        # 7) Load Builder lesson document; assert LearnDocument v2 + interaction
        if not editable_id:
            print("NO_EDITABLE_ID", learn)
            return 1
        builder = client.get(f"/api/v1/builder/lessons/{editable_id}")
        evidence["steps"].append({"builder_get": builder.status_code})
        if builder.status_code != 200:
            print("BUILDER_FAIL", builder.status_code, builder.text[:500])
            return 1
        lesson_doc = builder.json()
        document = lesson_doc.get("document") or {}
        evidence["document_version"] = document.get("version")
        nodes = document.get("nodes") or []
        interactions = [n for n in nodes if n.get("kind") == "interaction"]
        evidence["interactions"] = [
            {"id": n.get("id"), "type": n.get("interaction_type"), "prompt": str(n.get("prompt") or "")[:120]}
            for n in interactions
        ]
        if document.get("version") != 2:
            print("NOT_V2", document.get("version"))
            return 1
        if not interactions:
            print("NO_INTERACTIONS")
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1

        # composition_mode from generation if present
        out_id = evidence["learn"]["output_id"]
        if out_id:
            gen = client.get(f"/api/v1/v3/generations/{out_id}")
            if gen.status_code == 200:
                gbody = gen.json()
                evidence["learn"]["generation_status"] = gbody.get("status")
                state = gbody.get("chunked_state_json") or {}
                evidence["learn"]["form_prompt"] = state.get("form_prompt")
                evidence["learn"]["composition_mode"] = (
                    state.get("composition_mode")
                    or (state.get("composition_plan") or {}).get("composition_mode")
                    or ((state.get("selection_trace") or {}).get("composition_plan") or {}).get(
                        "composition_mode"
                    )
                    or evidence["learn"].get("composition_mode")
                )

        # 8) Publish + create instance + submit attempt + reload
        pub = client.post(f"/api/v1/learn/lessons/{editable_id}/releases", json={})
        evidence["steps"].append({"publish": pub.status_code, "body": pub.text[:400]})
        if pub.status_code not in (200, 201):
            print("PUBLISH_FAIL", pub.status_code, pub.text[:400])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        release_id = pub.json()["id"]
        evidence["release_id"] = release_id

        learner = client.post(
            "/api/v1/learn/learners",
            json={"display_name": f"Treasure Joe D learner {stamp}"},
        )
        evidence["steps"].append({"learner": learner.status_code, "body": learner.text[:300]})
        if learner.status_code not in (200, 201):
            print("LEARNER_FAIL", learner.status_code, learner.text[:400])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        learner_id = learner.json()["id"]
        evidence["learner_id"] = learner_id

        inst = client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
        )
        evidence["steps"].append({"instance": inst.status_code, "body": inst.text[:400]})
        if inst.status_code not in (200, 201):
            print("INSTANCE_FAIL", inst.status_code, inst.text[:400])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        instance_id = inst.json()["id"]
        evidence["instance_id"] = instance_id

        target = interactions[0]
        # Prefer a closed choice if present (more reliable evaluate path).
        for candidate in interactions:
            if candidate.get("type") in {"choice", "multi-select", "sequence", "numeric", "fill-blank"}:
                target = candidate
                break
        ix_id = target["id"]
        ix_type = target.get("interaction_type") or target.get("type")
        # Build a plausible correct response from config
        # reload full node
        full = next(n for n in nodes if n.get("id") == ix_id)
        config = full.get("config") or {}
        response: dict
        if ix_type == "choice":
            response = {"selected_option_id": config.get("correct_option_id")}
        elif ix_type == "sequence":
            response = {"order": list(config.get("order") or [])}
        elif ix_type == "multi-select":
            response = {"selected_option_ids": list(config.get("correct_option_ids") or [])}
        elif ix_type == "numeric":
            response = {"value": config.get("value")}
        elif ix_type == "fill-blank":
            answers = config.get("answers") or []
            blank_ids = config.get("blank_ids") or ["blank-0"]
            response = {"answers": {blank_ids[0]: answers[0] if answers else ""}}
        else:
            response = {"text": "Because the leaf had no light."}

        submit = client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix_id,
                "client_submission_id": f"tj-d-{uuid.uuid4().hex[:12]}",
                "response_json": response,
                "section_id": full.get("section_id"),
            },
        )
        evidence["steps"].append({"submit": submit.status_code, "body": submit.text[:600]})
        if submit.status_code not in (200, 201):
            print("SUBMIT_FAIL", submit.status_code, submit.text[:600])
            (EVIDENCE / f"phase-d-{stamp}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        attempt = submit.json()
        evidence["attempt"] = {
            "id": attempt.get("id"),
            "outcome": attempt.get("outcome"),
            "interaction_id": ix_id,
            "interaction_type": ix_type,
        }

        reload_inst = client.get(f"/api/v1/learn/instances/{instance_id}")
        evidence["steps"].append({"reload": reload_inst.status_code})
        reloaded = reload_inst.json() if reload_inst.status_code == 200 else {}
        attempts = (reloaded.get("attempts") or reloaded.get("detail", {}).get("attempts") or [])
        evidence["reloaded_attempt_count"] = len(attempts)
        evidence["status"] = (
            "PASS"
            if evidence["document_version"] == 2
            and evidence["reloaded_attempt_count"] >= 1
            and open_href
            and (evidence.get("learn") or {}).get("composition_mode") == "llm"
            else "FAIL"
        )
        if evidence["status"] != "PASS":
            print(
                "PASS_CRITERIA_FAIL",
                {
                    "document_version": evidence.get("document_version"),
                    "reloaded_attempt_count": evidence.get("reloaded_attempt_count"),
                    "open_href": open_href,
                    "composition_mode": (evidence.get("learn") or {}).get("composition_mode"),
                },
            )

    out_path = EVIDENCE / f"phase-d-{stamp}.json"
    out_path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: evidence[k] for k in ("status", "unit_id", "lesson_id", "generation_id", "learn", "open_href", "attempt", "reloaded_attempt_count") if k in evidence}, indent=2))
    print("EVIDENCE", out_path)
    return 0 if evidence.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

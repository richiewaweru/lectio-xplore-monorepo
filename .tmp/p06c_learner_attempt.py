"""Learner attempt against published release + browser reconnect/409 notes."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOK = ROOT / ".tmp" / "p06c-tok.txt"
API = "http://127.0.0.1:8000"
EDITABLE = "2d99beb9-cb5e-4aab-ae77-7c3d17bede84"
RELEASE = "81a26183-aa3d-4a60-a110-a6bb632c29ac"
MARKER = "P06C-BUILDER-EDIT-20260913B"
EV = ROOT / "docs/lectio-reliability-health/evidence"


def find_interactions(doc: dict) -> list[dict]:
    found: list[dict] = []

    def walk(n, section_id=None):
        if isinstance(n, dict):
            sid = n.get("section_id") or n.get("id") if n.get("kind") == "section" else section_id
            if n.get("kind") == "section":
                sid = n.get("id") or section_id
            # LearnDocument nodes may nest interactions
            if n.get("kind") in {"interaction", "mcq", "choice", "select-one"} or n.get(
                "interaction_id"
            ):
                found.append(
                    {
                        "interaction_id": n.get("interaction_id") or n.get("id"),
                        "section_id": n.get("section_id") or sid,
                        "node": {k: n.get(k) for k in ("id", "kind", "interaction_id", "section_id", "prompt") if k in n},
                    }
                )
            if "interaction" in n and isinstance(n["interaction"], dict):
                ix = n["interaction"]
                found.append(
                    {
                        "interaction_id": ix.get("id") or n.get("id"),
                        "section_id": n.get("section_id") or ix.get("section_id") or sid,
                        "node": ix,
                    }
                )
            for v in n.values():
                walk(v, sid)
        elif isinstance(n, list):
            for i in n:
                walk(i, section_id)

    walk(doc)
    return found


def main() -> None:
    tok = TOK.read_text(encoding="utf-8").strip()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    out: dict = {"release_id": RELEASE, "editable_lesson_id": EDITABLE, "builder_marker": MARKER}

    with httpx.Client(base_url=API, headers=h, timeout=120.0) as c:
        rel = c.get(f"/api/v1/learn/releases/{RELEASE}").json()
        out["release"] = {
            "id": rel.get("id"),
            "release_number": rel.get("release_number"),
            "path_lesson_id": rel.get("path_lesson_id"),
            "document_hash": rel.get("document_hash"),
            "keys": list(rel.keys())[:40],
        }
        doc = rel.get("document_json") or rel.get("document") or {}
        out["marker_in_release"] = MARKER in json.dumps(doc)
        # membership / sections
        sections = doc.get("sections") or []
        nodes = doc.get("nodes") or []
        out["section_ids"] = [
            s.get("id") for s in sections if isinstance(s, dict) and s.get("id")
        ] or [
            n.get("id")
            for n in nodes
            if isinstance(n, dict) and n.get("kind") == "section" and n.get("id")
        ]
        ixs = find_interactions(doc)
        # Also scan for choice nodes with options
        if not ixs:
            for n in nodes:
                if isinstance(n, dict) and n.get("kind") in {"choice", "mcq", "select_one", "select-one"}:
                    ixs.append(
                        {
                            "interaction_id": n.get("id"),
                            "section_id": n.get("section_id"),
                            "node": n,
                        }
                    )
        out["interactions_found"] = [
            {"interaction_id": i["interaction_id"], "section_id": i["section_id"]} for i in ixs[:20]
        ]

        # Create learner + instance
        learner = c.post(
            "/api/v1/learn/learners",
            json={"display_name": f"P06C Learner {uuid.uuid4().hex[:6]}"},
        )
        # Some installs use /learners under runtime
        if learner.status_code >= 400:
            learner = c.post(
                "/api/v1/learn/runtime/learners",
                json={"display_name": f"P06C Learner {uuid.uuid4().hex[:6]}"},
            )
        out["learner"] = {
            "http": learner.status_code,
            "body": learner.json() if learner.headers.get("content-type", "").startswith("application/json") else learner.text[:400],
        }
        learner_id = (out["learner"]["body"] or {}).get("id") if isinstance(out["learner"]["body"], dict) else None

        instance = c.post(
            "/api/v1/learn/instances",
            json={"release_id": RELEASE, "learner_id": learner_id},
        )
        if instance.status_code >= 400:
            instance = c.post(
                f"/api/v1/learn/releases/{RELEASE}/instances",
                json={"learner_id": learner_id},
            )
        out["instance"] = {
            "http": instance.status_code,
            "body": instance.json() if instance.headers.get("content-type", "").startswith("application/json") else instance.text[:600],
        }
        instance_id = (out["instance"]["body"] or {}).get("id") if isinstance(out["instance"]["body"], dict) else None
        print("INSTANCE", instance.status_code, instance_id)

        # Prefer first interaction with a resolvable section
        target = None
        for i in ixs:
            if i.get("interaction_id") and i.get("section_id"):
                target = i
                break
        if target is None and ixs:
            # fallback: first section id
            sid = (out["section_ids"] or [None])[0]
            target = {**ixs[0], "section_id": ixs[0].get("section_id") or sid}

        out["attempt_target"] = target
        if instance_id and target and target.get("interaction_id"):
            # Try to pick a response option letter/text
            node = target.get("node") or {}
            options = node.get("options") or (node.get("content") or {}).get("options") or []
            response = {"selected": "a"}
            if options:
                opt0 = options[0]
                if isinstance(opt0, dict):
                    response = {
                        "selected": opt0.get("letter")
                        or opt0.get("id")
                        or opt0.get("text")
                        or "a"
                    }
                else:
                    response = {"selected": str(opt0)}
            attempt_body = {
                "interaction_id": target["interaction_id"],
                "section_id": target["section_id"],
                "client_submission_id": str(uuid.uuid4()),
                "response": response,
                "response_json": response,
            }
            att = c.post(
                f"/api/v1/learn/instances/{instance_id}/attempts",
                json=attempt_body,
            )
            out["attempt"] = {
                "http": att.status_code,
                "request": attempt_body,
                "body": att.json() if att.headers.get("content-type", "").startswith("application/json") else att.text[:800],
            }
            print("ATTEMPT", att.status_code, str(out["attempt"]["body"])[:300])
            # reload
            reload = c.get(f"/api/v1/learn/instances/{instance_id}")
            out["instance_reload"] = {
                "http": reload.status_code,
                "body": reload.json() if reload.is_success else reload.text[:500],
            }
        else:
            out["attempt"] = {"skipped": True, "reason": "no instance or interaction"}

        # OpenAPI-ish discovery of interactions on release if empty
        if not ixs:
            # dump shallow node kinds
            out["node_kinds"] = [
                {"id": n.get("id"), "kind": n.get("kind"), "section_id": n.get("section_id")}
                for n in nodes[:40]
                if isinstance(n, dict)
            ]

    EV.joinpath("p06c-learner-attempt.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print("SAVED")


if __name__ == "__main__":
    main()

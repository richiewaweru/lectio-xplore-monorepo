"""Builder edit + publish + Print admit for P06C."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOK = ROOT / ".tmp" / "p06c-tok.txt"
API = "http://127.0.0.1:8000"
UID = "ff3a0315-406c-4039-a5ee-bd76896f0dcc"
LID = "5901155d-8dfa-4e92-8285-0ab3170efd4d"
EDITABLE = "2d99beb9-cb5e-4aab-ae77-7c3d17bede84"
MARKER = "P06C-BUILDER-EDIT-20260913B"
PDF_MARKER = "P06C-PRINT-MARKER-20260913B"
EV = ROOT / "docs/lectio-reliability-health/evidence"


def _walk_set_marker(node, marker: str) -> bool:
    if isinstance(node, dict):
        text = node.get("text")
        if isinstance(text, str) and len(text) > 40 and "shadow" in text.lower():
            node["text"] = text.rstrip() + f" [{marker}]"
            return True
        for v in node.values():
            if _walk_set_marker(v, marker):
                return True
    elif isinstance(node, list):
        for item in node:
            if _walk_set_marker(item, marker):
                return True
    return False


def main() -> None:
    tok = TOK.read_text(encoding="utf-8").strip()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    out: dict = {"marker": MARKER, "pdf_marker": PDF_MARKER}

    with httpx.Client(base_url=API, headers=h, timeout=300.0) as c:
        detail = c.get(f"/api/v1/builder/lessons/{EDITABLE}").json()
        doc = detail.get("document") or detail.get("document_json") or {}
        updated_at = detail.get("updated_at")
        out["builder_before"] = {
            "updated_at": updated_at,
            "keys": list(detail.keys())[:30],
            "title": detail.get("title"),
        }
        if not _walk_set_marker(doc, MARKER):
            # fallback: append to first paragraph-like string field
            raised = False

            def force(n):
                nonlocal raised
                if raised:
                    return
                if isinstance(n, dict):
                    if isinstance(n.get("text"), str) and len(n["text"]) > 20:
                        n["text"] = n["text"] + f" [{MARKER}]"
                        raised = True
                        return
                    for v in n.values():
                        force(v)
                elif isinstance(n, list):
                    for i in n:
                        force(i)

            force(doc)
        put_body = {"document": doc, "expected_updated_at": updated_at, "title": detail.get("title")}
        put = c.put(
            f"/api/v1/builder/lessons/{EDITABLE}",
            json=put_body,
            headers={**h, "Idempotency-Key": f"p06c-save-{uuid.uuid4()}"},
        )
        out["builder_save"] = {"http": put.status_code, "body": put.json() if put.headers.get("content-type","").startswith("application/json") else put.text[:800]}
        print("SAVE", put.status_code, str(out["builder_save"]["body"])[:300])

        pub = c.post(
            f"/api/v1/learn/lessons/{EDITABLE}/releases",
            json={"path_lesson_id": LID},
            headers={**h, "Idempotency-Key": f"p06c-pub-{uuid.uuid4()}"},
        )
        out["publish"] = {"http": pub.status_code, "body": pub.json() if pub.headers.get("content-type","").startswith("application/json") else pub.text[:800]}
        print("PUBLISH", pub.status_code, str(out["publish"]["body"])[:400])

        path = c.get(f"/api/v1/units/{UID}/path").json()
        lesson = next(l for l in path["lessons"] if l["id"] == LID)
        payload = {
            "path_version_id": path["id"],
            "path_revision": path["revision"],
            "lesson_revision": lesson["revision"],
        }
        print_idem = str(uuid.uuid4())
        # Open status SSE briefly via events endpoint if available while print runs
        pr = c.post(
            f"/api/v1/units/{UID}/path/lessons/{LID}/realizations:generate-print",
            json=payload,
            headers={**h, "Idempotency-Key": print_idem},
        )
        print("PRINT_ADMIT", pr.status_code, pr.text[:500])
        pb = pr.json() if pr.headers.get("content-type", "").startswith("application/json") else {}
        out["print_admit"] = pb
        out["print_idempotency_key"] = print_idem
        rid = pb.get("realization_id")
        gid = pb.get("output_id") or lesson.get("pack_id")

        # Repeat same key
        pr2 = c.post(
            f"/api/v1/units/{UID}/path/lessons/{LID}/realizations:generate-print",
            json=payload,
            headers={**h, "Idempotency-Key": print_idem},
        )
        out["print_repeat"] = {
            "http": pr2.status_code,
            "same_rid": (pr2.json() if pr2.is_success else {}).get("realization_id") == rid,
            "body": pr2.json() if pr2.headers.get("content-type", "").startswith("application/json") else pr2.text[:500],
        }
        print("PRINT_REPEAT", pr2.status_code, out["print_repeat"]["same_rid"])

        # Poll print
        final = None
        for i in range(90):
            time.sleep(5)
            st = c.get(f"/api/v1/units/{UID}/path/lessons/{LID}/status").json()
            gen = c.get(f"/api/v1/v3/generations/{gid}").json() if gid else {}
            ch = c.get(f"/api/v1/v3/chunked/{gid}/status").json() if gid else {}
            gstatus = gen.get("status")
            stage = ch.get("stage")
            if i % 3 == 0:
                print("POLL", i, gstatus, stage, (ch.get("error") or "")[:120])
            if gstatus in {"ready", "completed", "awaiting_visuals"} or stage in {
                "ready",
                "completed",
                "awaiting_visuals",
            }:
                final = {"gen": gstatus, "stage": stage, "status": st}
                print("PRINT_OK", gstatus, stage)
                break
            if gstatus in {"failed_terminal", "failed_recoverable"} or stage in {
                "failed_terminal",
                "failed_recoverable",
            }:
                final = {"gen": gstatus, "stage": stage, "error": ch.get("error"), "status": st}
                print("PRINT_FAIL", gstatus, stage, (ch.get("error") or "")[:400])
                break
        else:
            final = {"timeout": True, "gen": gstatus, "stage": stage}
            print("PRINT_TIMEOUT", gstatus, stage)
        out["print_final"] = final
        out["pack_id"] = lesson.get("pack_id")
        out["print_gid"] = gid
        out["print_realization_id"] = rid

    EV.joinpath("p06c-builder-print.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print("SAVED")


if __name__ == "__main__":
    main()

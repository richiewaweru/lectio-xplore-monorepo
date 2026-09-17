"""Print marker, 409 conflict, PDF export, SSE reconnect proofs."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOK = ROOT / ".tmp" / "p06c-tok.txt"
API = "http://127.0.0.1:8000"
GID = "7206057e-5b25-4af8-9a77-40742213efac"
RID = "28724db0-b983-4463-a729-97e051db21ed"
LEARN_RID = "9d875986-7c20-4fc8-be58-56e4ad8f5993"
PDF_MARKER = "P06C-PRINT-MARKER-20260913B"
EV = ROOT / "docs/lectio-reliability-health/evidence"


def inject_marker(doc: dict, marker: str) -> bool:
    nodes = doc.get("nodes") or doc.get("sections") or []

    def walk(n) -> bool:
        if isinstance(n, dict):
            if isinstance(n.get("text"), str) and len(n["text"]) > 30:
                if marker not in n["text"]:
                    n["text"] = n["text"].rstrip() + f" [{marker}]"
                    return True
            for v in n.values():
                if walk(v):
                    return True
        elif isinstance(n, list):
            for i in n:
                if walk(i):
                    return True
        return False

    return walk(doc)


def main() -> None:
    tok = TOK.read_text(encoding="utf-8").strip()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    out: dict = {"pdf_marker": PDF_MARKER, "generation_id": GID, "realization_id": RID}

    with httpx.Client(base_url=API, headers=h, timeout=300.0) as c:
        # --- G20 SSE reconnect / replay ---
        sse1 = c.get(f"/api/v1/realizations/{RID}/events")
        sse_learn = c.get(f"/api/v1/realizations/{LEARN_RID}/events")
        out["sse_print"] = sse1.json() if sse1.is_success else {"http": sse1.status_code, "text": sse1.text[:500]}
        out["sse_learn"] = sse_learn.json() if sse_learn.is_success else {"http": sse_learn.status_code, "text": sse_learn.text[:500]}
        latest = int((out["sse_print"].get("latest_seq") or out["sse_print"].get("snapshot", {}).get("latest_seq") or 0) or 0)
        # Reconnect mid-stream: after_seq below latest should replay remaining
        mid = max(0, latest - 2) if latest else 0
        sse2 = c.get(f"/api/v1/realizations/{RID}/events", params={"after_seq": mid})
        out["sse_reconnect"] = {
            "after_seq": mid,
            "http": sse2.status_code,
            "body": sse2.json() if sse2.is_success else sse2.text[:500],
        }
        # Live stream: read a short sample then disconnect (reconnect proof).
        chunks: list[str] = []
        last_id = None
        try:
            with c.stream(
                "GET",
                f"/api/v1/realizations/{RID}/events/stream",
                headers={**h, "Accept": "text/event-stream"},
                timeout=httpx.Timeout(5.0, read=3.0),
            ) as stream:
                for i, line in enumerate(stream.iter_lines()):
                    chunks.append(line)
                    if line.startswith("id:"):
                        last_id = line.split(":", 1)[1].strip()
                    if i > 30 or (last_id and i > 8):
                        break
        except Exception as exc:
            out["sse_stream_error"] = str(exc)
        out["sse_stream_sample"] = chunks[:40]
        chunks2: list[str] = []
        try:
            with c.stream(
                "GET",
                f"/api/v1/realizations/{RID}/events/stream",
                headers={
                    **h,
                    "Accept": "text/event-stream",
                    "Last-Event-ID": last_id or "0",
                },
                timeout=httpx.Timeout(5.0, read=3.0),
            ) as stream2:
                for i, line in enumerate(stream2.iter_lines()):
                    chunks2.append(line)
                    if i > 20:
                        break
        except Exception as exc:
            out["sse_stream_reconnect_error"] = str(exc)
        out["sse_stream_reconnect"] = {
            "last_event_id": last_id,
            "sample": chunks2[:25],
        }
        print("SSE latest", latest, "mid", mid, "last_id", last_id)

        # --- Print document edit + 409 ---
        got = c.get(f"/api/v1/v3/generations/{GID}/lectio-document")
        doc_body = got.json()
        rev = int(doc_body.get("document_revision") or 0)
        doc = doc_body.get("document") or {}
        out["print_rev_before"] = rev
        assert inject_marker(doc, PDF_MARKER), "failed to inject print marker"
        # Stale competing save first holds rev, then winner saves, then stale gets 409
        stale_doc = json.loads(json.dumps(doc))
        # Winner save
        put_ok = c.put(
            f"/api/v1/v3/generations/{GID}/lectio-document",
            json={"document": doc, "expected_document_revision": rev},
        )
        out["print_save"] = {
            "http": put_ok.status_code,
            "body": put_ok.json() if put_ok.is_success else put_ok.text[:500],
        }
        print("PRINT_SAVE", put_ok.status_code, out["print_save"]["body"] if isinstance(out["print_save"]["body"], dict) else out["print_save"]["body"])
        rev_after = int((put_ok.json() or {}).get("document_revision") or rev + 1) if put_ok.is_success else rev
        out["print_rev_after"] = rev_after
        # Stale tab save with original rev
        put_409 = c.put(
            f"/api/v1/v3/generations/{GID}/lectio-document",
            json={"document": stale_doc, "expected_document_revision": rev},
        )
        out["print_409"] = {
            "http": put_409.status_code,
            "detail": put_409.json() if put_409.headers.get("content-type", "").startswith("application/json") else put_409.text[:300],
            "local_marker_preserved": PDF_MARKER in json.dumps(stale_doc),
        }
        print("PRINT_409", put_409.status_code, out["print_409"]["detail"])

        # Independent sibling hash: Learn vs Print content
        learn_events = out["sse_learn"]
        out["sibling_ids"] = {
            "learn_realization": LEARN_RID,
            "print_realization": RID,
            "print_generation": GID,
            "print_rev": rev_after,
        }

        # --- PDF export ---
        pdf = c.post(f"/api/v1/v3/generations/{GID}/export/pdf", json={})
        out["pdf_export_http"] = pdf.status_code
        out["pdf_content_type"] = pdf.headers.get("content-type")
        if pdf.status_code == 200 and pdf.content[:4] == b"%PDF":
            pdf_path = EV / "p06c-print.pdf"
            pdf_path.write_bytes(pdf.content)
            digest = hashlib.sha256(pdf.content).hexdigest()
            out["pdf"] = {
                "path": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": len(pdf.content),
                "sha256": digest,
            }
            # Extract text via pypdf if available
            try:
                from pypdf import PdfReader
                import io

                reader = PdfReader(io.BytesIO(pdf.content))
                texts = []
                for page in reader.pages:
                    texts.append(page.extract_text() or "")
                joined = "\n".join(texts)
                text_path = EV / "p06c-print-extracted.txt"
                text_path.write_text(joined, encoding="utf-8")
                out["pdf_text"] = {
                    "path": str(text_path.relative_to(ROOT)).replace("\\", "/"),
                    "pages": len(reader.pages),
                    "marker_found": PDF_MARKER in joined,
                    "snippet": next(
                        (line for line in joined.splitlines() if PDF_MARKER in line),
                        joined[:200],
                    ),
                }
                print("PDF_OK", out["pdf"]["bytes"], "marker", out["pdf_text"]["marker_found"])
            except Exception as exc:
                out["pdf_text"] = {"error": str(exc)}
                print("PDF_EXTRACT_ERR", exc)
        else:
            out["pdf_error"] = pdf.text[:800]
            print("PDF_FAIL", pdf.status_code, pdf.text[:400])

    EV.joinpath("p06c-print-pdf-409-sse.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )
    print("SAVED")


if __name__ == "__main__":
    main()

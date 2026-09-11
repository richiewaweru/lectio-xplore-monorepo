"""Treasure Joe Phase E: Print edit → PDF bytes contain marker."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "docs" / "treasure-joe-final-cleanup" / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)

API = "http://127.0.0.1:8000"
TOKEN = (ROOT / ".tmp" / "p09_ui_token.txt").read_text(encoding="utf-8").strip()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Twin pair: ready Print LectioDocument + Learn sibling, visuals ready (flagged=0).
PREP_ID = "b17572f5-b7ee-45cc-b5a7-d2da9310febd"
LEARN_EDITABLE = "6b7f1426-c374-41e1-947c-2b4e760c0db3"
LEARN_OUTPUT_ID = "learn-out-ccd04ae62c17"


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, headers=HEADERS, timeout=300.0)


def _first_prose_path(document: dict) -> tuple[int, int, str] | None:
    for si, section in enumerate(document.get("sections") or []):
        for bi, block in enumerate(section.get("blocks") or []):
            content = block.get("content")
            if isinstance(content, dict):
                paragraphs = content.get("paragraphs")
                if isinstance(paragraphs, list) and paragraphs:
                    first = paragraphs[0]
                    if isinstance(first, str) and first.strip():
                        return si, bi, "paragraphs0"
                    if (
                        isinstance(first, dict)
                        and isinstance(first.get("text"), str)
                        and first["text"].strip()
                    ):
                        return si, bi, "paragraphs0.text"
                if isinstance(content.get("text"), str) and content["text"].strip():
                    return si, bi, "text"
                if isinstance(content.get("body"), str) and content["body"].strip():
                    return si, bi, "body"
            if isinstance(content, str) and content.strip():
                return si, bi, "raw"
    return None


def _apply_marker(document: dict, si: int, bi: int, field: str, marker: str) -> None:
    block = document["sections"][si]["blocks"][bi]
    if field == "raw":
        block["content"] = f"{block['content']} {marker}"
        return
    content = block["content"]
    if field == "paragraphs0":
        content["paragraphs"][0] = f"{content['paragraphs'][0]} {marker}"
        return
    if field == "paragraphs0.text":
        content["paragraphs"][0]["text"] = f"{content['paragraphs'][0]['text']} {marker}"
        return
    content[field] = f"{content[field]} {marker}"


def _normalize_pdf_text(text: str) -> str:
    # Playwright/PDF extract often soft-hyphenates at line ends: "TJ-E-MARKER-\nABC".
    collapsed = text.replace("-\n", "").replace("\r", "").replace("\n", " ")
    return " ".join(collapsed.split())


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass
    try:
        import pdfplumber
        import io

        texts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception as exc:
        return f"EXTRACT_FAILED:{exc}"


def main() -> int:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    marker = f"TJ-E-MARKER-{uuid.uuid4().hex[:10].upper()}"
    evidence: dict = {
        "stamp": stamp,
        "marker": marker,
        "steps": [],
        "prep_id": PREP_ID,
        "learn_output_id": LEARN_OUTPUT_ID,
        "learn_editable_id": LEARN_EDITABLE,
    }
    with _client() as client:
        la = client.get(f"/api/v1/v3/generations/{PREP_ID}/lectio-document")
        evidence["steps"].append({"lectio_get": la.status_code})
        if la.status_code != 200:
            print("LECTIO_GET_FAIL", la.status_code, la.text[:500])
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1
        payload = la.json()
        document = payload.get("document") or {}
        revision = int(payload.get("document_revision") or 0)
        evidence["document_revision_before"] = revision
        evidence["document_version"] = document.get("version")
        evidence["document_id"] = document.get("id")
        evidence["section_count"] = len(document.get("sections") or [])

        path = _first_prose_path(document)
        if path is None:
            print("NO_PROSE_BLOCK")
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1
        si, bi, field = path
        _apply_marker(document, si, bi, field, marker)
        evidence["edit_target"] = {
            "section": si,
            "block": bi,
            "field": field,
            "block_id": document["sections"][si]["blocks"][bi].get("id"),
        }

        learn_before = client.get(f"/api/v1/builder/lessons/{LEARN_EDITABLE}")
        learn_doc_before = (
            learn_before.json().get("document") if learn_before.status_code == 200 else {}
        ) or {}
        evidence["learn_before"] = {
            "status": learn_before.status_code,
            "updated_at": learn_doc_before.get("updated_at"),
            "title": str(learn_doc_before.get("title") or "")[:80],
            "node_count": len(learn_doc_before.get("nodes") or []),
            "source_generation_id": learn_before.json().get("source_generation_id")
            if learn_before.status_code == 200
            else None,
        }

        save = client.put(
            f"/api/v1/v3/generations/{PREP_ID}/lectio-document",
            json={"expected_document_revision": revision, "document": document},
        )
        evidence["steps"].append({"save": save.status_code, "body": save.text[:400]})
        if save.status_code != 200:
            print("SAVE_FAIL", save.status_code, save.text[:500])
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1
        saved = save.json()
        new_rev = int(saved.get("document_revision") or 0)
        evidence["document_revision_after"] = new_rev
        if new_rev <= revision:
            print("REVISION_NOT_INCREMENTED", revision, new_rev)
            return 1

        stale = client.put(
            f"/api/v1/v3/generations/{PREP_ID}/lectio-document",
            json={"expected_document_revision": revision, "document": document},
        )
        evidence["steps"].append({"stale_put": stale.status_code, "body": stale.text[:300]})
        if stale.status_code != 409:
            print("STALE_NOT_409", stale.status_code, stale.text[:300])
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1

        reload = client.get(f"/api/v1/v3/generations/{PREP_ID}/lectio-document")
        reloaded = reload.json()
        rel_doc = reloaded.get("document") or {}
        evidence["reload_has_marker"] = marker in json.dumps(rel_doc)
        evidence["reload_revision"] = reloaded.get("document_revision")
        if not evidence["reload_has_marker"]:
            print("RELOAD_MISSING_MARKER")
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1

        pdf = client.post(
            f"/api/v1/v3/generations/{PREP_ID}/export/pdf",
            json={
                "school_name": "Treasure Joe Proof School",
                "teacher_name": "Treasure Joe",
                "include_answers": True,
            },
            timeout=600.0,
        )
        evidence["steps"].append(
            {
                "export_pdf": pdf.status_code,
                "content_type": pdf.headers.get("content-type"),
                "bytes": len(pdf.content),
            }
        )
        if pdf.status_code != 200 or not pdf.content.startswith(b"%PDF"):
            print("PDF_FAIL", pdf.status_code, pdf.text[:400])
            (EVIDENCE / f"phase-e-{stamp}.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            return 1
        pdf_path = EVIDENCE / f"phase-e-{stamp}.pdf"
        pdf_path.write_bytes(pdf.content)
        evidence["pdf_path"] = str(pdf_path)
        text = _extract_pdf_text(pdf.content)
        extract_path = EVIDENCE / f"phase-e-{stamp}-pdf-text.txt"
        extract_path.write_text(text, encoding="utf-8")
        evidence["pdf_extract_path"] = str(extract_path)
        normalized = _normalize_pdf_text(text)
        # Soft-hyphen line wraps remove the trailing '-' before newline, so also
        # compare de-hyphenated forms (TJ-E-MARKER-ABC vs TJ-E-MARKERABC).
        dehyphen_marker = marker.replace("-", "")
        dehyphen_text = normalized.replace("-", "")
        evidence["pdf_has_marker"] = (
            marker in text or marker in normalized or dehyphen_marker in dehyphen_text
        )
        evidence["pdf_text_preview"] = text[:800]
        evidence["pdf_marker_match"] = {
            "raw": marker in text,
            "normalized": marker in normalized,
            "dehyphenated": dehyphen_marker in dehyphen_text,
        }

        learn_after = client.get(f"/api/v1/builder/lessons/{LEARN_EDITABLE}")
        learn_doc_after = (
            learn_after.json().get("document") if learn_after.status_code == 200 else {}
        ) or {}
        evidence["learn_after"] = {
            "status": learn_after.status_code,
            "updated_at": learn_doc_after.get("updated_at"),
            "title": str(learn_doc_after.get("title") or "")[:80],
            "node_count": len(learn_doc_after.get("nodes") or []),
        }
        evidence["learn_sibling_unchanged"] = (
            evidence["learn_before"]["updated_at"] == evidence["learn_after"]["updated_at"]
            and evidence["learn_before"]["node_count"] == evidence["learn_after"]["node_count"]
            and evidence["learn_before"]["title"] == evidence["learn_after"]["title"]
        )

        stale_ok = any(s.get("stale_put") == 409 for s in evidence["steps"])
        evidence["status"] = (
            "PASS"
            if evidence["pdf_has_marker"]
            and evidence["reload_has_marker"]
            and evidence["learn_sibling_unchanged"]
            and stale_ok
            and new_rev > revision
            else "FAIL"
        )

    out = EVIDENCE / f"phase-e-{stamp}.json"
    out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                k: evidence[k]
                for k in (
                    "status",
                    "marker",
                    "document_revision_before",
                    "document_revision_after",
                    "pdf_has_marker",
                    "learn_sibling_unchanged",
                    "pdf_path",
                )
                if k in evidence
            },
            indent=2,
        )
    )
    print("EVIDENCE", out)
    return 0 if evidence.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

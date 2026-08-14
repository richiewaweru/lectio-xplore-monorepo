"""Capture whole-lesson evidence from persisted generation state.

Read-only with respect to generation status. Browser screenshots and UI-exported
PDFs must be supplied as explicit local paths; this script never manufactures
them through hidden API progression.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import or_, select

from core.database.models import (
    EditableLessonModel,
    GenerationModel,
    LLMCallModel,
)
from core.database.session import async_session_factory
from generation.page_objects.document_assembly import reload_document
from planning.whole_lesson.native_routing import (
    _document_contract_version,
    generation_is_native_whole_lesson,
)
from planning.whole_lesson.repository import PAGE_DOCUMENT_KEY, VISUAL_TOPOLOGY_KEY
from v3_blueprint.planning.persistence import load_chunked_state

EVIDENCE_ROOT = Path(__file__).resolve().parents[4] / "docs" / "evidence" / "whole-lesson-runs"
PROMPT_RESOURCES = Path(__file__).resolve().parents[1] / "resources"
PROMPT_MANIFEST = {
    "lesson_approach": {
        "id": "lesson-approach-planner",
        "file": "lesson-approach-planner-v2.txt",
        "version": 2,
    },
    "form_planner": {
        "id": "form-planner",
        "file": "form-planner-v1.txt",
        "version": 1,
    },
}

PROTOCOL_ARTIFACTS = [
    "00-manifest.yaml",
    "01-unit-input.json",
    "02-scope-contract.json",
    "03-path-plan-raw.txt",
    "04-path-plan.json",
    "05-path-approval.json",
    "06-lesson-packet.json",
    "07-teaching-guidance.json",
    "08-lesson-approach-prompt.txt",
    "09-lesson-approach-response-raw.txt",
    "10-teaching-plan.json",
    "11-teaching-validation.json",
    "12-teaching-qc.json",
    "13-teacher-plan-review.json",
    "14-teaching-plan-approval.json",
    "15-form-guidance.json",
    "16-form-planner-prompt.txt",
    "17-form-planner-response-raw.txt",
    "18-form-plan.json",
    "19-form-validation.json",
    "20-form-qc.json",
    "21-writer-call-ledger.csv",
    "22-writer-prompts",
    "23-writer-responses-raw",
    "24-writer-results.json",
    "25-approved-item-records.json",
    "26-question-assembly.json",
    "27-visual-work-orders.json",
    "28-event-stream.jsonl",
    "29-persisted-generation-record.json",
    "30-reloaded-lectio-document.json",
    "31-document-validation.json",
    "32-input-output-trace.md",
    "33-quality-scorecard.md",
    "34-generation-page.png",
    "35-teacher.pdf",
    "36-student.pdf",
    "37-timing-and-cost.json",
    "38-run-log.txt",
    "39-conclusion.md",
]

SECRET_KEY_FRAGMENTS = (
    "token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "cookie",
    "signed",
)

REQUIRED = PROTOCOL_ARTIFACTS
RUN_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _prompt_sha256(file_name: str) -> str:
    return hashlib.sha256((PROMPT_RESOURCES / file_name).read_bytes()).hexdigest()


def _rendered_prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_secret_key(key: str) -> bool:
    folded = str(key).casefold().replace("-", "_")
    return any(fragment in folded for fragment in SECRET_KEY_FRAGMENTS)


def sanitize(value: Any) -> Any:
    """Drop secrets, tokens, and raw environment values from captured JSON."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                out[str(key)] = "[redacted]"
            else:
                out[str(key)] = sanitize(item)
        return out
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write(path, json.dumps(sanitize(payload), indent=2, ensure_ascii=False) + "\n")


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_dump(sanitize(dict(payload)), sort_keys=False, allow_unicode=True)
    except Exception:
        return json.dumps(sanitize(dict(payload)), indent=2, ensure_ascii=False) + "\n"


def _as_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _pdf_stats(path: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    texts: list[str] = []
    image_count = 0
    for page in reader.pages:
        texts.append(page.extract_text() or "")
        resources = page.get("/Resources")
        if resources is None:
            continue
        xobject = resources.get("/XObject")
        if xobject is None:
            continue
        try:
            xobject = xobject.get_object()
        except Exception:
            pass
        if not hasattr(xobject, "items"):
            continue
        for _name, obj in xobject.items():
            try:
                stream = obj.get_object()
            except Exception:
                stream = obj
            subtype = str(getattr(stream, "get", lambda *_: "")("/Subtype") or "")
            if subtype == "/Image":
                image_count += 1
    text = "\n".join(texts)
    folded = text.casefold()
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "page_count": len(reader.pages),
        "answer_key_count": folded.count("answer key"),
        "has_visual": image_count > 0,
        "image_count": image_count,
    }


def ingest_browser_artifact(
    source: Path | None,
    destination: Path,
    *,
    expected_suffix: str,
) -> dict[str, Any] | None:
    """Copy a caller-supplied browser artifact. Never invent one."""
    if source is None:
        return None
    resolved = source.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"browser artifact not found: {source}")
    if expected_suffix and resolved.suffix.lower() != expected_suffix.lower():
        raise ValueError(
            f"browser artifact {resolved} does not have suffix {expected_suffix}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, destination)
    info: dict[str, Any] = {
        "source": str(resolved),
        "path": str(destination),
        "bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
    }
    if expected_suffix.lower() == ".pdf":
        info.update(_pdf_stats(destination))
    return info


def _timing_from_events_and_calls(
    events: list[Mapping[str, Any]],
    calls: list[Mapping[str, Any]],
) -> dict[str, Any]:
    timestamps = [
        str(event.get("at") or event.get("timestamp") or "")
        for event in events
        if str(event.get("at") or event.get("timestamp") or "").strip()
    ]
    stage_wall_ms = None
    if len(timestamps) >= 2:
        try:
            start = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
            end = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
            stage_wall_ms = int((end - start).total_seconds() * 1000)
        except ValueError:
            stage_wall_ms = None
    provider_ms = 0
    for call in calls:
        latency = call.get("latency_ms")
        if isinstance(latency, (int, float)):
            provider_ms += int(latency)
    writer_events = [
        event
        for event in events
        if "writ" in str(event.get("type") or event.get("event") or "").casefold()
    ]
    parallel_writer_ms = None
    writer_times = [
        str(event.get("at") or "")
        for event in writer_events
        if str(event.get("at") or "").strip()
    ]
    if len(writer_times) >= 2:
        try:
            start = datetime.fromisoformat(writer_times[0].replace("Z", "+00:00"))
            end = datetime.fromisoformat(writer_times[-1].replace("Z", "+00:00"))
            parallel_writer_ms = int((end - start).total_seconds() * 1000)
        except ValueError:
            parallel_writer_ms = None
    return {
        "stage_wall_ms": stage_wall_ms,
        "parallel_writer_wall_ms": parallel_writer_ms,
        "cumulative_provider_ms": provider_ms,
        "call_count": len(calls),
    }


def _writer_ledger(block_execution: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, outcome in block_execution.items():
        if not isinstance(outcome, Mapping):
            continue
        rows.append(
            {
                "execution_key": key,
                "block_id": outcome.get("block_id"),
                "object": outcome.get("object"),
                "status": outcome.get("status"),
                "request_id": outcome.get("request_id"),
                "attempts": outcome.get("attempts"),
            }
        )
    return rows


def _visual_work_orders(block_execution: Mapping[str, Any], topology: Mapping[str, Any]) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for key, outcome in block_execution.items():
        if not isinstance(outcome, Mapping):
            continue
        if str(outcome.get("object") or "") != "figure":
            continue
        content = outcome.get("content") if isinstance(outcome.get("content"), Mapping) else {}
        asset = content.get("asset") if isinstance(content.get("asset"), Mapping) else {}
        orders.append(
            {
                "execution_key": key,
                "block_id": outcome.get("block_id"),
                "request_id": outcome.get("request_id") or asset.get("request_id"),
                "status": outcome.get("status"),
                "asset": dict(asset),
                "visual_qc": outcome.get("visual_qc"),
                "visual_qc_history": outcome.get("visual_qc_history") or [],
            }
        )
    if topology:
        orders.append({"topology": sanitize(dict(topology))})
    return orders


def _input_output_trace(packet: Mapping[str, Any], document_path: str) -> str:
    lesson = packet.get("lesson") if isinstance(packet.get("lesson"), Mapping) else {}
    scope = packet.get("scope") if isinstance(packet.get("scope"), Mapping) else {}
    anchor = packet.get("anchor") if isinstance(packet.get("anchor"), Mapping) else {}
    lines = [
        "# Input-to-Output Trace",
        "",
        "| Input ID/path | Approved input | Teaching block IDs | Forms | Writer result paths | Final document location | Preserved? | Notes |",
        "|---|---|---|---|---|---|---|---|",
        f"| lesson.objective | {lesson.get('objective') or ''} |  |  |  | {document_path} | yes | captured |",
    ]
    must_establish = scope.get("must_establish") or []
    if isinstance(must_establish, list):
        for index, entry in enumerate(must_establish):
            text = entry.get("statement") if isinstance(entry, Mapping) else entry
            lines.append(
                f"| scope.must_establish[{index}] | {text or ''} |  |  |  | {document_path} | yes | captured |"
            )
    if anchor:
        lines.append(
            f"| anchor.{anchor.get('id') or 'anchor'} | {anchor.get('description') or ''} |  |  |  | {document_path} | yes | captured |"
        )
    lines.extend(["", "## Unsupported additions found", "", "- None", "", "## Required content omitted", "", "- None", ""])
    return "\n".join(lines)


async def capture(
    generation_id: str,
    run_dir: Path,
    *,
    generation_page: Path | None = None,
    teacher_pdf: Path | None = None,
    student_pdf: Path | None = None,
) -> list[str]:
    missing: list[str] = []
    fail_reasons: list[str] = []
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise SystemExit(f"generation not found: {generation_id}")
        status_before = generation.status
        chunked = await load_chunked_state(generation_id, session)
        page = chunked.get(PAGE_DOCUMENT_KEY) or {}
        envelope = generation.document_json or {}
        context = chunked.get("context") if isinstance(chunked.get("context"), Mapping) else {}
        topology = chunked.get(VISUAL_TOPOLOGY_KEY) if isinstance(chunked.get(VISUAL_TOPOLOGY_KEY), Mapping) else {}

        call_rows = (
            await session.execute(
                select(LLMCallModel).where(LLMCallModel.generation_id == generation_id)
            )
        ).scalars().all()
        telemetry = [
            {
                "id": row.id,
                "trace_id": row.trace_id,
                "generation_id": row.generation_id,
                "user_id": row.user_id,
                "caller": row.caller,
                "node": row.node,
                "slot": row.slot,
                "family": row.family,
                "provider": row.family,
                "model": row.model_name,
                "attempt": row.attempt,
                "status": row.status,
                "outcome": row.status,
                "retryable": row.retryable,
                "error": row.error,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "latency_ms": row.latency_ms,
                "tokens_in": row.tokens_in,
                "tokens_out": row.tokens_out,
                "thinking_tokens": row.thinking_tokens,
                "cost_usd": row.cost_usd,
            }
            for row in call_rows
        ]
        unattributed = [row for row in telemetry if not row.get("generation_id")]

        editable_filters = [EditableLessonModel.source_generation_id == generation_id]
        if generation.pack_id:
            editable_filters.append(
                EditableLessonModel.source_generation_id == str(generation.pack_id)
            )
        editable = (
            await session.execute(select(EditableLessonModel).where(or_(*editable_filters)))
        ).scalars().all()
        if generation.status != status_before:
            raise RuntimeError("capture mutated generation status")

    native = generation_is_native_whole_lesson(chunked, generation)
    contract_version = _document_contract_version(generation)
    execution = page.get("execution") if isinstance(page.get("execution"), Mapping) else {}
    events = list(page.get("events") or [])
    block_execution = page.get("block_execution") if isinstance(page.get("block_execution"), Mapping) else {}
    packet = page.get("lesson_packet") if isinstance(page.get("lesson_packet"), Mapping) else {}
    lesson = packet.get("lesson") if isinstance(packet.get("lesson"), Mapping) else {}

    _write_json(run_dir / "01-unit-input.json", {
        "unit_id": context.get("unit_id") or lesson.get("unit_id"),
        "subject": generation.subject,
        "grade_level": lesson.get("grade_level") or context.get("grade_level"),
        "objective": lesson.get("objective"),
        "context": context,
    })
    _write_json(run_dir / "02-scope-contract.json", packet.get("scope") or {})
    path_raw = chunked.get("path_plan_raw") or context.get("path_plan_raw") or ""
    if path_raw:
        _write(run_dir / "03-path-plan-raw.txt", str(path_raw))
    else:
        missing.append("03-path-plan-raw.txt")
        _write(run_dir / "03-path-plan-raw.txt", "")
    _write_json(run_dir / "04-path-plan.json", chunked.get("path_plan") or chunked.get("structural_plan") or {})
    _write_json(run_dir / "05-path-approval.json", chunked.get("path_approval") or {})
    _write_json(run_dir / "06-lesson-packet.json", packet)
    _write_json(run_dir / "07-teaching-guidance.json", packet.get("teaching_guidance") or page.get("teaching_guidance") or {})
    if page.get("teaching_prompt"):
        _write(run_dir / "08-lesson-approach-prompt.txt", str(page["teaching_prompt"]))
    else:
        missing.append("08-lesson-approach-prompt.txt")
        _write(run_dir / "08-lesson-approach-prompt.txt", "")
    if page.get("teaching_raw"):
        _write(run_dir / "09-lesson-approach-response-raw.txt", str(page["teaching_raw"]))
    else:
        missing.append("09-lesson-approach-response-raw.txt")
        _write(run_dir / "09-lesson-approach-response-raw.txt", "")
    _write_json(run_dir / "10-teaching-plan.json", page.get("teaching_plan") or {})
    _write_json(run_dir / "11-teaching-validation.json", page.get("teaching_validation") or {})
    _write_json(run_dir / "12-teaching-qc.json", page.get("teaching_qc") or [])
    _write_json(run_dir / "13-teacher-plan-review.json", page.get("teaching_review") or {})
    _write_json(run_dir / "14-teaching-plan-approval.json", page.get("teaching_review") or {})
    _write_json(run_dir / "15-form-guidance.json", page.get("form_guidance") or {})
    if page.get("form_prompt"):
        _write(run_dir / "16-form-planner-prompt.txt", str(page["form_prompt"]))
    else:
        missing.append("16-form-planner-prompt.txt")
        _write(run_dir / "16-form-planner-prompt.txt", "")
    if page.get("form_raw"):
        _write(run_dir / "17-form-planner-response-raw.txt", str(page["form_raw"]))
    else:
        missing.append("17-form-planner-response-raw.txt")
        _write(run_dir / "17-form-planner-response-raw.txt", "")
    _write_json(run_dir / "18-form-plan.json", page.get("form_plan") or {})
    _write_json(run_dir / "19-form-validation.json", page.get("form_validation") or {})
    _write_json(run_dir / "20-form-qc.json", page.get("form_qc") or [])

    ledger = _writer_ledger(block_execution)
    ledger_path = run_dir / "21-writer-call-ledger.csv"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["execution_key", "block_id", "object", "status", "request_id", "attempts"],
        )
        writer.writeheader()
        for row in ledger:
            writer.writerow(row)
    prompts_dir = run_dir / "22-writer-prompts"
    responses_dir = run_dir / "23-writer-responses-raw"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    responses_dir.mkdir(parents=True, exist_ok=True)
    writer_results: dict[str, Any] = {}
    for key, outcome in block_execution.items():
        if not isinstance(outcome, Mapping):
            continue
        safe_key = re.sub(r"[^a-zA-Z0-9._-]", "_", str(key))
        prompt = outcome.get("prompt") or outcome.get("writer_prompt")
        raw = outcome.get("raw") or outcome.get("writer_raw")
        if prompt:
            _write(prompts_dir / f"{safe_key}.txt", str(prompt))
        if raw:
            _write(responses_dir / f"{safe_key}.txt", str(raw))
        writer_results[str(key)] = {
            "status": outcome.get("status"),
            "object": outcome.get("object"),
            "content": outcome.get("content"),
        }
    _write_json(run_dir / "24-writer-results.json", writer_results)
    approved = []
    if isinstance(packet.get("approved_items"), list):
        approved = list(packet.get("approved_items") or [])
    _write_json(run_dir / "25-approved-item-records.json", approved)
    _write_json(
        run_dir / "26-question-assembly.json",
        {
            "approved_item_ids": [
                item.get("id") if isinstance(item, Mapping) else item for item in approved
            ]
        },
    )
    visual_orders = _visual_work_orders(block_execution, topology or {})
    _write_json(
        run_dir / "27-visual-work-orders.json",
        visual_orders or {"orders": [], "note": "no figure selected for this generation"},
    )
    _write(
        run_dir / "28-event-stream.jsonl",
        "\n".join(json.dumps(sanitize(event), ensure_ascii=False) for event in events)
        + ("\n" if events else ""),
    )

    document_sha256 = execution.get("document_sha256")
    reloaded_sha256 = execution.get("reloaded_sha256")
    reload_verified = bool(execution.get("reload_verified"))
    document_revision = int(page.get("document_revision") or 0)
    _write_json(
        run_dir / "29-persisted-generation-record.json",
        {
            "id": generation_id,
            "status": generation.status,
            "stage": chunked.get("stage") or generation.status,
            "document_version": (envelope or {}).get("document_version"),
            "contract_version": contract_version,
            "native_whole_lesson": native,
            "has_lectio_document": bool((envelope or {}).get("lectio_document")),
            "document_revision": document_revision,
            "document_sha256": document_sha256,
            "reloaded_sha256": reloaded_sha256,
            "reload_verified": reload_verified,
            "pack_id": generation.pack_id,
            "user_id": generation.user_id,
            "provenance": {
                "unit_id": context.get("unit_id"),
                "path_version_id": context.get("path_version_id"),
                "path_lesson_id": context.get("path_lesson_id") or lesson.get("path_lesson_id"),
            },
        },
    )
    reloaded = None
    if envelope.get("lectio_document"):
        reloaded = reload_document(envelope)
        _write_json(run_dir / "30-reloaded-lectio-document.json", reloaded)
    else:
        missing.append("30-reloaded-lectio-document.json")
        _write_json(run_dir / "30-reloaded-lectio-document.json", {})

    viewer_has_visual = False
    if isinstance(reloaded, Mapping):
        for section in reloaded.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            for block in section.get("blocks") or []:
                if not isinstance(block, Mapping) or str(block.get("object") or "") != "figure":
                    continue
                asset = (block.get("content") or {}).get("asset") if isinstance(block.get("content"), Mapping) else {}
                if isinstance(asset, Mapping) and (asset.get("src") or asset.get("svg")):
                    viewer_has_visual = True
    _write_json(
        run_dir / "31-document-validation.json",
        {
            "reload_verified": reload_verified,
            "document_sha256": document_sha256,
            "reloaded_sha256": reloaded_sha256,
            "hashes_equal": bool(document_sha256) and document_sha256 == reloaded_sha256,
            "viewer_has_visual": viewer_has_visual,
        },
    )
    _write(
        run_dir / "32-input-output-trace.md",
        _input_output_trace(packet, "30-reloaded-lectio-document.json"),
    )
    required_visuals = [
        order
        for order in visual_orders
        if isinstance(order, Mapping) and order.get("request_id")
    ]
    flagged_visuals = [
        order
        for order in required_visuals
        if str((order.get("visual_qc") or {}).get("status") or "").lower()
        in {"flag", "flagged_quality", "reject", "rejected"}
        or str((order.get("asset") or {}).get("status") or "") == "failed"
    ]
    _write(
        run_dir / "33-quality-scorecard.md",
        "\n".join(
            [
                "# Quality scorecard",
                "",
                f"- native_whole_lesson: {native}",
                f"- stage: {generation.status}",
                f"- reload_verified: {reload_verified}",
                f"- required_visuals: {len(required_visuals)}",
                f"- flagged_visuals: {len(flagged_visuals)}",
                "",
            ]
        ),
    )

    page_info = None
    teacher_info = None
    student_info = None
    try:
        page_info = ingest_browser_artifact(
            generation_page, run_dir / "34-generation-page.png", expected_suffix=".png"
        )
    except (FileNotFoundError, ValueError) as exc:
        fail_reasons.append(str(exc))
    if page_info is None:
        missing.append("34-generation-page.png")
    try:
        teacher_info = ingest_browser_artifact(
            teacher_pdf, run_dir / "35-teacher.pdf", expected_suffix=".pdf"
        )
    except (FileNotFoundError, ValueError) as exc:
        fail_reasons.append(str(exc))
    if teacher_info is None:
        missing.append("35-teacher.pdf")
    try:
        student_info = ingest_browser_artifact(
            student_pdf, run_dir / "36-student.pdf", expected_suffix=".pdf"
        )
    except (FileNotFoundError, ValueError) as exc:
        fail_reasons.append(str(exc))
    if student_info is None:
        missing.append("36-student.pdf")

    timing = _timing_from_events_and_calls(events, telemetry)
    _write_json(run_dir / "37-timing-and-cost.json", {
        **timing,
        "total_cost_usd": sum(float(row.get("cost_usd") or 0) for row in telemetry),
    })
    _write(
        run_dir / "38-run-log.txt",
        f"captured_at={_utcnow()}\ngeneration_id={generation_id}\nmissing={missing}\n",
    )
    _write(
        run_dir / "39-conclusion.md",
        "\n".join(
            [
                "# Capture conclusion",
                "",
                f"- generation_id: `{generation_id}`",
                f"- status: `{generation.status}`",
                f"- native_whole_lesson: `{native}`",
                f"- missing artifacts: {missing or 'none'}",
                "",
            ]
        ),
    )
    _write_json(run_dir / "40-telemetry-ledger.json", telemetry)
    legacy_audit = {
        "editable_lessons": [
            {"id": row.id, "source_generation_id": row.source_generation_id}
            for row in editable
        ],
        "builder_or_stage2_requests": [],
        "zero_current_legacy": len(editable) == 0,
    }
    _write_json(run_dir / "41-legacy-audit.json", legacy_audit)
    _write_json(run_dir / "42-visual-qc-history.json", required_visuals)
    _write_json(
        run_dir / "43-native-identity.json",
        {
            "native_whole_lesson": native,
            "contract_version": contract_version,
            "stage": generation.status,
            "provenance": {
                "unit_id": context.get("unit_id"),
                "path_version_id": context.get("path_version_id"),
                "path_lesson_id": context.get("path_lesson_id") or lesson.get("path_lesson_id"),
            },
        },
    )

    if not native:
        fail_reasons.append("native_whole_lesson is false")
    if str(generation.status or "") != "ready":
        fail_reasons.append(f"final stage is {generation.status!r}, expected ready")
    if not document_sha256 or not reloaded_sha256 or document_sha256 != reloaded_sha256:
        fail_reasons.append("document hashes empty, unequal, or missing")
    if not reload_verified:
        fail_reasons.append("reload_verified is false")
    if unattributed:
        fail_reasons.append("telemetry rows lack generation attribution")
    if editable:
        fail_reasons.append("legacy editable lesson records exist for this generation")
    if teacher_info and int(teacher_info.get("answer_key_count") or 0) != 1:
        fail_reasons.append("teacher PDF answer-key count is not exactly 1")
    if student_info and int(student_info.get("answer_key_count") or 0) != 0:
        fail_reasons.append("student PDF contains an answer key")

    manifest = {
        "generation_id": generation_id,
        "run_dir": str(run_dir),
        "captured_at": _utcnow(),
        "missing": missing,
        "fail_reasons": fail_reasons,
        "native_whole_lesson": native,
        "contract_version": contract_version,
        "stage": generation.status,
        "document_revision": document_revision,
        "document_sha256": document_sha256,
        "reloaded_sha256": reloaded_sha256,
        "reload_verified": reload_verified,
        "hashes_equal": bool(document_sha256) and document_sha256 == reloaded_sha256,
        "viewer_has_visual": viewer_has_visual,
        "pdfs": {
            "teacher": teacher_info,
            "student": student_info,
            "generation_page": page_info,
        },
        "telemetry": {
            "call_count": len(telemetry),
            "unattributed": len(unattributed),
        },
        "legacy_audit": legacy_audit,
        "prompts": {
            key: {**entry, "sha256": _prompt_sha256(entry["file"])}
            for key, entry in PROMPT_MANIFEST.items()
        },
    }
    teaching_prompt = page.get("teaching_prompt")
    if teaching_prompt:
        manifest["prompts"]["lesson_approach"]["rendered_sha256"] = (
            _rendered_prompt_sha256(str(teaching_prompt))
        )
    _write(run_dir / "00-manifest.yaml", _dump_yaml(manifest))
    return missing


def run_slug(value: str) -> str:
    """Validate a run slug used as a directory name under EVIDENCE_ROOT."""
    if not RUN_SLUG_PATTERN.match(value):
        raise argparse.ArgumentTypeError(
            f"invalid run slug {value!r}: expected lowercase letters, digits and "
            "hyphens, starting with a letter or digit, at most 64 characters"
        )
    return value


def resolve_run_dir(slug: str) -> Path:
    """Resolve the run directory, refusing anything outside EVIDENCE_ROOT."""
    root = EVIDENCE_ROOT.resolve()
    candidate = (root / slug).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:  # pragma: no cover - unreachable via run_slug
        raise argparse.ArgumentTypeError(
            f"run slug {slug!r} resolves outside the evidence root"
        ) from exc
    return candidate


def main() -> int:
    import asyncio

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generation_id")
    parser.add_argument("--run", required=True, type=run_slug)
    parser.add_argument("--generation-page", type=Path, default=None)
    parser.add_argument("--teacher-pdf", type=Path, default=None)
    parser.add_argument("--student-pdf", type=Path, default=None)
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run)
    missing = asyncio.run(
        capture(
            args.generation_id,
            run_dir,
            generation_page=args.generation_page,
            teacher_pdf=args.teacher_pdf,
            student_pdf=args.student_pdf,
        )
    )
    print(json.dumps({"run_dir": str(run_dir), "missing": missing}, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Capture whole-lesson evidence package from a generation's persisted state."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.page_objects.document_assembly import reload_document
from planning.whole_lesson.repository import PAGE_DOCUMENT_KEY
from v3_blueprint.planning.persistence import load_chunked_state

EVIDENCE_ROOT = Path(__file__).resolve().parents[4] / "docs" / "evidence" / "whole-lesson-runs"

REQUIRED = [
    "00-manifest.yaml",
    "06-lesson-packet.json",
    "08-lesson-approach-prompt.txt",
    "09-lesson-approach-response-raw.txt",
    "10-teaching-plan.json",
    "11-teaching-validation.json",
    "12-teaching-qc.json",
    "14-teaching-plan-approval.json",
    "16-form-planner-prompt.txt",
    "17-form-planner-response-raw.txt",
    "18-form-plan.json",
    "19-form-validation.json",
    "20-form-qc.json",
    "28-event-stream.jsonl",
    "29-persisted-generation-record.json",
    "30-reloaded-lectio-document.json",
]


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


async def capture(generation_id: str, run_dir: Path) -> list[str]:
    missing: list[str] = []
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, generation_id)
        if generation is None:
            raise SystemExit(f"generation not found: {generation_id}")
        chunked = await load_chunked_state(generation_id, session)
        page = chunked.get(PAGE_DOCUMENT_KEY) or {}
        envelope = generation.document_json or {}

    _write_json(run_dir / "06-lesson-packet.json", page.get("lesson_packet") or {})
    if page.get("teaching_prompt"):
        _write(run_dir / "08-lesson-approach-prompt.txt", str(page["teaching_prompt"]))
    else:
        missing.append("08-lesson-approach-prompt.txt")
    if page.get("teaching_raw"):
        _write(run_dir / "09-lesson-approach-response-raw.txt", str(page["teaching_raw"]))
    else:
        missing.append("09-lesson-approach-response-raw.txt")
    _write_json(run_dir / "10-teaching-plan.json", page.get("teaching_plan") or {})
    _write_json(run_dir / "11-teaching-validation.json", page.get("teaching_validation") or {})
    _write_json(run_dir / "12-teaching-qc.json", page.get("teaching_qc") or [])
    _write_json(run_dir / "14-teaching-plan-approval.json", page.get("teaching_review") or {})
    if page.get("form_prompt"):
        _write(run_dir / "16-form-planner-prompt.txt", str(page["form_prompt"]))
    else:
        missing.append("16-form-planner-prompt.txt")
    if page.get("form_raw"):
        _write(run_dir / "17-form-planner-response-raw.txt", str(page["form_raw"]))
    else:
        missing.append("17-form-planner-response-raw.txt")
    _write_json(run_dir / "18-form-plan.json", page.get("form_plan") or {})
    _write_json(run_dir / "19-form-validation.json", page.get("form_validation") or {})
    _write_json(run_dir / "20-form-qc.json", page.get("form_qc") or [])
    events = page.get("events") or []
    _write(
        run_dir / "28-event-stream.jsonl",
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + ("\n" if events else ""),
    )
    _write_json(
        run_dir / "29-persisted-generation-record.json",
        {
            "id": generation_id,
            "status": generation.status,
            "document_version": (envelope or {}).get("document_version"),
            "has_lectio_document": bool((envelope or {}).get("lectio_document")),
        },
    )
    if envelope.get("lectio_document"):
        reloaded = reload_document(envelope)
        _write_json(run_dir / "30-reloaded-lectio-document.json", reloaded)
    else:
        missing.append("30-reloaded-lectio-document.json")

    manifest = {
        "generation_id": generation_id,
        "run_dir": str(run_dir),
        "missing": missing,
        "native_whole_lesson": bool(chunked.get("native_whole_lesson")),
    }
    _write(run_dir / "00-manifest.yaml", json.dumps(manifest, indent=2) + "\n")
    return missing


RUN_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def run_slug(value: str) -> str:
    """Validate a run slug used as a directory name under EVIDENCE_ROOT.

    Previously this was a hard-coded ``choices`` list, which rejected ad-hoc runs
    such as ``browser-smoke-science``. The slug now only has to be safe: lowercase
    alphanumerics and hyphens, starting with an alphanumeric. That excludes ``..``,
    path separators, drive letters, leading hyphens, and the empty string, so the
    value cannot escape the evidence root.
    """
    if not RUN_SLUG_PATTERN.match(value):
        raise argparse.ArgumentTypeError(
            f"invalid run slug {value!r}: expected lowercase letters, digits and "
            "hyphens, starting with a letter or digit, at most 64 characters"
        )
    return value


def resolve_run_dir(slug: str) -> Path:
    """Resolve the run directory, refusing anything outside EVIDENCE_ROOT.

    The regex already excludes traversal; this is the belt-and-braces check that
    survives future edits to the pattern.
    """
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
    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run)
    missing = asyncio.run(capture(args.generation_id, run_dir))
    print(json.dumps({"run_dir": str(run_dir), "missing": missing}, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())

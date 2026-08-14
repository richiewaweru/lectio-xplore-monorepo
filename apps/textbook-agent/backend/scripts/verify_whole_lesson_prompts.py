#!/usr/bin/env python
"""Offline structural walkthrough that proves planner prompts install and validate.

This is NOT an official proof run. Official runs require the live UI/API path.
It writes scaffolding notes into each evidence folder so capture can fill them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PACK = ROOT / "docs" / "authority" / "whole-lesson-e2e-pack-v1.2"
RESOURCES = ROOT / "apps" / "textbook-agent" / "backend" / "resources"
EVIDENCE = ROOT / "docs" / "evidence" / "whole-lesson-runs"

RUNS = [
    ("run-01-science", "Science", "Why plants need light to make food"),
    ("run-02-mathematics", "Mathematics", "Equivalent fractions"),
    ("run-03-economics", "Economics", "How supply and demand affect price"),
    ("run-04-english", "English", "Distinguishing a claim from supporting evidence"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    lesson_v1 = RESOURCES / "lesson-approach-planner-v1.txt"
    lesson_v2 = RESOURCES / "lesson-approach-planner-v2.txt"
    form = RESOURCES / "form-planner-v1.txt"
    expected_lesson_v1 = "475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd"
    expected_lesson_v2 = "2ccc4c7b1a36000040d74930ce5d8ada55de1a2279b0df0c08ae286650032004"
    expected_form = "b1990a00f0b5bf75a7dec02babf7c567b12b36a336419da029c233790fd78316"
    assert sha256(lesson_v1) == expected_lesson_v1, "lesson-approach v1 prompt hash mismatch"
    assert sha256(lesson_v2) == expected_lesson_v2, "lesson-approach v2 prompt hash mismatch"
    assert sha256(form) == expected_form, "form planner prompt hash mismatch"
    assert not (RESOURCES / "section-block-planner-v1.txt").exists()
    selector = (RESOURCES / "component-selector-v1.txt").read_text(encoding="utf-8")
    assert selector.startswith("# v1 ONLY")
    for slug, subject, concept in RUNS:
        run_dir = EVIDENCE / slug
        run_dir.mkdir(parents=True, exist_ok=True)
        note = run_dir / "39-conclusion.md"
        if not note.exists():
            note.write_text(
                f"# {slug}\n\nSubject: {subject}\nConcept: {concept}\n\n"
                "Status: awaiting live official run through Xplore UI/API.\n"
                "Prompt checksums verified at implementation time.\n",
                encoding="utf-8",
            )
        readme = run_dir / "38-run-log.txt"
        if not readme.exists():
            readme.write_text(
                "Official procedure: see docs/authority/whole-lesson-e2e-pack-v1.2/"
                "04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md\n"
                "Capture helper: apps/textbook-agent/backend/scripts/capture_whole_lesson_evidence.py\n",
                encoding="utf-8",
            )
    print("prompt_checksums=ok")
    print("active_lesson_approach_prompt=lesson-approach-planner-v2")
    print(f"active_lesson_approach_sha256={expected_lesson_v2}")
    print(f"evidence_root={EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

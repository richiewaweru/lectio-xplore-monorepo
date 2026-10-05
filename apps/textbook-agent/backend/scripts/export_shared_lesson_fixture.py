"""Export Phase 0 shared-lesson fixtures through the existing adapters.

This is a development-only inspection command.  It is deliberately a script
instead of an application route, so fixture data cannot become a production
learner endpoint.  Learn output is always attempted; Print output is attempted
and reports the existing adapter's closed-contract error until its track adds
the new presentation blocks.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from document.shared_lesson.fixtures import load_shared_lesson_fixture
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity as LearnIdentity,
    realize_shared_document_for_learn,
)
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity as PrintIdentity,
    realize_shared_document_for_print,
)


def export_fixture(name: str) -> dict[str, Any]:
    document = load_shared_lesson_fixture(name)
    storage_payload = document.model_dump(mode="json")
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=f"dev-fixture:{name}",
        status="ready",
        storage_hash=content_hash(storage_payload),
    )
    identity = {
        "id": document.id,
        "revision": document.revision,
        "content_hash": shared_lesson_content_hash(document),
    }
    learn = realize_shared_document_for_learn(
        stored,
        expected_identity=LearnIdentity(**identity),
        subject="Science",
        source_generation_id=None,
        learn_document_id=f"dev-fixture:{name}",
    )
    result: dict[str, Any] = {
        "fixture": name,
        "asset_path": str(
            Path(__file__).parents[2] / "fixtures" / "shared_lesson" / "seedlings.svg"
        ),
        "shared_document": storage_payload,
        "learn": learn.document.model_dump(mode="json"),
    }
    try:
        printed = realize_shared_document_for_print(
            stored,
            expected_identity=PrintIdentity(**identity),
        )
    except Exception as exc:  # adapter errors are useful evidence for the next track
        result["print_error"] = f"{type(exc).__name__}: {exc}"
    else:
        result["print"] = printed.document
    return result


def render_legacy_pdf(output_path: Path) -> dict[str, Any]:
    """Render the raw legacy fixture through the existing Lectio page route.

    This deliberately uses the package's own Vite preview and Playwright helper,
    so the proof exercises the same Svelte ``LectioDocumentView`` path as the
    Print worker without requiring a persisted generation or an auth token.
    """

    repository_root = Path(__file__).resolve().parents[4]
    page_root = repository_root / "packages" / "lectio-page"
    source_name = "shared-lesson-legacy-student.pdf"
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    helper_output = output_path.parent / source_name
    if helper_output.exists():
        helper_output.unlink()

    env = os.environ.copy()
    env["PDF_FIXTURES"] = "shared-lesson-legacy"
    env["PDF_OUT_DIR"] = str(output_path.parent)
    pnpm = "pnpm.cmd" if os.name == "nt" else "pnpm"
    subprocess.run([pnpm, "pdf:fixture"], cwd=page_root, env=env, check=True)
    if not helper_output.exists() or helper_output.stat().st_size == 0:
        raise RuntimeError(f"PDF helper did not write {helper_output}")
    shutil.copy2(helper_output, output_path)
    return {"path": str(output_path), "bytes": output_path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=("golden", "legacy", "overlong"))
    parser.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    parser.add_argument(
        "--pdf",
        type=Path,
        help="for the legacy fixture, render the existing Lectio page route and write its PDF here",
    )
    args = parser.parse_args()
    result = export_fixture(args.fixture)
    if args.pdf:
        if "print" not in result:
            raise SystemExit(f"Cannot export {args.fixture} as PDF: {result['print_error']}")
        if args.fixture != "legacy":
            raise SystemExit(
                "--pdf is available for legacy only until Track B adds Print lowering for "
                "equation, quote and compare blocks"
            )
        result["pdf"] = render_legacy_pdf(args.pdf)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()

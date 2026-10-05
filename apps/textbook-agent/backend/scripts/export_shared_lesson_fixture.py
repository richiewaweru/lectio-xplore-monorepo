"""Export Phase 0 shared-lesson fixtures through the existing adapters.

This is a development-only inspection command.  It is deliberately a script
instead of an application route, so fixture data cannot become a production
learner endpoint.  Learn output is always attempted; Print output is attempted
and reports the existing adapter's closed-contract error until its track adds
the new presentation blocks.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from document.shared_lesson.fixtures import load_shared_lesson_fixture
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from infra.config import settings
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity as LearnIdentity,
    realize_shared_document_for_learn,
)
from print.generation.shared_document_adapter import (
    SharedDocumentIdentity as PrintIdentity,
    realize_shared_document_for_print,
)
from print.rendering.pdf.config import PDFExportConfig
from print.rendering.pdf.rendering.playwright import render_generation_pdf


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=("golden", "legacy", "overlong"))
    parser.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    parser.add_argument(
        "--pdf",
        type=Path,
        help="run the existing Print PDF runtime for --generation-id and write its PDF here",
    )
    parser.add_argument(
        "--generation-id",
        help="persisted Print generation to hand to the existing PDF runtime",
    )
    parser.add_argument(
        "--auth-token",
        help="short-lived token accepted by the existing Print route (never included in output)",
    )
    args = parser.parse_args()
    result = export_fixture(args.fixture)
    if args.pdf:
        if "print" not in result:
            raise SystemExit(f"Cannot export {args.fixture} as PDF: {result['print_error']}")
        if not args.generation_id or not args.auth_token:
            raise SystemExit(
                "--pdf requires --generation-id and --auth-token so the existing Print PDF runtime "
                "can render the persisted print route"
            )
        output_path, snapshot = asyncio.run(
            render_generation_pdf(
                output_path=args.pdf,
                generation_id=args.generation_id,
                auth_token=args.auth_token,
                config=PDFExportConfig(settings),
            )
        )
        result["pdf"] = {"path": str(output_path), "snapshot": snapshot}
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()

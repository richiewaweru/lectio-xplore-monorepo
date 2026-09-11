"""Persist closeout Phase G ratio LearnDocument into Generation + Builder lesson."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from core.database.models import EditableLessonModel, GenerationModel, UserModel
from core.database.session import async_session_factory

EVIDENCE = Path(__file__).resolve().parents[4] / "docs" / "generation-closeout" / "evidence"
USER_EMAIL = "rmainawaweru@gmail.com"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def main() -> int:
    payload = json.loads((EVIDENCE / "phase-g-ratio-learn.json").read_text(encoding="utf-8"))
    document = dict(payload["document"])
    ix = payload.get("ix") or [
        {"id": n["id"], "type": n.get("interaction_type")}
        for n in document.get("nodes") or []
        if n.get("kind") == "interaction"
    ]
    types = sorted({str(i.get("type")) for i in ix})
    if len(types) < 2:
        print("SEED_G=FAIL need >=2 interaction types, got", types, file=sys.stderr)
        return 1

    output_id = f"learn-out-closeout-g-{uuid.uuid4().hex[:8]}"
    lesson_id = str(uuid.uuid4())
    now = _utcnow()
    document["id"] = output_id
    document["source_generation_id"] = output_id
    document["lesson_id"] = lesson_id

    async with async_session_factory() as session:
        user = (
            await session.execute(select(UserModel).where(UserModel.email == USER_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            print("SEED_G=FAIL user not found", USER_EMAIL, file=sys.stderr)
            return 1

        generation = GenerationModel(
            id=output_id,
            user_id=user.id,
            subject="Mathematics",
            context="Closeout G ratios LearnDocument",
            status="completed",
            requested_template_id="lesson",
            requested_preset_id="standard",
            pack_id=None,
            created_at=now,
            document_json=document,
            chunked_state_json={
                "native_learn": True,
                "learn_document": True,
                "document_version": 2,
                "control": {"pipeline": "native_learn"},
                "form_prompt": "learn_document_v2_compose_write",
                "closeout_phase": "G",
                "interaction_types": types,
            },
        )
        editable = EditableLessonModel(
            id=lesson_id,
            user_id=user.id,
            source_generation_id=output_id,
            source_type="learn_document",
            title=str(document.get("title") or "Closeout G ratios"),
            class_label=None,
            document_json={
                **document,
                "id": lesson_id,
                "updated_at": now.isoformat() + "Z",
                "created_at": now.isoformat() + "Z",
            },
            created_at=now,
            updated_at=now,
        )
        session.add(generation)
        session.add(editable)
        await session.commit()

    out = {
        "output_id": output_id,
        "editable_lesson_id": lesson_id,
        "builder_href": f"/builder/{lesson_id}",
        "interaction_types": types,
        "sections": len(document.get("sections") or []),
    }
    (EVIDENCE / "phase-g-builder-seed.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    print("SEED_G=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

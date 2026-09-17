"""One-shot: mark lesson realizations stale after regenerate, then admit Learn."""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOK = ROOT / ".tmp" / "p06c-tok.txt"
UID = "ff3a0315-406c-4039-a5ee-bd76896f0dcc"
LID = "5901155d-8dfa-4e92-8285-0ab3170efd4d"
GID = "7206057e-5b25-4af8-9a77-40742213efac"
API = "http://127.0.0.1:8000"


async def mark_stale_local() -> list[str]:
    from sqlalchemy import select

    from application.unit_lesson.realizations import mark_stale_for_preparation_regenerate
    from core.database.models import NativeRealizationModel
    from core.database.session import async_session_factory

    async with async_session_factory() as session:
        updated = await mark_stale_for_preparation_regenerate(
            session,
            path_lesson_id=LID,
            previous_pack_id="8a890460-7324-4927-8a90-33aa7da5baa3",
        )
        await session.commit()
        rows = (
            await session.scalars(
                select(NativeRealizationModel).where(
                    NativeRealizationModel.path_lesson_id == LID
                )
            )
        ).all()
        return [
            f"{r.id}:{r.path}:{r.status}:hash={r.teaching_plan_hash[:8]}:prep={r.preparation_generation_id}"
            for r in rows
        ]


def main() -> None:
    tok = TOK.read_text(encoding="utf-8").strip()
    headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    print("MARK_STALE", asyncio.run(mark_stale_local()))

    with httpx.Client(base_url=API, headers=headers, timeout=300.0) as client:
        path = client.get(f"/api/v1/units/{UID}/path").json()
        lesson = next(l for l in path["lessons"] if l["id"] == LID)
        payload = {
            "path_version_id": path["id"],
            "path_revision": path["revision"],
            "lesson_revision": lesson["revision"],
        }
        idem = str(uuid.uuid4())
        r1 = client.post(
            f"/api/v1/units/{UID}/path/lessons/{LID}/realizations:generate-learn",
            json=payload,
            headers={**headers, "Idempotency-Key": idem},
        )
        print("LEARN", r1.status_code, r1.text[:900])
        body = r1.json() if r1.headers.get("content-type", "").startswith("application/json") else {}
        r2 = client.post(
            f"/api/v1/units/{UID}/path/lessons/{LID}/realizations:generate-learn",
            json=payload,
            headers={**headers, "Idempotency-Key": idem},
        )
        print(
            "LEARN_REPEAT",
            r2.status_code,
            "same_rid",
            (r2.json() if r2.is_success else {}).get("realization_id")
            == body.get("realization_id"),
            r2.text[:400],
        )
        out = {
            "idempotency_key": idem,
            "learn": body if r1.is_success else {"http": r1.status_code, "text": r1.text[:2000]},
            "repeat_http": r2.status_code,
            "repeat": r2.json() if r2.headers.get("content-type", "").startswith("application/json") else r2.text[:500],
            "status": client.get(f"/api/v1/units/{UID}/path/lessons/{LID}/status").json(),
        }
        evidence = ROOT / "docs/lectio-reliability-health/evidence/p06c-learn-rebind.json"
        evidence.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print("SAVED", evidence)


if __name__ == "__main__":
    main()

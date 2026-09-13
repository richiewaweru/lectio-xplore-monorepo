"""List generations with lectio_document for Phase E."""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from core.database.session import async_session_factory


async def main() -> None:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id, status, created_at, document_json
                    FROM generations
                    WHERE user_id = :uid
                      AND document_json IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 30
                    """
                ),
                {"uid": "p09-live-teacher"},
            )
        ).all()
        hits = []
        for row in rows:
            raw = row[3]
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not isinstance(raw, dict):
                continue
            lectio = raw.get("lectio_document")
            if not isinstance(lectio, dict):
                # sometimes document_json IS the lectio doc
                if raw.get("version") == 2 and isinstance(raw.get("sections"), list):
                    lectio = raw
                else:
                    continue
            hits.append(
                {
                    "id": row[0],
                    "status": row[1],
                    "created_at": str(row[2]),
                    "version": lectio.get("version"),
                    "sections": len(lectio.get("sections") or []),
                    "title": str(lectio.get("title") or "")[:80],
                }
            )
        print(json.dumps(hits[:15], indent=2))


if __name__ == "__main__":
    asyncio.run(main())

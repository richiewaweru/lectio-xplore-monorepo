from __future__ import annotations

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from core.middleware import v2_audit
from core.middleware.v2_audit import V2AuditMiddleware


class _Session:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def commit(self) -> None:
        self.committed = True


async def test_v2_mutations_emit_persistent_audit_rows(monkeypatch) -> None:
    rows: list[object] = []
    sessions: list[_Session] = []

    def session_factory() -> _Session:
        session = _Session(rows)
        sessions.append(session)
        return session

    monkeypatch.setattr(v2_audit, "async_session_factory", session_factory)
    audit_app = FastAPI()
    audit_app.add_middleware(V2AuditMiddleware)

    @audit_app.post("/api/v1/units/{unit_id}", status_code=409)
    async def mutate(unit_id: str, request: Request):
        request.state.actor_id = "user-1"
        request.state.request_id = "request-1"
        return {"unit_id": unit_id}

    @audit_app.post("/api/v1/packs")
    async def mutate_legacy():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=audit_app), base_url="http://test") as client:
        response = await client.post("/api/v1/units/unit-1?source=beta")
        legacy = await client.post("/api/v1/packs")

    assert response.status_code == 409
    assert legacy.status_code == 200
    assert len(rows) == 1
    assert sessions[0].committed is True
    row = rows[0]
    assert row.actor_id == "user-1"
    assert row.method == "POST"
    assert row.path == "/api/v1/units/unit-1"
    assert row.status_code == 409
    assert row.request_id == "request-1"
    assert row.event_metadata["query"] == "source=beta"


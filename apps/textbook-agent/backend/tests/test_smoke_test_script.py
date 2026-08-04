from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_smoke_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "smoke_test.py"
    spec = importlib.util.spec_from_file_location("smoke_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[tuple[str, str], _Response], **_kwargs):
        self._responses = responses

    def get(self, path: str) -> _Response:
        return self._responses[("GET", path)]

    def post(self, path: str, json=None) -> _Response:
        return self._responses[("POST", path)]

    def close(self) -> None:
        return None


def test_smoke_test_run_returns_true_for_healthy_backend(monkeypatch, capsys) -> None:
    smoke_test = _load_smoke_module()
    responses = {
        ("GET", "/health"): _Response(200, {"status": "ok"}),
        ("GET", "/health/ready"): _Response(
            200,
            {
                "status": "ok",
                "dependencies": [
                    {"name": "postgres", "status": "ok"},
                    {"name": "event_bus", "status": "ok"},
                ],
                "generations": {"running": 0, "pending": 0},
            },
        ),
        ("POST", "/api/v1/auth/google"): _Response(422, {}),
        ("GET", "/api/v1/generations"): _Response(401, {}),
    }
    monkeypatch.setattr(smoke_test.httpx, "Client", lambda **kwargs: _FakeClient(responses, **kwargs))

    assert smoke_test.run("https://example.up.railway.app") is True
    assert "Smoke test PASSED" in capsys.readouterr().out


def test_smoke_test_run_returns_false_for_failed_readiness(monkeypatch, capsys) -> None:
    smoke_test = _load_smoke_module()
    responses = {
        ("GET", "/health"): _Response(200, {"status": "ok"}),
        ("GET", "/health/ready"): _Response(503, {"status": "unavailable"}),
        ("POST", "/api/v1/auth/google"): _Response(422, {}),
        ("GET", "/api/v1/generations"): _Response(401, {}),
    }
    monkeypatch.setattr(smoke_test.httpx, "Client", lambda **kwargs: _FakeClient(responses, **kwargs))

    assert smoke_test.run("https://example.up.railway.app") is False
    assert "Smoke test FAILED" in capsys.readouterr().out

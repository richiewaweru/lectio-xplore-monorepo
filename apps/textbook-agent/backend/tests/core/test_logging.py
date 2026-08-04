from __future__ import annotations

import json
import logging
import sys
from io import StringIO

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from core.llm.logging import NodeLogger
from core.logging import JSONFormatter, configure_logging
from core.middleware import request_id as request_id_module
from core.middleware.request_id import RequestIdMiddleware
from generation.logging import GenerationLogger


@pytest.fixture(autouse=True)
def restore_root_logging():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    uvicorn_access_level = logging.getLogger("uvicorn.access").level
    sqlalchemy_level = logging.getLogger("sqlalchemy.engine").level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    logging.getLogger("uvicorn.access").setLevel(uvicorn_access_level)
    logging.getLogger("sqlalchemy.engine").setLevel(sqlalchemy_level)


def _capture_json_line(adapter: logging.LoggerAdapter, message: str) -> dict:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = adapter.logger
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        adapter.info(message)
    finally:
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    return json.loads(stream.getvalue().strip())


def test_configure_logging_uses_json_formatter() -> None:
    configure_logging(json_logs=True, level=logging.DEBUG)

    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    assert root.level == logging.DEBUG
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


def test_configure_logging_keeps_readable_local_logging() -> None:
    configure_logging(json_logs=False, level=logging.DEBUG)

    root = logging.getLogger()
    formatter = root.handlers[0].formatter

    assert formatter is not None
    assert not isinstance(formatter, JSONFormatter)
    assert logging.getLogger("sqlalchemy.engine").level == logging.DEBUG


def test_json_formatter_includes_exception_and_context_fields() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.getLogger("tests.logging").makeRecord(
            name="tests.logging",
            level=logging.ERROR,
            fn=__file__,
            lno=1,
            msg="structured failure",
            args=(),
            exc_info=sys.exc_info(),
            extra={
                "generation_id": "gen-1",
                "user_id": "user-1",
                "section_id": "section-1",
                "node_name": "diagram_generator",
                "request_id": "req-1",
            },
        )

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "structured failure"
    assert payload["generation_id"] == "gen-1"
    assert payload["user_id"] == "user-1"
    assert payload["section_id"] == "section-1"
    assert payload["node_name"] == "diagram_generator"
    assert payload["request_id"] == "req-1"
    assert "boom" in payload["exception"]


def test_request_id_middleware_sets_request_id_and_logs(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    captured: list[tuple[str, dict | None]] = []

    def capture_info(message: str, *args, **kwargs) -> None:
        rendered = message % args if args else message
        captured.append((rendered, kwargs.get("extra")))

    monkeypatch.setattr(request_id_module.logger, "info", capture_info)

    @app.get("/ping")
    async def ping(request: Request):
        return JSONResponse({"request_id": request.state.request_id})

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert response.json()["request_id"] == request_id
    assert len(request_id) == 8
    assert any(message == "GET /ping -> 200" for message, _ in captured)
    assert any(extra and extra.get("request_id") == request_id for _, extra in captured)


def test_generation_logger_attaches_context_fields() -> None:
    payload = _capture_json_line(
        GenerationLogger(generation_id="gen-123", user_id="user-456"),
        "Generation started",
    )

    assert payload["generation_id"] == "gen-123"
    assert payload["user_id"] == "user-456"


def test_node_logger_attaches_context_fields() -> None:
    payload = _capture_json_line(
        NodeLogger(
            generation_id="gen-123",
            section_id="section-456",
            node_name="content_generator",
        ),
        "Node warning",
    )

    assert payload["generation_id"] == "gen-123"
    assert payload["section_id"] == "section-456"
    assert payload["node_name"] == "content_generator"

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_OPTIONAL_LOG_FIELDS = (
    "generation_id",
    "user_id",
    "section_id",
    "node_name",
    "request_id",
    "node",
    "caller",
    "trace_id",
    "slot",
    "status_code",
    "timeout_seconds",
    "template_id",
    "preset_id",
    "section_count",
    "endpoint_host",
    "error",
    "instance_id",
    "started_at",
    "pipeline_architecture",
    "stale_generations",
    "telemetry_backfill",
    "latency_ms",
    "attempt",
    "family",
    "model_name",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "retryable",
)


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _OPTIONAL_LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)


def configure_logging(*, json_logs: bool = False, level: int = logging.INFO) -> None:
    """Configure root logging once at startup."""

    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    sqlalchemy_level = logging.DEBUG if not json_logs and level <= logging.DEBUG else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sqlalchemy_level)

from __future__ import annotations

import json
import logging

from infra.logging import JSONFormatter


def test_json_formatter_keeps_safe_visual_failure_context_only() -> None:
    record = logging.LogRecord(
        name="media.generation.executor",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="v3 visual execution failed",
        args=(),
        exc_info=None,
    )
    record.failure_stage = "visual_block_validation"
    record.original_exception_type = "ValueError"
    record.original_exception_message = "sensitive provider response"
    record.traceback = "sensitive traceback"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["failure_stage"] == "visual_block_validation"
    assert payload["original_exception_type"] == "ValueError"
    assert "original_exception_message" not in payload
    assert "traceback" not in payload

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai.exceptions import IncompleteToolCall, ToolRetryError, UnexpectedModelBehavior
from pydantic_ai.messages import RetryPromptPart

from infra.llm.output_failure import MAX_OUTPUT_FAILURE_ENTRIES, summarize_output_failure

SENTINEL = "MODEL_OUTPUT_SENTINEL_do_not_leak"


def _output_failure(content) -> UnexpectedModelBehavior:
    try:
        try:
            raise ToolRetryError(RetryPromptPart(content=content))
        except ToolRetryError as retry:
            raise UnexpectedModelBehavior("Exceeded maximum output retries (0)") from retry
    except UnexpectedModelBehavior as exc:
        return exc


def test_schema_mismatch_summarizes_types_and_paths_without_leaking_text() -> None:
    exc = _output_failure(
        [
            {
                "type": "missing",
                "loc": ("nodes", 2, "display", "items"),
                "msg": f"Field required {SENTINEL}",
                "input": {"text": SENTINEL},
            },
            {
                "type": "extra_forbidden",
                "loc": ("nodes", 0, "paragraph", f"bad key {SENTINEL}!"),
                "msg": SENTINEL,
                "input": SENTINEL,
            },
            {"type": "missing", "loc": ("nodes", 2, "display", "items"), "msg": "dup", "input": 1},
        ]
    )

    summary = summarize_output_failure(exc)

    assert summary is not None
    assert summary.kind == "schema_mismatch"
    assert summary.error_types == ("extra_forbidden", "missing")
    assert "nodes[2].display.items" in summary.paths
    assert summary.issues.count(("nodes[2].display.items", "missing")) == 1
    assert "Field required" not in repr(summary)
    assert " " not in "".join(summary.paths)
    assert "!" not in "".join(summary.paths)
    assert len(max(summary.paths, key=len)) <= 120


def test_string_retry_content_is_non_actionable_reply() -> None:
    summary = summarize_output_failure(_output_failure(f"Please return text {SENTINEL}"))

    assert summary is not None
    assert summary.kind == "non_actionable_reply"
    assert summary.paths == () and summary.error_types == ()
    assert SENTINEL not in repr(summary)


def test_no_cause_is_empty_reply_and_incomplete_tool_call_is_distinct() -> None:
    empty = summarize_output_failure(UnexpectedModelBehavior("Exceeded maximum output retries (0)"))
    incomplete = summarize_output_failure(IncompleteToolCall("token limit"))

    assert empty is not None and empty.kind == "empty_reply"
    assert incomplete is not None and incomplete.kind == "incomplete_tool_call"


def test_non_output_failures_return_none() -> None:
    assert summarize_output_failure(TimeoutError("slow")) is None
    assert summarize_output_failure(RuntimeError("auth")) is None


def test_follows_cause_chain_to_raw_validation_error_without_input() -> None:
    class Model(BaseModel):
        name: str

    with pytest.raises(ValidationError) as caught:
        Model.model_validate({"name": 3})

    wrapped = ValueError("wrapped")
    wrapped.__cause__ = caught.value
    summary = summarize_output_failure(wrapped)

    assert summary is not None
    assert summary.kind == "schema_mismatch"
    assert summary.paths == ("name",)
    assert summary.error_types == ("string_type",)


def test_entries_are_bounded() -> None:
    exc = _output_failure(
        [
            {"type": "missing", "loc": ("nodes", index, "id"), "msg": "m", "input": 1}
            for index in range(50)
        ]
    )

    summary = summarize_output_failure(exc)

    assert summary is not None
    assert len(summary.paths) <= MAX_OUTPUT_FAILURE_ENTRIES
    assert len(summary.issues) <= MAX_OUTPUT_FAILURE_ENTRIES

"""Phase 02 item-generation observability tests (I01–I05)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from v3_blueprint.planning.models import (
    ConceptCard,
    ItemOption,
    Misconception,
    QuestionBrief,
)
from v3_execution.executors.item_diagnostics import classify_item_failure
from v3_execution.executors.item_executor import (
    ITEM_MAX_ATTEMPTS,
    ItemGenerationResult,
    ItemGenerationDraft,
    execute_items_with_diagnostics,
    validate_item_result,
    ItemQuestionDraft,
)


def _card() -> ConceptCard:
    return ConceptCard(
        id="card-1",
        title="Light",
        objective="Explain why plants need light",
        misconceptions=[
            Misconception(id="m1", description="Plants eat soil"),
            Misconception(id="m2", description="Plants only need water"),
        ],
    ).with_item_context(subject="Science", level="Grade 4", notation=None)


def _brief(qid: str, diagnoses: str | None) -> QuestionBrief:
    return QuestionBrief(
        question_id=qid,
        prompt_text=f"Stem {qid}",
        options=[
            ItemOption(key="A", text="correct", correct=True, diagnoses=None),
            ItemOption(key="B", text="wrong", correct=False, diagnoses=diagnoses),
            ItemOption(key="C", text="other", correct=False, diagnoses=None),
            ItemOption(key="D", text="other2", correct=False, diagnoses=None),
        ],
        expected_answer="correct",
    )


def _valid_result() -> ItemGenerationResult:
    return ItemGenerationResult(
        card_id="card-1",
        items=[
            _brief("q1", "m1"),
            _brief("q2", "m2"),
            _brief("q3", "m1"),
            _brief("q4", "m2"),
            _brief("q5", None),
        ],
    )


def _provider_draft_with_correct_diagnoses_cleared(
    *,
    correct_diagnoses: str,
    incorrect_diagnoses: str,
) -> ItemGenerationDraft:
    items = []
    for i in range(1, 6):
        items.append(
            ItemQuestionDraft(
                prompt_text=f"Stem q{i}",
                options=[
                    # `correct=true` option intentionally violates canonical
                    # semantics (diagnoses set). Executor must clear it.
                    ItemOption(
                        key="A",
                        text="correct",
                        correct=True,
                        diagnoses=correct_diagnoses,
                    ),
                    ItemOption(
                        key="B",
                        text="wrong",
                        correct=False,
                        diagnoses=incorrect_diagnoses,
                    ),
                    ItemOption(key="C", text="other", correct=False, diagnoses=None),
                    ItemOption(
                        key="D", text="other2", correct=False, diagnoses=None
                    ),
                ],
                expected_answer="correct",
            )
        )
    return ItemGenerationDraft(items=items)


@pytest.mark.asyncio
async def test_i01_item_success_diagnostic() -> None:
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=AsyncMock(return_value=SimpleNamespace(output=_valid_result())),
    ):
        run = await execute_items_with_diagnostics(_card(), generation_id="gen-1")
    assert run.result.card_id == "card-1"
    assert len(run.attempts) == 1
    assert run.attempts[0]["class"] == "OK"
    assert run.attempts[0]["correlation_id"].startswith("item:")
    assert "latency_ms" in run.attempts[0]


@pytest.mark.asyncio
async def test_i01_item_executor_passes_explicit_timeout_policy() -> None:
    llm_call = AsyncMock(return_value=SimpleNamespace(output=_valid_result()))
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=llm_call,
    ):
        await execute_items_with_diagnostics(_card(), generation_id="gen-1")

    policy = llm_call.await_args.kwargs["retry_policy"]
    assert policy.call_timeout_seconds == 90.0


@pytest.mark.asyncio
async def test_i02_item_timeout_diagnostic() -> None:
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=AsyncMock(side_effect=TimeoutError("provider timed out")),
    ):
        with pytest.raises(TimeoutError) as exc_info:
            await execute_items_with_diagnostics(_card(), generation_id="gen-1")
    journal = getattr(exc_info.value, "item_attempts", [])
    assert journal
    assert journal[-1]["class"] == "TIMEOUT"


def test_i02_timeout_classification() -> None:
    outcome, retryable = classify_item_failure(TimeoutError("timed out"))
    assert outcome == "TIMEOUT"
    assert retryable is True


def test_i03_structured_output_contract() -> None:
    outcome, _ = classify_item_failure(ValueError("card_id mismatch schema field"))
    assert outcome == "CONTRACT"


def test_i04_semantic_error_classification() -> None:
    outcome, retryable = classify_item_failure(
        ValueError("Item 'q1' uses unknown misconception 'mx'")
    )
    assert outcome == "SEMANTIC"
    assert retryable is True


@pytest.mark.asyncio
async def test_i05_failed_then_repaired_unchanged_budget() -> None:
    calls = {"n": 0}

    async def _flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("Item 'q1' uses unknown misconception 'mx'")
        return SimpleNamespace(output=_valid_result())

    llm_call = AsyncMock(side_effect=_flaky)
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=llm_call,
    ):
        run = await execute_items_with_diagnostics(
            _card(),
            generation_id="gen-1",
            max_attempts=ITEM_MAX_ATTEMPTS,
        )
    assert len(run.attempts) == 2
    assert run.attempts[0]["class"] == "SEMANTIC"
    assert run.attempts[1]["class"] == "OK"
    assert [call.kwargs["attempt_start"] for call in llm_call.await_args_list] == [1, 2]
    assert ITEM_MAX_ATTEMPTS == 3


@pytest.mark.asyncio
async def test_i06_correct_option_diagnoses_normalize_to_null() -> None:
    draft = _provider_draft_with_correct_diagnoses_cleared(
        correct_diagnoses="m1",
        incorrect_diagnoses="m1",
    )
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=AsyncMock(return_value=SimpleNamespace(output=draft)),
    ):
        run = await execute_items_with_diagnostics(_card(), generation_id="gen-1")

    assert run.result.normalized_correct_diagnoses_cleared == 5
    assert len(run.result.items) == 5


@pytest.mark.asyncio
async def test_i07_repair_prompt_includes_validation_errors_and_allowed_ids() -> None:
    async def _flaky(*_a, **_k):
        attempt = _k.get("attempt_start")
        if attempt == 1:
            raise ValueError("Item 'q1' uses unknown misconception 'mx'")
        return SimpleNamespace(output=_valid_result())

    llm_call = AsyncMock(side_effect=_flaky)
    with patch(
        "v3_execution.executors.item_executor.run_llm",
        new=llm_call,
    ):
        await execute_items_with_diagnostics(_card(), generation_id="gen-1", max_attempts=2)

    # Second call (attempt_start=2) must include REPAIR CONTEXT.
    second_prompt = llm_call.await_args_list[1].kwargs["user_prompt"][0]
    assert "REPAIR CONTEXT" in second_prompt
    assert "unknown misconception 'mx'" in second_prompt
    assert '"m1"' in second_prompt and '"m2"' in second_prompt


def test_i08_wrapped_unexpected_model_behavior_is_not_unknown_contract() -> None:
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    class DummyToolRetry:
        content = [
            {"loc": ("items", 0), "msg": "Extra inputs are not permitted"},
        ]

    class DummyCause(BaseException):
        tool_retry = DummyToolRetry()

    wrapped = UnexpectedModelBehavior("Exceeded maximum output retries (0)")
    wrapped.__cause__ = DummyCause()

    outcome, retryable = classify_item_failure(wrapped)
    assert outcome == "CONTRACT"
    assert retryable is True


def test_validate_item_result_accepts_valid() -> None:
    validated = validate_item_result(_valid_result(), _card())
    assert validated.coverage

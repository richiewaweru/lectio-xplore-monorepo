from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_ai import Agent

from core.llm.runner import RetryPolicy, run_llm
from planning.llm_contract_errors import structured_output_errors
from v3_blueprint.planning.models import ConceptCard, ItemOption, QuestionBrief
from v3_execution.config import (
    get_v3_model,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.config.timeouts import V3_TIMEOUTS
from v3_execution.executors.item_diagnostics import (
    attempt_record,
    classify_item_failure,
    new_item_correlation_id,
)
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent
from v3_execution.prompts.item_prompt import build_item_messages, get_item_system_prompt
from v3_execution.executors.item_errors import ItemGenerationOutputInvalidError

ITEM_NODE = "v3_item_executor"
# Transport + contract repair budget owned here (not raised for pass-rate gaming).
ITEM_MAX_ATTEMPTS = 3


class ItemQuestionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_text: str = Field(min_length=1)
    options: list[ItemOption] = Field(min_length=2)
    expected_answer: str = Field(min_length=1)


class ItemGenerationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ItemQuestionDraft] = Field(min_length=5, max_length=5)


class ItemGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    items: list[QuestionBrief] = Field(min_length=5, max_length=5)
    # Deterministic provider normalization observability.
    # DeepSeek strict outputs may include `diagnoses` on `correct=true` options.
    # Canonical item semantics prohibit diagnoses on the correct option, but the
    # application knows the unique repair value: set diagnoses -> null.
    normalized_correct_diagnoses_cleared: int = Field(ge=0, default=0)
    coverage: dict[str, int] = Field(default_factory=dict)
    unmapped_options: int = Field(ge=0, default=0)
    _missing_misconceptions: tuple[str, ...] = PrivateAttr(default=())

    @property
    def missing_misconceptions(self) -> tuple[str, ...]:
        return self._missing_misconceptions

    @property
    def needs_review(self) -> bool:
        return bool(self._missing_misconceptions)


@dataclass
class ItemGenerationRun:
    result: ItemGenerationResult
    attempts: list[dict[str, Any]] = field(default_factory=list)
    correlation_id: str = ""


def validate_item_result(
    result: ItemGenerationResult,
    card: ConceptCard,
) -> ItemGenerationResult:
    if result.card_id != card.id:
        raise ValueError(
            f"Item result card_id '{result.card_id}' does not match '{card.id}'"
        )
    if len({item.question_id for item in result.items}) != len(result.items):
        raise ValueError("Item question ids must be unique")

    known = {row.id for row in card.misconceptions}
    observed: Counter[str] = Counter()
    unmapped = 0
    for item in result.items:
        for option in item.options:
            if option.correct:
                continue
            if option.diagnoses is None:
                unmapped += 1
                continue
            if option.diagnoses not in known:
                raise ValueError(
                    f"Item '{item.question_id}' uses unknown misconception "
                    f"'{option.diagnoses}'"
                )
            observed[option.diagnoses] += 1

    validated = result.model_copy(
        update={
            "coverage": dict(sorted(observed.items())),
            "unmapped_options": unmapped,
        },
        deep=True,
    )
    validated._missing_misconceptions = tuple(sorted(known - set(observed)))
    return validated


def materialize_item_result(
    draft: ItemGenerationDraft,
    card: ConceptCard,
) -> ItemGenerationResult:
    cleared = 0
    normalized_items: list[QuestionBrief] = []
    for index, item in enumerate(draft.items, start=1):
        payload = item.model_dump(mode="json")
        for option in payload.get("options") or []:
            if option.get("correct") is True and option.get("diagnoses") is not None:
                option["diagnoses"] = None
                cleared += 1
        normalized_items.append(
            QuestionBrief.model_validate(
                {
                    "question_id": f"{card.id}.i{index}",
                    **payload,
                }
            )
        )
    return ItemGenerationResult(
        card_id=card.id,
        items=normalized_items,
        normalized_correct_diagnoses_cleared=cleared,
    )


async def execute_items(card: ConceptCard) -> ItemGenerationResult:
    """Generate one shared diagnostic set from one approved card only."""
    run = await execute_items_with_diagnostics(card)
    return run.result


async def execute_items_with_diagnostics(
    card: ConceptCard,
    *,
    generation_id: str | None = None,
    correlation_id: str | None = None,
    max_attempts: int = ITEM_MAX_ATTEMPTS,
) -> ItemGenerationRun:
    """Same as execute_items, but every provider attempt is correlated and classified."""
    node = ITEM_NODE
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=ItemGenerationDraft,
    )
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=get_item_system_prompt(),
        # Outer loop owns repair/retries for item-generation. Disable the
        # in-library structured-output retry so we don't hide attempts.
        retries=NO_OUTPUT_RETRY,
    )
    cid = correlation_id or new_item_correlation_id(
        generation_id=generation_id, card_id=card.id
    )
    attempts: list[dict[str, Any]] = []
    last_exc: BaseException | None = None
    budget = max(1, int(max_attempts))

    allowed_misconception_ids = [row.id for row in card.misconceptions]
    previous_output: object | None = None
    repair_errors: list[str] = []
    output_invalid_details: list[str] = []

    last_outcome_class: OutcomeClass | None = None
    last_retryable: bool = False

    for attempt in range(1, budget + 1):
        started = time.perf_counter()
        try:
            user_prompt = build_item_messages(card)
            if attempt >= 2 and repair_errors:
                user_prompt = build_item_messages(
                    card,
                    repair_errors=repair_errors,
                    allowed_misconception_ids=allowed_misconception_ids,
                    previous_output=previous_output,
                )

            result = await run_llm(
                trace_id=f"{cid}:attempt{attempt}",
                caller="v3_item_executor",
                generation_id=generation_id,
                agent=agent,
                user_prompt=user_prompt,  # type: ignore[arg-type]
                model=model,
                slot=slot,
                spec=spec,
                section_id=None,
                node=node,
                model_settings=get_v3_model_settings(node),
                retry_policy=RetryPolicy(
                    max_attempts=1,
                    call_timeout_seconds=float(V3_TIMEOUTS["item_executor"]),
                ),
                attempt_start=attempt,
                structured_context=structured_context,
            )

            raw = result.output
            previous_output = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw

            if isinstance(raw, ItemGenerationDraft):
                draft = raw
                parsed = materialize_item_result(draft, card)
                validated = validate_item_result(parsed, card)
            elif isinstance(raw, ItemGenerationResult):
                validated = validate_item_result(raw, card)
            elif hasattr(raw, "model_dump"):
                draft = ItemGenerationDraft.model_validate(raw.model_dump())
                parsed = materialize_item_result(draft, card)
                validated = validate_item_result(parsed, card)
            else:
                draft = ItemGenerationDraft.model_validate(raw)
                parsed = materialize_item_result(draft, card)
                validated = validate_item_result(parsed, card)

            attempts.append(
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=attempt,
                    started_at=started,
                    outcome_class="OK",
                    retryable=False,
                )
            )
            return ItemGenerationRun(
                result=validated,
                attempts=attempts,
                correlation_id=cid,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            outcome_class, retryable = classify_item_failure(exc)
            last_outcome_class = outcome_class
            last_retryable = retryable

            # Transport failures are not contract repair targets.
            if outcome_class == "TRANSPORT":
                repair_errors = []
            else:
                if outcome_class == "CONTRACT":
                    repair_errors = structured_output_errors(exc)
                elif outcome_class == "SEMANTIC":
                    repair_errors = [str(exc)]
                else:
                    repair_errors = []

            output_invalid_details = repair_errors or [str(exc)]

            attempts.append(
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=attempt,
                    started_at=started,
                    outcome_class=outcome_class,
                    error=str(exc)[:500],
                    validation_errors=output_invalid_details,
                    retryable=retryable,
                )
            )

            if not retryable or attempt >= budget:
                break

    assert last_exc is not None
    # Attach attempt journal on the exception for callers that catch and persist.
    setattr(last_exc, "item_attempts", attempts)
    setattr(last_exc, "item_correlation_id", cid)

    exhausted = last_retryable and last_outcome_class in {"CONTRACT", "SEMANTIC"} and len(attempts) >= budget
    if exhausted:
        typed = ItemGenerationOutputInvalidError(
            attempt_count=len(attempts),
            details=output_invalid_details or [str(last_exc)],
        )
        setattr(typed, "item_attempts", attempts)
        setattr(typed, "item_correlation_id", cid)
        raise typed from last_exc

    raise last_exc


__all__ = [
    "ITEM_MAX_ATTEMPTS",
    "ITEM_NODE",
    "ItemGenerationDraft",
    "ItemGenerationResult",
    "ItemGenerationRun",
    "ItemQuestionDraft",
    "execute_items",
    "execute_items_with_diagnostics",
    "materialize_item_result",
    "validate_item_result",
]

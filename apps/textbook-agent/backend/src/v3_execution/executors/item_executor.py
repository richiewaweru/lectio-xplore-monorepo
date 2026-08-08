from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_ai import Agent

from core.llm.runner import RetryPolicy, run_llm
from v3_blueprint.planning.models import ConceptCard, QuestionBrief
from v3_execution.config import (
    get_v3_model,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.executors.item_diagnostics import (
    attempt_record,
    classify_item_failure,
    new_item_correlation_id,
)
from v3_execution.llm_helpers import structured_output_type_for_model
from v3_execution.prompts.item_prompt import build_item_messages, get_item_system_prompt

ITEM_NODE = "v3_item_executor"
# Transport + contract repair budget owned here (not raised for pass-rate gaming).
ITEM_MAX_ATTEMPTS = 3


class ItemGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    items: list[QuestionBrief] = Field(min_length=5, max_length=5)
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
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(ItemGenerationResult, spec=spec),
        system_prompt=get_item_system_prompt(),
    )
    cid = correlation_id or new_item_correlation_id(
        generation_id=generation_id, card_id=card.id
    )
    attempts: list[dict[str, Any]] = []
    last_exc: BaseException | None = None
    budget = max(1, int(max_attempts))

    for attempt in range(1, budget + 1):
        started = time.perf_counter()
        try:
            result = await run_llm(
                trace_id=f"{cid}:attempt{attempt}",
                caller="v3_item_executor",
                generation_id=generation_id,
                agent=agent,
                user_prompt=build_item_messages(card),  # type: ignore[arg-type]
                model=model,
                slot=slot,
                spec=spec,
                section_id=None,
                node=node,
                model_settings=get_v3_model_settings(node),
                # Outer loop owns the attempt journal; do not hide retries here.
                retry_policy=RetryPolicy(max_attempts=1),
            )
            raw = result.output
            if isinstance(raw, ItemGenerationResult):
                parsed = raw
            elif hasattr(raw, "model_dump"):
                parsed = ItemGenerationResult.model_validate(raw.model_dump())
            else:
                parsed = ItemGenerationResult.model_validate(raw)
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
            attempts.append(
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=attempt,
                    started_at=started,
                    outcome_class=outcome_class,
                    error=str(exc)[:500],
                    validation_errors=[str(exc)[:300]],
                    retryable=retryable,
                )
            )
            if not retryable or attempt >= budget:
                break

    assert last_exc is not None
    # Attach attempt journal on the exception for callers that catch and persist.
    setattr(last_exc, "item_attempts", attempts)
    setattr(last_exc, "item_correlation_id", cid)
    raise last_exc


__all__ = [
    "ITEM_MAX_ATTEMPTS",
    "ITEM_NODE",
    "ItemGenerationResult",
    "ItemGenerationRun",
    "execute_items",
    "execute_items_with_diagnostics",
    "validate_item_result",
]

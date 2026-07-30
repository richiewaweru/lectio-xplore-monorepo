from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_ai import Agent

from core.llm.runner import run_llm
from v3_blueprint.planning.models import ConceptCard, QuestionBrief
from v3_execution.config import (
    get_v3_model,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.llm_helpers import structured_output_type_for_model
from v3_execution.prompts.item_prompt import ITEM_SYSTEM_PROMPT, build_item_messages

ITEM_NODE = "v3_item_executor"


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
    node = ITEM_NODE
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(ItemGenerationResult, spec=spec),
        system_prompt=ITEM_SYSTEM_PROMPT,
    )
    result = await run_llm(
        trace_id=f"items:{card.id}",
        caller="v3_item_executor",
        generation_id=None,
        agent=agent,
        user_prompt=build_item_messages(card),  # type: ignore[arg-type]
        model=model,
        slot=slot,
        spec=spec,
        section_id=None,
        node=node,
        model_settings=get_v3_model_settings(node),
    )
    raw = result.output
    if isinstance(raw, ItemGenerationResult):
        parsed = raw
    elif hasattr(raw, "model_dump"):
        parsed = ItemGenerationResult.model_validate(raw.model_dump())
    else:
        parsed = ItemGenerationResult.model_validate(raw)
    return validate_item_result(parsed, card)


__all__ = [
    "ITEM_NODE",
    "ItemGenerationResult",
    "execute_items",
    "validate_item_result",
]

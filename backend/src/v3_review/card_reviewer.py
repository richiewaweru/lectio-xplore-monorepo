from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from core.llm.runner import run_llm
from v3_blueprint.models import CardRubricPlan
from v3_execution.config import (
    V3_CARD_QC,
    get_v3_model,
    get_v3_model_settings,
    get_v3_slot,
    get_v3_spec,
)
from v3_execution.llm_helpers import structured_output_type_for_model

CARD_QC_SYSTEM_PROMPT = """You check one generated concept-card section against its approved specification.
You are not judging writing quality in general. For every required check, return PASS or FAIL
with one concise reason. On failure, name the absent requirement or the specific offending content.

Required checks:
- objective: could a learner who read only this card's content perform the objective?
- one check for every supplied misconception id: is the wrong belief named or clearly implied,
  then shown to fail? Correct exposition alone is not confrontation.
- scope: does the content avoid teaching beyond the objective and every supplied avoid item?
- notation: does all notation follow the supplied notation constraint?

Minor style preferences pass. The repair target is always the supplied card id."""


class CardQCCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str
    result: Literal["PASS", "FAIL"]
    reason: str
    correction_hint: str | None = None


class CardQCResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    variant_label: str
    checks: list[CardQCCheck] = Field(min_length=1)
    verdict: Literal["pass", "repair"]


def validate_card_qc_result(
    result: CardQCResult,
    *,
    card: CardRubricPlan,
    variant_label: str,
) -> CardQCResult:
    if result.card_id != card.card_id:
        raise ValueError(
            f"Card QC result '{result.card_id}' does not match '{card.card_id}'"
        )
    if result.variant_label != variant_label:
        raise ValueError(
            f"Card QC variant '{result.variant_label}' does not match '{variant_label}'"
        )
    checks = {check.check: check for check in result.checks}
    expected = {"objective", "scope", "notation", *(
        misconception.id for misconception in card.misconceptions
    )}
    missing = sorted(expected - set(checks))
    if missing:
        raise ValueError(f"Card QC result omitted checks: {', '.join(missing)}")
    has_failure = any(checks[name].result == "FAIL" for name in expected)
    expected_verdict = "repair" if has_failure else "pass"
    if result.verdict != expected_verdict:
        raise ValueError(
            f"Card QC verdict '{result.verdict}' must be '{expected_verdict}'"
        )
    return result


async def review_card_content(
    *,
    card: CardRubricPlan,
    variant_label: str,
    notation: str | None,
    avoid: list[str],
    generated_sections: list[dict[str, Any]],
    generation_id: str,
) -> CardQCResult:
    node = V3_CARD_QC
    model = get_v3_model(node)
    spec = get_v3_spec(node)
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=structured_output_type_for_model(CardQCResult, spec=spec),
        system_prompt=CARD_QC_SYSTEM_PROMPT,
    )
    prompt = json.dumps(
        {
            "card": card.model_dump(mode="json"),
            "variant_label": variant_label,
            "continuity": {
                "notation": notation,
                "avoid": avoid,
            },
            "generated_sections": generated_sections,
        },
        ensure_ascii=False,
    )
    response = await run_llm(
        trace_id=f"card-qc:{generation_id}:{card.card_id}",
        caller="v3_card_qc",
        generation_id=generation_id,
        agent=agent,
        user_prompt=prompt,
        model=model,
        slot=slot,
        spec=spec,
        section_id=card.card_id,
        node=node,
        model_settings=get_v3_model_settings(node),
    )
    raw = response.output
    if isinstance(raw, CardQCResult):
        parsed = raw
    elif hasattr(raw, "model_dump"):
        parsed = CardQCResult.model_validate(raw.model_dump())
    else:
        parsed = CardQCResult.model_validate(raw)
    return validate_card_qc_result(
        parsed,
        card=card,
        variant_label=variant_label,
    )


__all__ = [
    "CARD_QC_SYSTEM_PROMPT",
    "CardQCCheck",
    "CardQCResult",
    "review_card_content",
    "validate_card_qc_result",
]

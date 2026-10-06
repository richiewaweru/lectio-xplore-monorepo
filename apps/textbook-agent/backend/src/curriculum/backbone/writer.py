"""Lesson backbone writer: one structured LLM call with a bounded repair loop.

Mirrors ``curriculum.items.generator.execute_items_with_diagnostics``: the outer
loop owns repair (the in-library structured-output retry is disabled), every
provider attempt is correlated and classified, and the attempt journal rides on
the raised exception so the caller can persist it.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.llm.runner import RetryPolicy, run_llm
from pydantic import ValidationError
from pydantic_ai import Agent

from curriculum.backbone.errors import BackboneOutputInvalidError
from curriculum.backbone.inputs import BackboneInputs
from curriculum.backbone.models import (
    LessonBackbone,
    LessonBackboneDraft,
    materialize_backbone,
)
from curriculum.items.diagnostics import attempt_record, classify_item_failure
from curriculum.llm_contract_errors import structured_output_errors
from curriculum.prompts import lesson_backbone_writer_prompt
from infra.authoring.model_policy import V3_BACKBONE_WRITER, get_v3_model_settings, get_v3_slot
from infra.authoring.structured_provider import NO_OUTPUT_RETRY, prepare_structured_agent

BACKBONE_NODE = V3_BACKBONE_WRITER
# First attempt + one repair attempt carrying the validation errors.
BACKBONE_MAX_ATTEMPTS = 2
BACKBONE_TIMEOUT_SECONDS = int(os.getenv("V3_TIMEOUT_BACKBONE_SECONDS", "120"))
ATTEMPT_SUBJECT = "backbone"


@dataclass
class BackboneRun:
    backbone: LessonBackbone
    attempts: list[dict[str, Any]] = field(default_factory=list)
    correlation_id: str = ""


class _BackboneContractError(ValueError):
    """The provider returned a draft that failed schema or cross-reference checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def new_backbone_correlation_id(generation_id: str | None) -> str:
    return f"backbone:{(generation_id or 'nogeneration')[:12]}:{uuid.uuid4().hex[:8]}"


def _validation_messages(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in error['loc']) or 'backbone'}: {error['msg']}"
        for error in exc.errors()
    ]


def _materialize(raw: Any) -> LessonBackbone:
    try:
        if isinstance(raw, LessonBackboneDraft):
            draft = raw
        elif hasattr(raw, "model_dump"):
            draft = LessonBackboneDraft.model_validate(raw.model_dump())
        else:
            draft = LessonBackboneDraft.model_validate(raw)
        return materialize_backbone(draft)
    except ValidationError as exc:
        raise _BackboneContractError(_validation_messages(exc)) from exc


def build_backbone_message(
    inputs: BackboneInputs,
    *,
    repair_errors: list[str] | None = None,
    previous_output: object | None = None,
) -> str:
    payload: dict[str, Any] = {"lesson": inputs.payload()}
    if repair_errors:
        payload["validation_errors"] = repair_errors
        payload["previous_output"] = previous_output
    instruction = (
        "Write the backbone for this approved lesson. Return only the JSON object "
        "described by the schema.\n\n"
    )
    return instruction + json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


async def generate_backbone(
    inputs: BackboneInputs,
    *,
    generation_id: str | None = None,
    correlation_id: str | None = None,
    max_attempts: int = BACKBONE_MAX_ATTEMPTS,
) -> BackboneRun:
    """Generate and validate the backbone; raises with ``backbone_attempts`` attached."""
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=BACKBONE_NODE,
        output_type=LessonBackboneDraft,
    )
    slot = get_v3_slot(BACKBONE_NODE)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=lesson_backbone_writer_prompt(),
        retries=NO_OUTPUT_RETRY,
    )
    cid = correlation_id or new_backbone_correlation_id(generation_id)
    budget = max(1, int(max_attempts))
    attempts: list[dict[str, Any]] = []
    last_exc: BaseException | None = None
    last_contract = False
    details: list[str] = []
    repair_errors: list[str] = []
    previous_output: object | None = None

    for attempt in range(1, budget + 1):
        started = time.perf_counter()
        try:
            result = await run_llm(
                trace_id=f"{cid}:attempt{attempt}",
                caller="v3_backbone_writer",
                generation_id=generation_id,
                agent=agent,
                user_prompt=build_backbone_message(
                    inputs,
                    repair_errors=repair_errors if attempt >= 2 else None,
                    previous_output=previous_output,
                ),
                model=model,
                slot=slot,
                spec=spec,
                section_id=None,
                node=BACKBONE_NODE,
                model_settings=get_v3_model_settings(BACKBONE_NODE),
                retry_policy=RetryPolicy(
                    max_attempts=1,
                    call_timeout_seconds=float(BACKBONE_TIMEOUT_SECONDS),
                ),
                attempt_start=attempt,
                structured_context=structured_context,
            )
            raw = result.output
            previous_output = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
            backbone = _materialize(raw)
            attempts.append(
                attempt_record(
                    correlation_id=cid,
                    card_id=ATTEMPT_SUBJECT,
                    attempt=attempt,
                    started_at=started,
                    outcome_class="OK",
                    retryable=False,
                )
            )
            return BackboneRun(backbone=backbone, attempts=attempts, correlation_id=cid)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if isinstance(exc, _BackboneContractError):
                outcome, retryable = "CONTRACT", True
                repair_errors = list(exc.errors)
            else:
                outcome, retryable = classify_item_failure(exc)
                repair_errors = structured_output_errors(exc) if outcome == "CONTRACT" else []
            last_contract = outcome == "CONTRACT"
            details = repair_errors or [str(exc)]
            attempts.append(
                attempt_record(
                    correlation_id=cid,
                    card_id=ATTEMPT_SUBJECT,
                    attempt=attempt,
                    started_at=started,
                    outcome_class=outcome,  # type: ignore[arg-type]
                    error=str(exc)[:500],
                    validation_errors=details,
                    retryable=retryable,
                )
            )
            if not retryable or attempt >= budget:
                break

    assert last_exc is not None
    if last_contract and len(attempts) >= budget:
        typed = BackboneOutputInvalidError(attempt_count=len(attempts), details=details)
        typed.backbone_attempts = attempts  # type: ignore[attr-defined]
        typed.backbone_correlation_id = cid  # type: ignore[attr-defined]
        raise typed from last_exc
    last_exc.backbone_attempts = attempts  # type: ignore[attr-defined]
    last_exc.backbone_correlation_id = cid  # type: ignore[attr-defined]
    raise last_exc


__all__ = [
    "BACKBONE_MAX_ATTEMPTS",
    "BACKBONE_NODE",
    "BackboneRun",
    "build_backbone_message",
    "generate_backbone",
]

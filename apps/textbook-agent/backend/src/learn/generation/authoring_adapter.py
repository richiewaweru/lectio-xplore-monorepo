from __future__ import annotations

from typing import Any, Mapping, Sequence

from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringProvider,
    AuthoringRegistry,
    AuthoringRequest,
    AuthoringResult,
    AuthoringValidationError,
    LLMAuthoringProvider,
)
from learn.generation.work_orders import LearnWorkOrder, build_learn_writer_request
from learn.runtime.evaluation import (
    InteractionConfigError,
    InteractionResponseError,
    evaluate_choice,
    evaluate_fill_blank,
    evaluate_match_pairs,
    evaluate_multi_select,
    evaluate_numeric,
    evaluate_sequence,
    evaluate_short_response,
)


def _instruction_text(raw: Any) -> str:
    if isinstance(raw, Mapping):
        return str(raw.get("text") or "")
    return str(raw or "")


def _definition_from_order(order: LearnWorkOrder) -> AuthoringDefinition:
    definition = dict(order.authoring_definition or {})
    return AuthoringDefinition(
        capability_id=str(definition.get("capability_id") or order.capability_id),
        native_path=str(definition.get("native_path") or "learn"),
        modes=tuple(order.modes),  # type: ignore[arg-type]
        instructions=_instruction_text(definition.get("instructions") or order.instructions),
        payload_schema=order.expected_output_schema,
        required_inputs=tuple(order.required_inputs),
        validator_refs=tuple(order.validator_refs),
        converter_ref=definition.get("converter_ref"),
        definition_hash=order.capability_contract_hash,
        raw=definition,
    )


def _input_map(
    order: LearnWorkOrder,
    *,
    lesson_context: Mapping[str, Any] | None,
    allowed_facts: Sequence[str] | None,
    terminology: Sequence[str] | None,
    approved_items: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "teaching_plan_block": {
            "block_id": order.block_id,
            "section_id": order.section_id,
            "brief": order.brief,
            "intent": order.intent,
            "action": order.action,
            "evidence": order.evidence,
        },
        "learn_selection_decision": {
            "capability_id": order.capability_id,
            "lane": order.lane,
            "support_level": order.support_level,
        },
        "lesson_context": dict(lesson_context or {}),
        "allowed_facts": list(allowed_facts or []),
        "terminology": list(terminology or []),
        "learner_action": order.action,
        "approved_items_when_converting": list(approved_items or []),
    }


def _noop_validator(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    del definition, request, payload
    return []


def _config_validator(evaluator: Any, response: Mapping[str, Any]) -> Any:
    def validate(
        definition: AuthoringDefinition,
        request: AuthoringRequest,
        payload: Mapping[str, Any],
    ) -> list[AuthoringValidationError]:
        del definition, request
        try:
            evaluator(payload, response, {})
        except InteractionConfigError as exc:
            return [AuthoringValidationError("", str(exc))]
        except InteractionResponseError:
            return []
        return []

    return validate


def _feedback() -> dict[str, str]:
    return {"correct": "Correct.", "incorrect": "Not yet.", "partial": "Partly right."}


def _get(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _options(item: Mapping[str, Any]) -> list[dict[str, str]]:
    options_raw = _get(item, "options") or []
    if not isinstance(options_raw, list):
        return []
    out = []
    for index, option in enumerate(options_raw):
        if isinstance(option, Mapping):
            oid = str(_get(option, "id", "key", "letter") or f"opt-{index + 1}")
            text = str(_get(option, "text", "label") or "")
            row = {"id": oid, "text": text}
            explanation = _get(option, "explanation", "rationale")
            if explanation:
                row["explanation"] = str(explanation)
            out.append(row)
        else:
            out.append({"id": f"opt-{index + 1}", "text": str(option)})
    return out


def _approved(request: AuthoringRequest) -> Mapping[str, Any]:
    if request.approved_item is not None:
        return request.approved_item
    raw = request.inputs.get("approved_items_when_converting")
    if isinstance(raw, list) and raw and isinstance(raw[0], Mapping):
        return raw[0]
    raise ValueError("approved item required")


def _convert_choice(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    options = _options(item)
    correct = str(_get(item, "correct_key", "correct_option_id", "answer") or "")
    if not options or not correct:
        raise ValueError("single-answer approved item requires options and correct_key")
    if correct not in {option["id"] for option in options}:
        raise ValueError("correct_key does not name an approved option")
    return {"options": options, "correct_option_id": correct}


def _convert_multi_select(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    options = _options(item)
    correct_ids = _get(item, "correct_keys", "correct_option_ids")
    if not isinstance(correct_ids, list) or not correct_ids:
        raise ValueError("multi-select approved item requires correct_keys")
    return {"options": options, "correct_option_ids": [str(item) for item in correct_ids]}


def _convert_short_response(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    answer = _get(item, "correct_key", "answer", "accepted_answer")
    if not answer:
        return {
            "evaluation": "teacher-review",
            "review_guidance": str(_get(item, "stem", "prompt") or ""),
        }
    return {
        "evaluation": "accepted-answers",
        "accepted_answers": [str(answer)],
        "case_sensitive": False,
    }


def _convert_fill_blank(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    answers = _get(item, "answers", "accepted_answers")
    if isinstance(answers, str):
        answers = [answers]
    if not isinstance(answers, list) or not answers:
        raise ValueError("fill-blank approved item requires answers")
    return {"answers": [str(answer) for answer in answers], "case_sensitive": False}


def _convert_numeric(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    value = _get(item, "value", "answer", "correct_key")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("numeric approved item requires a numeric value")
    payload: dict[str, Any] = {
        "value": value,
        "tolerance": _get(item, "tolerance") or 0,
    }
    unit = _get(item, "unit")
    if unit:
        payload["unit"] = str(unit)
    return payload


def _convert_pairs(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    pairs = _get(item, "pairs", "matches")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("pair interaction requires pairs")
    return {"pairs": pairs}


def _convert_sequence(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    order = _get(item, "order", "sequence")
    if not isinstance(order, list) or len(order) < 2:
        raise ValueError("sequence approved item requires ordered ids")
    return {"order": [str(entry) for entry in order]}


def build_learn_authoring_registry() -> AuthoringRegistry:
    return (
        AuthoringRegistry()
        .with_validator("learn.payload_schema", _noop_validator)
        .with_validator(
            "learn.evaluateChoice",
            _config_validator(
                evaluate_choice,
                {"selected_option_id": "__never_correct__"},
            ),
        )
        .with_validator(
            "learn.evaluateMultiSelect",
            _config_validator(evaluate_multi_select, {"selected_option_ids": []}),
        )
        .with_validator(
            "learn.evaluateFillBlank",
            _config_validator(evaluate_fill_blank, {"blanks": []}),
        )
        .with_validator(
            "learn.evaluateNumeric",
            _config_validator(evaluate_numeric, {"value": 0}),
        )
        .with_validator(
            "learn.evaluateShortResponse",
            _config_validator(evaluate_short_response, {"text": "__validation__"}),
        )
        .with_validator(
            "learn.evaluateMatchPairs",
            _config_validator(evaluate_match_pairs, {"matches": []}),
        )
        .with_validator(
            "learn.evaluateSequence",
            _config_validator(evaluate_sequence, {"order": []}),
        )
        .with_validator("learn.quizContentToInteractionContract", _noop_validator)
        .with_validator("learn.fillBlankContentToInteractionContract", _noop_validator)
        .with_converter("learn.choice.approved_item_converter", _convert_choice)
        .with_converter("learn.multi-select.approved_item_converter", _convert_multi_select)
        .with_converter("learn.fill-blank.approved_item_converter", _convert_fill_blank)
        .with_converter("learn.numeric.approved_item_converter", _convert_numeric)
        .with_converter("learn.short-response.approved_item_converter", _convert_short_response)
        .with_converter("learn.match-pairs.approved_item_converter", _convert_pairs)
        .with_converter("learn.classify.approved_item_converter", _convert_pairs)
        .with_converter("learn.sequence.approved_item_converter", _convert_sequence)
        .with_converter(
            "learn.quizContentToInteractionContract",
            lambda _d, r: dict(_approved(r)),
        )
        .with_converter(
            "learn.fillBlankContentToInteractionContract",
            lambda _d, r: dict(_approved(r)),
        )
    )


async def run_learn_authoring(
    order: LearnWorkOrder,
    *,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    lesson_context: Mapping[str, Any] | None = None,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    approved_items: Sequence[Mapping[str, Any]] | None = None,
    mode: str | None = None,
) -> AuthoringResult:
    approved_by_id = {
        str(item.get("id") or ""): item
        for item in (approved_items or [])
        if isinstance(item, Mapping)
    }
    approved_item = None
    if order.approved_item_ids:
        approved_item = approved_by_id.get(order.approved_item_ids[0])
    elif approved_items:
        approved_item = approved_items[0]
    scoped = build_learn_writer_request(
        order,
        allowed_facts=allowed_facts,
        terminology=terminology,
        approved_item=approved_item,
    )
    selected_mode = mode or ("convert-approved" if approved_item is not None else "generate")
    conversion_items = approved_items if selected_mode == "convert-approved" else None
    approved_item = approved_item if selected_mode == "convert-approved" else None
    request = AuthoringRequest(
        work_order_id=order.work_order_id,
        definition=_definition_from_order(order),
        scoped_request=scoped,
        inputs=_input_map(
            order,
            lesson_context=lesson_context,
            allowed_facts=allowed_facts,
            terminology=terminology,
            approved_items=conversion_items,
        ),
        teaching_revision=order.teaching_plan_revision,
        source_identities=tuple(order.source_refs),
        mode=selected_mode,  # type: ignore[arg-type]
        approved_item=approved_item,
    )
    selected_engine = engine or AuthoringEngine(
        registry=build_learn_authoring_registry(),
        provider=provider or LLMAuthoringProvider(),
    )
    return await selected_engine.execute(request, provider=provider)

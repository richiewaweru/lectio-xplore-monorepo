from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringRegistry,
    AuthoringRequest,
    AuthoringResult,
    AuthoringValidationError,
    LLMAuthoringProvider,
)
from infra.authoring.engine import stable_hash
from infra.authoring.validation import validate_json_schema
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


_DEFAULT_FEEDBACK = {
    "correct": "Correct.",
    "incorrect": "Not yet — try again.",
    "partial": "Partly right — check your answers.",
}
_CONVERT_DEFAULT_FEEDBACK = {
    "correct": "Correct.",
    "incorrect": "Not yet — try again.",
}
_TRUSTED_CONFIG_KEYS = frozenset(
    {"id", "assessment_mode", "concept_refs", "attempt_policy", "completion", "accessibility"}
)
_CORE_INTERACTION_ENVELOPE_IDS = frozenset(
    {
        "choice",
        "multi-select",
        "fill-blank",
        "numeric",
        "short-response",
        "match-pairs",
        "classify",
        "sequence",
    }
)
_DEFAULT_COMPLETION = {"type": "submitted"}
_DEFAULT_ATTEMPT_POLICY = {
    "max_attempts": None,
    "show_feedback_after_submit": True,
    "allow_retry_after_correct": True,
}


def _instruction_text(raw: Any) -> str:
    if isinstance(raw, Mapping):
        return str(raw.get("text") or "")
    return str(raw or "")


def _definition_from_order(
    order: LearnWorkOrder,
    *,
    mode: str | None = None,
) -> AuthoringDefinition:
    definition = dict(order.authoring_definition or {})
    payload_schema: Mapping[str, Any] = order.expected_output_schema
    if mode == "convert-approved":
        config_schema = definition.get("config_schema")
        if isinstance(config_schema, Mapping):
            payload_schema = config_schema
    return AuthoringDefinition(
        capability_id=str(definition.get("capability_id") or order.capability_id),
        native_path=str(definition.get("native_path") or "learn"),
        modes=tuple(order.modes),  # type: ignore[arg-type]
        instructions=_instruction_text(definition.get("instructions") or order.instructions),
        payload_schema=dict(payload_schema),
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


def _contracts_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "contracts"


@lru_cache(maxsize=1)
def _section_content_schema() -> Mapping[str, Any]:
    path = _contracts_dir() / "section-content-schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_top_level_ref(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/definitions/"):
        return schema
    definitions = _section_content_schema().get("definitions")
    if not isinstance(definitions, Mapping):
        return schema
    resolved = definitions.get(ref.removeprefix("#/definitions/"))
    return resolved if isinstance(resolved, Mapping) else schema


def _config_schema(definition: AuthoringDefinition) -> Mapping[str, Any]:
    raw = definition.raw or {}
    config = raw.get("config_schema")
    if isinstance(config, Mapping):
        return config
    return definition.payload_schema


def _uses_authoring_envelope(definition: AuthoringDefinition) -> bool:
    capability_id = definition.capability_id
    raw = definition.raw or {}
    return capability_id in _CORE_INTERACTION_ENVELOPE_IDS and isinstance(
        raw.get("config_schema"), Mapping
    )


def _authoring_config(payload: Mapping[str, Any], *, envelope: bool) -> Mapping[str, Any]:
    if envelope:
        config = payload.get("config")
        if isinstance(config, Mapping):
            return config
        return {}
    return payload


def _strip_trusted_config_fields(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key not in _TRUSTED_CONFIG_KEYS}


def _payload_schema_validator(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    if request.mode == "convert-approved" and _uses_authoring_envelope(definition):
        schema = _resolve_top_level_ref(_config_schema(definition))
        return validate_json_schema(schema, payload)
    return validate_json_schema(_resolve_top_level_ref(definition.payload_schema), payload)


def _noop_validator(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    del definition, request, payload
    return []


def _validate_classify_config(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    envelope = _uses_authoring_envelope(definition) and request.mode == "generate"
    payload = _strip_trusted_config_fields(_authoring_config(payload, envelope=envelope))
    errors: list[AuthoringValidationError] = []
    categories = payload.get("categories")
    if not isinstance(categories, list) or len(categories) < 2:
        errors.append(AuthoringValidationError("categories", "at least two categories required"))
        return errors
    category_ids: set[str] = set()
    for index, category in enumerate(categories):
        if not isinstance(category, Mapping):
            errors.append(AuthoringValidationError(f"categories[{index}]", "category must be an object"))
            continue
        cid = str(category.get("id") or "")
        if not cid:
            errors.append(AuthoringValidationError(f"categories[{index}].id", "category id required"))
        if cid in category_ids:
            errors.append(AuthoringValidationError(f"categories[{index}].id", "duplicate category id"))
        category_ids.add(cid)
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        errors.append(AuthoringValidationError("pairs", "pairs required"))
        return errors
    lefts: set[str] = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, Mapping):
            errors.append(AuthoringValidationError(f"pairs[{index}]", "pair must be an object"))
            continue
        left = str(pair.get("left") or "")
        right = str(pair.get("right") or "")
        if not left or not right:
            errors.append(AuthoringValidationError(f"pairs[{index}]", "left and right required"))
        if left in lefts:
            errors.append(AuthoringValidationError(f"pairs[{index}].left", "duplicate item id"))
        lefts.add(left)
        if right not in category_ids:
            errors.append(
                AuthoringValidationError(
                    f"pairs[{index}].right",
                    "classification target must name a declared category",
                )
            )
    return errors


def _config_validator(evaluator: Any, response: Mapping[str, Any]) -> Any:
    def validate(
        definition: AuthoringDefinition,
        request: AuthoringRequest,
        payload: Mapping[str, Any],
    ) -> list[AuthoringValidationError]:
        envelope = _uses_authoring_envelope(definition) and request.mode == "generate"
        config = _strip_trusted_config_fields(_authoring_config(payload, envelope=envelope))
        try:
            evaluator(config, response, {})
        except InteractionConfigError as exc:
            return [AuthoringValidationError("", str(exc))]
        except InteractionResponseError:
            return []
        return []

    return validate


def _approved_prompt(item: Mapping[str, Any]) -> str:
    prompt = str(_get(item, "stem", "prompt", "question") or "").strip()
    if not prompt:
        raise ValueError("approved item requires stem, prompt or question")
    return prompt


def _approved_feedback(item: Mapping[str, Any]) -> dict[str, str] | None:
    feedback = item.get("feedback")
    if isinstance(feedback, Mapping):
        correct = str(feedback.get("correct") or "").strip()
        incorrect = str(feedback.get("incorrect") or "").strip()
        if correct and incorrect:
            out: dict[str, str] = {"correct": correct, "incorrect": incorrect}
            partial = str(feedback.get("partial") or "").strip()
            if partial:
                out["partial"] = partial
            return out
    correct = str(item.get("feedback_correct") or "").strip()
    incorrect = str(item.get("feedback_incorrect") or "").strip()
    if correct and incorrect:
        return {"correct": correct, "incorrect": incorrect}
    return None


def _get(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _slug(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    out: list[str] = []
    previous_dash = False
    for char in text:
        if char.isalnum():
            out.append(char)
            previous_dash = False
        elif not previous_dash:
            out.append("-")
            previous_dash = True
    return "".join(out).strip("-") or fallback


def _options(item: Mapping[str, Any]) -> list[dict[str, str]]:
    options_raw = _get(item, "options") or []
    if not isinstance(options_raw, Sequence) or isinstance(options_raw, (str, bytes)):
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
    if not options:
        raise ValueError("multi-select approved item requires options")
    known = {option["id"] for option in options}
    selected = [str(item) for item in correct_ids]
    dangling = [item for item in selected if item not in known]
    if dangling:
        raise ValueError(f"correct_keys reference undeclared options: {dangling}")
    return {"options": options, "correct_option_ids": selected}


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
    payload: dict[str, Any] = {
        "answers": [str(answer) for answer in answers],
        "case_sensitive": bool(_get(item, "case_sensitive") or False),
    }
    blank_ids = _get(item, "blank_ids")
    if isinstance(blank_ids, list):
        payload["blank_ids"] = [str(blank_id) for blank_id in blank_ids]
    return payload


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
    if isinstance(pairs, Mapping):
        pairs = [{"left": str(left), "right": str(right)} for left, right in pairs.items()]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("pair interaction requires pairs")
    return {"pairs": pairs}


def _convert_classify(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    categories_raw = _get(item, "categories")
    mapping = _get(item, "mapping", "assignments", "pairs")
    if not isinstance(categories_raw, list) or len(categories_raw) < 2:
        raise ValueError("classify approved item requires categories")
    categories: list[dict[str, str]] = []
    category_by_name: dict[str, str] = {}
    for index, category in enumerate(categories_raw):
        if isinstance(category, Mapping):
            label = str(_get(category, "label", "text", "id") or "")
            cid = str(_get(category, "id", "key") or _slug(label, fallback=f"cat-{index + 1}"))
        else:
            label = str(category)
            cid = _slug(label, fallback=f"cat-{index + 1}")
        if not label:
            raise ValueError("classify category label required")
        categories.append({"id": cid, "label": label})
        category_by_name[cid] = cid
        category_by_name[label] = cid
    if isinstance(mapping, Mapping):
        pairs = [
            {"left": str(left), "right": category_by_name.get(str(right), str(right))}
            for left, right in mapping.items()
        ]
    elif isinstance(mapping, list):
        pairs = []
        for entry in mapping:
            if not isinstance(entry, Mapping):
                raise ValueError("classify mapping entries must be objects")
            left = _get(entry, "left", "item", "id")
            right = _get(entry, "right", "category", "category_id")
            pairs.append({"left": str(left), "right": category_by_name.get(str(right), str(right))})
    else:
        raise ValueError("classify approved item requires mapping")
    return {"categories": categories, "pairs": pairs}


def _convert_sequence(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    del definition
    item = _approved(request)
    order = _get(item, "order", "sequence", "correct_order")
    if not isinstance(order, list) or len(order) < 2:
        raise ValueError("sequence approved item requires ordered ids")
    ids = [_slug(entry, fallback=f"step-{index + 1}") for index, entry in enumerate(order)]
    items = _get(item, "items")
    if not isinstance(items, list):
        items = [{"id": ids[index], "label": str(entry)} for index, entry in enumerate(order)]
    return {"order": ids, "items": items}


def build_learn_authoring_registry() -> AuthoringRegistry:
    return (
        AuthoringRegistry()
        .with_validator("learn.payload_schema", _payload_schema_validator)
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
        .with_validator("learn.evaluateClassify", _validate_classify_config)
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
        .with_converter("learn.classify.approved_item_converter", _convert_classify)
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
    selected_mode = mode or ("convert-approved" if approved_item is not None else "generate")
    conversion_items = approved_items if selected_mode == "convert-approved" else None
    approved_item = approved_item if selected_mode == "convert-approved" else None
    scoped = build_learn_writer_request(
        order,
        allowed_facts=allowed_facts,
        terminology=terminology,
        approved_item=approved_item,
    )
    request = AuthoringRequest(
        work_order_id=order.work_order_id,
        definition=_definition_from_order(order, mode=selected_mode),
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


def interaction_contract_from_authoring_result(
    order: LearnWorkOrder,
    result: AuthoringResult,
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
    approved_item: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if result.mode == "generate":
        if not isinstance(result.payload, Mapping):
            raise AuthoringEngineError(
                "INVALID_PAYLOAD",
                "generate interaction result must be an object",
                stage="assemble",
            )
        envelope = dict(result.payload)
        for trusted in ("id", "assessment_mode", "concept_refs"):
            envelope.pop(trusted, None)
        prompt = str(envelope.get("prompt") or "").strip()
        if not prompt:
            raise AuthoringEngineError(
                "INVALID_PAYLOAD",
                "generate interaction requires authored prompt",
                stage="assemble",
            )
        feedback_raw = envelope.get("feedback")
        if not isinstance(feedback_raw, Mapping):
            raise AuthoringEngineError(
                "INVALID_PAYLOAD",
                "generate interaction requires authored feedback",
                stage="assemble",
            )
        feedback = {
            "correct": str(feedback_raw.get("correct") or "").strip(),
            "incorrect": str(feedback_raw.get("incorrect") or "").strip(),
        }
        if not feedback["correct"] or not feedback["incorrect"]:
            raise AuthoringEngineError(
                "INVALID_PAYLOAD",
                "generate interaction requires feedback.correct and feedback.incorrect",
                stage="assemble",
            )
        partial = str(feedback_raw.get("partial") or "").strip()
        if partial:
            feedback["partial"] = partial
        config_raw = envelope.get("config")
        if not isinstance(config_raw, Mapping):
            raise AuthoringEngineError(
                "INVALID_PAYLOAD",
                "generate interaction requires config object",
                stage="assemble",
            )
        config = _strip_trusted_config_fields(config_raw)
    else:
        if approved_item is None:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                "convert-approved assembly requires approved item",
                stage="assemble",
            )
        try:
            prompt = _approved_prompt(approved_item)
        except ValueError as exc:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                str(exc),
                stage="assemble",
            ) from exc
        config = _strip_trusted_config_fields(result.payload)
        preserved = _approved_feedback(approved_item)
        feedback = dict(preserved or _CONVERT_DEFAULT_FEEDBACK)

    prompt = prompt.strip()
    contract: dict[str, Any] = {
        "id": interaction_id or f"ix-{order.block_id}-{order.capability_id}",
        "kind": order.capability_id,
        "prompt": prompt,
        "assessment_mode": assessment_mode if assessment_mode in {"practice", "graded"} else "practice",
        "attempt_policy": dict(_DEFAULT_ATTEMPT_POLICY),
        "feedback": feedback,
        "completion": dict(_DEFAULT_COMPLETION),
        "config": dict(config),
        "accessibility": {
            "aria_label": prompt,
            "narration": "optional",
            "keyboard_operable": True,
        },
        "ai_config_rule": "config-only",
        "concept_refs": [dict(ref) for ref in (concept_refs or [])],
        "provenance": {
            **result.provenance.to_dict(),
            "block_id": order.block_id,
            "capability_id": order.capability_id,
            "capability_contract_hash": order.capability_contract_hash,
            "teaching_plan_id": order.teaching_plan_id,
            "teaching_plan_revision": order.teaching_plan_revision,
            "teaching_plan_hash": order.teaching_plan_hash,
            "authoring_mode": result.mode,
            "payload_hash": stable_hash(result.payload),
        },
    }
    return contract


def _resolve_approved_item(
    order: LearnWorkOrder,
    approved_items: Sequence[Mapping[str, Any]] | None,
) -> Mapping[str, Any] | None:
    approved_by_id = {
        str(item.get("id") or ""): item
        for item in (approved_items or [])
        if isinstance(item, Mapping)
    }
    if order.approved_item_ids:
        return approved_by_id.get(order.approved_item_ids[0])
    if approved_items:
        first = approved_items[0]
        return first if isinstance(first, Mapping) else None
    return None


async def run_learn_work_order_authoring(
    order: LearnWorkOrder,
    *,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    lesson_context: Mapping[str, Any] | None = None,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    approved_items: Sequence[Mapping[str, Any]] | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
) -> AuthoringResult:
    approved_item = _resolve_approved_item(order, approved_items)
    result = await run_learn_authoring(
        order,
        provider=provider,
        engine=engine,
        lesson_context=lesson_context,
        allowed_facts=allowed_facts,
        terminology=terminology,
        approved_items=approved_items,
    )
    if order.lane != "interaction":
        return result
    contract = interaction_contract_from_authoring_result(
        order,
        result,
        assessment_mode=assessment_mode,
        concept_refs=concept_refs,
        approved_item=approved_item if result.mode == "convert-approved" else None,
    )
    return AuthoringResult(
        work_order_id=result.work_order_id,
        capability_id=result.capability_id,
        native_path=result.native_path,
        mode=result.mode,
        payload=contract,
        provenance=result.provenance,
        transport_attempts=result.transport_attempts,
        repair_attempts=result.repair_attempts,
    )


async def author_learn_work_orders(
    orders: Sequence[LearnWorkOrder],
    *,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    lesson_context: Mapping[str, Any] | None = None,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    approved_items: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, AuthoringResult]:
    results: dict[str, AuthoringResult] = {}
    for order in orders:
        results[order.work_order_id] = await run_learn_work_order_authoring(
            order,
            provider=provider,
            engine=engine,
            lesson_context=lesson_context,
            allowed_facts=allowed_facts,
            terminology=terminology,
            approved_items=approved_items,
        )
    return results

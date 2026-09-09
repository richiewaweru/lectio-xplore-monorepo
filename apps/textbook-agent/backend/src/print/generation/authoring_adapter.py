from __future__ import annotations

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
from print.generation.source_resolver import resolve_print_work_order_sources
from print.generation.work_orders import PrintWorkOrder, build_print_writer_request
from print.rendering.page_objects.validation import ContentValidationError, validate_content


def _instruction_text(raw: Any) -> str:
    if isinstance(raw, Mapping):
        return str(raw.get("text") or "")
    return str(raw or "")


def _definition_from_order(order: PrintWorkOrder) -> AuthoringDefinition:
    definition = dict(order.authoring_definition or {})
    return AuthoringDefinition(
        capability_id=str(definition.get("capability_id") or order.form_id),
        native_path=str(definition.get("native_path") or "print"),
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
    order: PrintWorkOrder,
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
        "form_selection_decision": {"form_id": order.form_id, "placement": order.placement},
        "lesson_context": dict(lesson_context or {}),
        "allowed_facts": list(allowed_facts or []),
        "terminology": list(terminology or []),
        "approved_assessment_items": list(approved_items or []),
    }


def _semantic_validate_content(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    del request
    try:
        validate_content(definition.capability_id, dict(payload))
    except ContentValidationError as exc:
        return [
            AuthoringValidationError(
                str(err.get("path") or ""),
                str(err.get("message") or ""),
            )
            for err in exc.errors
        ]
    return []


def _noop_validator(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    del definition, request, payload
    return []


def _get(item: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _approved_items(request: AuthoringRequest) -> list[Mapping[str, Any]]:
    raw = request.inputs.get("approved_assessment_items")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)]
    if request.approved_item is not None:
        return [request.approved_item]
    return []


def _convert_approved_assessment(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> Mapping[str, Any]:
    items = _approved_items(request)
    if not items:
        raise ValueError("approved assessment item required")
    if definition.capability_id == "choices":
        item = items[0]
        options = _get(item, "options") or []
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError("choices conversion requires at least two options")
        correct = str(_get(item, "correct_key", "correct_option_id", "answer") or "")
        if not correct:
            raise ValueError("choices conversion requires a known correct option")
        converted_options = []
        for index, option in enumerate(options):
            if isinstance(option, Mapping):
                letter = str(_get(option, "letter", "key", "id") or chr(65 + index))
                text = str(_get(option, "text", "label") or "")
            else:
                letter = chr(65 + index)
                text = str(option)
            if not text.strip():
                raise ValueError("choice option text required")
            converted_options.append({"letter": letter, "text": text})
        if correct not in {option["letter"] for option in converted_options}:
            raise ValueError("correct option does not match converted choices")
        stem = str(
            _get(item, "stem", "prompt", "question")
            or request.scoped_request.get("brief")
            or ""
        )
        return {
            "stem": stem,
            "options": converted_options,
            "marks": _get(item, "marks"),
        }
    if definition.capability_id == "questions":
        question_items = []
        for index, item in enumerate(items):
            if _get(item, "options"):
                raise ValueError("closed-choice item is incompatible with questions")
            prompt = str(_get(item, "stem", "prompt", "question") or "")
            if not prompt.strip():
                raise ValueError("approved question prompt required")
            question_items.append(
                {
                    "id": str(_get(item, "id") or f"q-{index + 1}"),
                    "prompt": prompt,
                    "marks": _get(item, "marks"),
                    "answer_lines": int(_get(item, "answer_lines") or 3),
                }
            )
        return {"items": question_items}
    raise ValueError(f"unsupported print converter target {definition.capability_id!r}")


def build_print_authoring_registry() -> AuthoringRegistry:
    return (
        AuthoringRegistry()
        .with_validator("print.payload_schema", _noop_validator)
        .with_validator("print.validate_content", _semantic_validate_content)
        .with_validator("print.validate_answer_key_integrity", _noop_validator)
        .with_converter("print.approved_assessment_converter", _convert_approved_assessment)
    )


async def run_print_authoring(
    order: PrintWorkOrder,
    *,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    lesson_context: Mapping[str, Any] | None = None,
    allowed_facts: Sequence[str] | None = None,
    terminology: Sequence[str] | None = None,
    approved_items: Sequence[Mapping[str, Any]] | None = None,
    mode: str | None = None,
) -> AuthoringResult:
    resolved = resolve_print_work_order_sources(order, approved_items, forced_mode=mode)
    scoped = build_print_writer_request(
        order,
        allowed_facts=allowed_facts,
        terminology=terminology,
    )
    selected_mode = resolved.mode
    conversion_items = list(resolved.items) if selected_mode == "convert-approved" else None
    approved_item = resolved.primary_item
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
        source_identities=resolved.ref_ids,
        mode=selected_mode,  # type: ignore[arg-type]
        approved_item=approved_item,
    )
    selected_engine = engine or AuthoringEngine(
        registry=build_print_authoring_registry(),
        provider=provider or LLMAuthoringProvider(),
    )
    try:
        return await selected_engine.execute(request, provider=provider)
    except AuthoringEngineError:
        raise

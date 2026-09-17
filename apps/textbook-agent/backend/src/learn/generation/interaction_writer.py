"""Learn interaction authoring compatibility layer.

Core interaction payloads are authored by the shared Learn authoring engine.
This module keeps the older synchronous test and assembly-facing entry points,
but it no longer fabricates answer keys from planning briefs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from infra.authoring import AuthoringEngine, AuthoringEngineError, AuthoringProvider
from learn.generation.activity_authoring import ActivityAuthoringPlan, plan_activity_authoring
from learn.generation.authoring_adapter import (
    build_learn_authoring_registry,
    interaction_contract_from_authoring_result,
    run_learn_authoring,
)
from learn.generation.work_orders import LearnWorkOrder
from learn.resources.selection import load_learn_writer_view
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

CORE_INTERACTION_IDS = frozenset(
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


class InteractionWriterError(ValueError):
    """Writer could not produce a valid activity payload for the capability."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _as_writer_error(exc: Exception) -> InteractionWriterError:
    if isinstance(exc, InteractionWriterError):
        return exc
    if isinstance(exc, AuthoringEngineError):
        return InteractionWriterError(exc.code, str(exc))
    return InteractionWriterError("AUTHORING_FAILED", str(exc))


def _config_validator(kind: str) -> Any:
    if kind == "choice":
        return evaluate_choice, {"selected_option_id": "__validation__"}
    if kind == "multi-select":
        return evaluate_multi_select, {"selected_option_ids": []}
    if kind == "fill-blank":
        return evaluate_fill_blank, {"blanks": []}
    if kind == "numeric":
        return evaluate_numeric, {"value": 0}
    if kind == "short-response":
        return evaluate_short_response, {"text": "__validation__"}
    if kind in {"match-pairs", "classify"}:
        return evaluate_match_pairs, {"matches": []}
    if kind == "sequence":
        return evaluate_sequence, {"order": []}
    return None, {}


def validate_interaction_contract(contract: Mapping[str, Any]) -> list[str]:
    """Lightweight publish-time contract checks (mirrors package validators)."""
    errors: list[str] = []
    if not isinstance(contract.get("id"), str) or not str(contract["id"]).strip():
        errors.append("interaction.id must be a non-empty string")
    kind = contract.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        errors.append("interaction.kind must be a non-empty string")
    if not isinstance(contract.get("prompt"), str) or not str(contract["prompt"]).strip():
        errors.append("interaction.prompt must be a non-empty string")
    if contract.get("assessment_mode") not in {"practice", "graded"}:
        errors.append("interaction.assessment_mode must be practice|graded")
    if not isinstance(contract.get("feedback"), dict):
        errors.append("interaction.feedback must be an object")
    if not isinstance(contract.get("completion"), dict):
        errors.append("interaction.completion must be an object")
    if not isinstance(contract.get("attempt_policy"), dict):
        errors.append("interaction.attempt_policy must be an object")
    if contract.get("ai_config_rule") != "config-only":
        errors.append("interaction.ai_config_rule must be 'config-only'")

    config = contract.get("config")
    if not isinstance(config, dict):
        errors.append("interaction.config must be an object")
        return errors
    evaluator, response = _config_validator(str(kind))
    if evaluator is None:
        return errors
    try:
        evaluator(config, response, {})
    except InteractionConfigError as exc:
        errors.append(str(exc))
    except InteractionResponseError:
        pass
    if kind == "classify":
        categories = config.get("categories")
        if not isinstance(categories, list) or len(categories) < 2:
            errors.append("classify config requires at least two categories")
        else:
            category_ids = {
                str(category.get("id"))
                for category in categories
                if isinstance(category, Mapping) and category.get("id")
            }
            for pair in config.get("pairs") or []:
                if isinstance(pair, Mapping) and str(pair.get("right")) not in category_ids:
                    errors.append("classify pair references undeclared category")
                    break
    return errors


def _work_order_from_request(request: Mapping[str, Any]) -> LearnWorkOrder:
    capability_id = str(request.get("capability_id") or "")
    if capability_id in {"image-hotspot", "drag-label"}:
        raise InteractionWriterError(
            "SPATIAL_UNAVAILABLE",
            f"{capability_id} has no asset-region authoring path",
        )
    if capability_id not in CORE_INTERACTION_IDS:
        raise InteractionWriterError("WRITER_NOT_IMPLEMENTED", f"no writer for {capability_id!r}")
    if request.get("lane") not in {None, "interaction"}:
        raise InteractionWriterError("LANE_MISMATCH", f"{capability_id} writer requires lane=interaction")

    card = {}
    try:
        raw_card = (load_learn_writer_view().get("capabilities") or {}).get(capability_id)
        if isinstance(raw_card, Mapping):
            card = dict(raw_card)
    except Exception:  # noqa: BLE001
        card = {}
    from core.prompts.loader import effective_prompt_text, hash_prompt

    definition = dict(request.get("authoring_definition") or card)
    schema = request.get("payload_schema") or card.get("payload_schema") or {}
    base_instructions = (
        request.get("instructions") or definition.get("instructions") or card.get("instructions")
    )
    policy = effective_prompt_text("interaction-writer")
    if isinstance(base_instructions, Mapping):
        base_text = str(base_instructions.get("text") or "")
    else:
        base_text = str(base_instructions or "")
    instructions = f"{policy}\n\n{base_text}".strip() if base_text else policy
    required_inputs = request.get("required_inputs") or card.get("required_inputs") or []
    modes = request.get("modes") or card.get("modes") or ["generate", "convert-approved"]
    validator_refs = request.get("validator_refs") or card.get("validator_refs") or []
    contract_hash = str(
        request.get("capability_contract_hash")
        or card.get("definition_hash")
        or hash_prompt(instructions)
    )

    approved_items = request.get("approved_items")
    approved_ids: list[str] = []
    if isinstance(approved_items, Sequence) and not isinstance(approved_items, (str, bytes)):
        for item in approved_items:
            if isinstance(item, Mapping) and item.get("id"):
                approved_ids.append(str(item["id"]))
            elif getattr(item, "id", None):
                approved_ids.append(str(item.id))

    return LearnWorkOrder(
        work_order_id=str(request.get("work_order_id") or f"learn::request::{capability_id}"),
        block_id=str(request.get("block_id") or "block"),
        section_id=str(request.get("section_id") or "section"),
        lane="interaction",
        capability_id=capability_id,
        teaching_plan_id=str(request.get("teaching_plan_id") or "ad-hoc"),
        teaching_plan_revision=int(request.get("teaching_plan_revision") or 1),
        teaching_plan_hash=str(request.get("teaching_plan_hash") or "ad-hoc"),
        capability_contract_hash=contract_hash,
        source_refs=[str(item) for item in request.get("source_refs") or []],
        dependency_ids=[str(item) for item in request.get("dependency_ids") or []],
        expected_output_schema=dict(schema),
        field_guidance=dict(request.get("field_guidance") or card.get("field_guidance") or {}),
        authoring_definition=definition,
        instructions=instructions,
        required_inputs=list(required_inputs),
        modes=list(modes),
        validator_refs=list(validator_refs),
        brief=str(request.get("brief") or ""),
        intent=str(request.get("intent") or ""),
        action=request.get("action") if isinstance(request.get("action"), str) else None,
        evidence=str(request.get("evidence") or ""),
        support_level=request.get("support_level") if isinstance(request.get("support_level"), str) else None,
        authoring_mode="approved_item" if approved_ids else "new",
        approved_item_ids=approved_ids,
        shared_task=(
            dict(request["shared_task"])
            if isinstance(request.get("shared_task"), Mapping)
            else None
        ),
    )


async def write_interaction_from_request_async(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    mode: str | None = None,
    budget_ledger: Any | None = None,
    checkpoint_store: Any | None = None,
    durable_persist_hook: Any | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
) -> dict[str, Any]:
    """Async interaction authoring — safe to await from the running event loop."""
    # The provider-call budget is per logical interaction work item.  A
    # capability (for example ``choice``) may legitimately appear more than
    # once in one lesson, so falling back to capability alone would make
    # unrelated tasks consume one another's retry budget.
    if not request.get("work_order_id") and interaction_id:
        request = dict(request)
        request["work_order_id"] = f"learn::interaction::{interaction_id}"
    order = _work_order_from_request(request)
    approved_items_raw = request.get("approved_items") or []
    approved_items = [
        dict(item) if isinstance(item, Mapping) else vars(item)
        for item in approved_items_raw
    ]
    lesson_context = (
        dict(request["lesson_context"])
        if isinstance(request.get("lesson_context"), Mapping)
        else {}
    )
    if not str(lesson_context.get("objective") or "").strip():
        lesson_context["objective"] = str(
            request.get("brief") or order.brief or order.intent or "Learn objective"
        ).strip()
    allowed_facts_raw = request.get("allowed_facts")
    if not isinstance(allowed_facts_raw, Sequence) or isinstance(
        allowed_facts_raw, (str, bytes)
    ):
        allowed_facts = None
    else:
        allowed_facts = list(allowed_facts_raw)
    terminology = (
        list(request["terminology"])
        if isinstance(request.get("terminology"), Sequence)
        and not isinstance(request.get("terminology"), (str, bytes))
        else None
    )
    selected_engine = engine or AuthoringEngine(
        registry=build_learn_authoring_registry(),
        provider=provider,
        budget_ledger=budget_ledger,
        progress_store=progress_store,
        progress_run_id=progress_run_id,
        progress_stage="interaction",
        durable_persist_hook=durable_persist_hook,
    )
    if durable_persist_hook is not None and getattr(
        selected_engine, "durable_persist_hook", None
    ) is None:
        selected_engine.durable_persist_hook = durable_persist_hook
    if budget_ledger is not None and getattr(selected_engine, "budget_ledger", None) is None:
        selected_engine.budget_ledger = budget_ledger
    checkpoint_key = f"interaction:{interaction_id or order.work_order_id}"
    compat = None
    try:
        if checkpoint_store is not None:
            from infra.execution.checkpoints import CheckpointCompatibility, content_hash

            compat = CheckpointCompatibility(
                teaching_revision=int(order.teaching_plan_revision or 1),
                input_hash=content_hash(
                    {
                        "capability_id": order.capability_id,
                        "brief": order.brief,
                        "intent": order.intent,
                        "action": getattr(order, "action", None),
                        "allowed_facts": allowed_facts or [],
                        "terminology": terminology or [],
                        "interaction_id": interaction_id or order.work_order_id,
                        "block_id": getattr(order, "block_id", None),
                    }
                ),
                definition_hash=str(order.capability_id or ""),
                composition_identity=str(interaction_id or order.work_order_id),
            )
            prior = checkpoint_store.get(checkpoint_key)
            if prior is not None and prior.status == "ready" and prior.payload is not None:
                checkpoint_store.decide_resume(checkpoint_key, compatibility=compat)
                return dict(prior.payload)
            checkpoint_store.begin(checkpoint_key, compatibility=compat)

        result = await run_learn_authoring(
            order,
            provider=provider,
            engine=selected_engine,
            lesson_context=lesson_context,
            allowed_facts=allowed_facts,
            terminology=terminology,
            approved_items=approved_items,
            mode=mode,
            requested_knowledge_policy=(
                str(request["requested_knowledge_policy"])
                if request.get("requested_knowledge_policy")
                else None
            ),
            requested_assessment_policy=(
                str(request["requested_assessment_policy"])
                if request.get("requested_assessment_policy")
                else None
            ),
        )
        from learn.generation.source_resolver import resolve_learn_work_order_sources

        resolved = resolve_learn_work_order_sources(
            order, approved_items, forced_mode=mode
        )
        contract = interaction_contract_from_authoring_result(
            order,
            result,
            interaction_id=interaction_id,
            assessment_mode=assessment_mode,
            concept_refs=concept_refs,
            approved_item=(
                resolved.primary_item if result.mode == "convert-approved" else None
            ),
        )
        if checkpoint_store is not None and compat is not None:
            checkpoint_store.commit(
                checkpoint_key,
                payload=dict(contract),
                compatibility=compat,
            )
    except Exception as exc:
        if checkpoint_store is not None:
            try:
                checkpoint_store.mark_ambiguous(checkpoint_key)
            except Exception:
                logger = __import__("logging").getLogger(__name__)
                logger.debug(
                    "interaction checkpoint mark_ambiguous failed", exc_info=True
                )
        raise _as_writer_error(exc) from exc
    errors = validate_interaction_contract(contract)
    if errors:
        raise InteractionWriterError("CONTRACT_INVALID", "; ".join(errors))
    return contract


def write_interaction_from_request(
    request: Mapping[str, Any],
    *,
    interaction_id: str | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    mode: str | None = None,
    budget_ledger: Any | None = None,
    checkpoint_store: Any | None = None,
    durable_persist_hook: Any | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
) -> dict[str, Any]:
    """Author one interaction through the shared engine.

    Generate mode requires a configured provider or engine. Convert-approved mode
    is deterministic, but still goes through the engine converter and validators.
    Sync entry for tests; prefer ``write_interaction_from_request_async`` under
    a running event loop so durable persist hooks stay on the same loop.
    """
    return _run_sync(
        write_interaction_from_request_async(
            request,
            interaction_id=interaction_id,
            assessment_mode=assessment_mode,
            concept_refs=concept_refs,
            provider=provider,
            engine=engine,
            mode=mode,
            budget_ledger=budget_ledger,
            checkpoint_store=checkpoint_store,
            durable_persist_hook=durable_persist_hook,
            progress_store=progress_store,
            progress_run_id=progress_run_id,
        )
    )


def write_interaction_from_work_order(
    order: LearnWorkOrder,
    *,
    allowed_facts: Sequence[str] | None = None,
    lesson_context: Mapping[str, Any] | None = None,
    terminology: Sequence[str] | None = None,
    assessment_mode: str = "practice",
    concept_refs: Sequence[Mapping[str, Any]] | None = None,
    approved_items: Sequence[Any] | Mapping[str, Any] | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
) -> tuple[ActivityAuthoringPlan, dict[str, Any], dict[str, Any]]:
    """Plan, author and wrap one interaction through the shared engine."""
    if order.lane != "interaction":
        raise InteractionWriterError("LANE_MISMATCH", "content work orders use content writers")
    plan = plan_activity_authoring(order, approved_items=approved_items)
    if isinstance(approved_items, Mapping):
        approved_seq = [
            dict(item) if isinstance(item, Mapping) else vars(item)
            for item in approved_items.values()
        ]
    else:
        approved_seq = [
            dict(item) if isinstance(item, Mapping) else vars(item)
            for item in (approved_items or [])
        ]
    context = dict(lesson_context or {})
    if not str(context.get("objective") or "").strip():
        context["objective"] = order.brief.strip() or order.intent or "Learn objective"
    if allowed_facts is None:
        facts: list[str] | None = None
    else:
        facts = list(allowed_facts)
    try:
        result = _run_sync(
            run_learn_authoring(
                order,
                provider=provider,
                engine=engine,
                lesson_context=context,
                allowed_facts=facts,
                terminology=terminology,
                approved_items=approved_seq,
            )
        )
        from learn.generation.source_resolver import resolve_learn_work_order_sources

        resolved = resolve_learn_work_order_sources(order, approved_seq)
        payload = interaction_contract_from_authoring_result(
            order,
            result,
            assessment_mode=assessment_mode,
            concept_refs=concept_refs,
            approved_item=resolved.primary_item if result.mode == "convert-approved" else None,
        )
    except Exception as exc:
        raise _as_writer_error(exc) from exc
    request = {
        "work_order_id": order.work_order_id,
        "capability_id": order.capability_id,
        "authoring_mode": result.mode,
    }
    return plan, request, payload


def interaction_payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

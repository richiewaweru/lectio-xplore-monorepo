from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from infra.authoring.models import (
    AuthoringDefinition,
    AuthoringEngineError,
    AuthoringMode,
    AuthoringProvenance,
    AuthoringProvider,
    AuthoringProviderCall,
    AuthoringRequest,
    AuthoringResult,
    AuthoringTransportError,
    AuthoringValidationError,
    Converter,
    Validator,
)
from infra.authoring.prompts import build_authoring_prompt, build_repair_prompt
from infra.authoring.validation import validate_json_schema
from infra.execution.call_budget import (
    DEFAULT_MAX_PROVIDER_CALLS,
    BudgetExhaustedError,
    CallBudget,
    CallBudgetLedger,
)
from infra.execution.error_policy import classify_provider_error
from infra.execution.progress import ProgressStore, TraceExporter, prompt_hash_for


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_usage(
    result: object | None,
) -> tuple[int | None, int | None, float | None, str | None, str | None]:
    """Pull token/cost/model metadata when present; unknown stays None (never 0)."""
    if result is None:
        return None, None, None, None, None
    usage = None
    model = None
    provider_request_id = None
    if isinstance(result, Mapping):
        usage = result.get("usage")
        model = result.get("model") or result.get("model_name")
        provider_request_id = result.get("provider_request_id") or result.get("request_id")
    else:
        usage = getattr(result, "usage", None)
        model = getattr(result, "model", None) or getattr(result, "model_name", None)
        provider_request_id = getattr(result, "provider_request_id", None) or getattr(
            result, "request_id", None
        )
    tokens_in = tokens_out = cost_usd = None
    if isinstance(usage, Mapping):
        if "tokens_in" in usage or "input_tokens" in usage or "prompt_tokens" in usage:
            raw_in = usage.get("tokens_in", usage.get("input_tokens", usage.get("prompt_tokens")))
            tokens_in = int(raw_in) if raw_in is not None else None
        if "tokens_out" in usage or "output_tokens" in usage or "completion_tokens" in usage:
            raw_out = usage.get(
                "tokens_out", usage.get("output_tokens", usage.get("completion_tokens"))
            )
            tokens_out = int(raw_out) if raw_out is not None else None
        if "cost_usd" in usage or "cost" in usage:
            raw_cost = usage.get("cost_usd", usage.get("cost"))
            cost_usd = float(raw_cost) if raw_cost is not None else None
    return tokens_in, tokens_out, cost_usd, str(model) if model else None, (
        str(provider_request_id) if provider_request_id else None
    )

def _coerce_json_object(raw: object) -> dict[str, Any]:
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump(mode="json")
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        raw = json.loads(text)
    if not isinstance(raw, dict):
        raise TypeError(f"expected JSON object, got {type(raw).__name__}")
    return raw


def _missing(value: Any) -> bool:
    return value is None


def _definition_hash(definition: AuthoringDefinition) -> str:
    if definition.definition_hash:
        return definition.definition_hash
    return stable_hash(
        {
            "capability_id": definition.capability_id,
            "native_path": definition.native_path,
            "modes": list(definition.modes),
            "instructions": definition.instructions,
            "payload_schema": dict(definition.payload_schema),
            "required_inputs": list(definition.required_inputs),
            "validator_refs": list(definition.validator_refs),
            "converter_ref": definition.converter_ref,
            "raw": dict(definition.raw),
        }
    )


def provenance_for(request: AuthoringRequest) -> AuthoringProvenance:
    definition_hash = _definition_hash(request.definition) if request.definition else ""
    return AuthoringProvenance(
        work_order_id=request.work_order_id,
        source_identities=tuple(request.source_identities),
        teaching_revision=request.teaching_revision,
        definition_hash=definition_hash,
        input_hash=stable_hash(
            {
                "scoped_request": dict(request.scoped_request),
                "inputs": dict(request.inputs),
                "mode": request.mode,
                "approved_item": dict(request.approved_item or {}),
                "policy": dict(request.policy or {}),
            }
        ),
        policy=dict(request.policy) if request.policy is not None else None,
    )


@dataclass
class AuthoringRegistry:
    validators: dict[str, Validator] = field(default_factory=dict)
    converters: dict[str, Converter] = field(default_factory=dict)

    def with_validator(self, ref: str, validator: Validator) -> AuthoringRegistry:
        self.validators[ref] = validator
        return self

    def with_converter(self, ref: str, converter: Converter) -> AuthoringRegistry:
        self.converters[ref] = converter
        return self


class LLMAuthoringProvider:
    def __init__(self, *, node_name: str = "v3_block_writer_fast") -> None:
        self.node_name = node_name

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        from v3_execution.llm_helpers import run_structured_agent

        # Nested SDK/output retries multiply the durable work-item call budget.
        # AuthoringEngine owns repair attempts; each invoke is one counted call.
        try:
            return await run_structured_agent(
                node_name=self.node_name,
                trace_id=call.work_order_id,
                generation_id=None,
                system_prompt=call.prompt,
                user_prompt="Return JSON only for the selected capability payload.",
                output_schema=dict(call.output_schema),
                repair_attempts=0,
                retries={"output": 0},
            )
        except AuthoringTransportError:
            raise
        except Exception as exc:
            raise AuthoringTransportError(str(exc)) from exc


@dataclass
class AuthoringEngine:
    registry: AuthoringRegistry = field(default_factory=AuthoringRegistry)
    provider: AuthoringProvider | None = None
    # Soft caps within the durable CallBudget (default max 3 real dispatches).
    max_transport_attempts: int = 1
    max_repair_attempts: int = 2
    max_provider_calls: int = DEFAULT_MAX_PROVIDER_CALLS
    call_budget: CallBudget | None = None
    budget_ledger: CallBudgetLedger | None = None
    # P04: optional durable progress / soft trace exporter (never blocks generation).
    progress_store: ProgressStore | None = None
    progress_run_id: str | None = None
    progress_stage: str = "writing"
    trace_exporter: TraceExporter | None = None

    async def execute(
        self,
        request: AuthoringRequest,
        *,
        provider: AuthoringProvider | None = None,
        call_budget: CallBudget | None = None,
    ) -> AuthoringResult:
        definition = self._resolve_definition(request)
        effective = self._with_selected_mode(request, definition)
        provenance = provenance_for(effective)
        self._validate_required_inputs(effective, definition, provenance)
        self._validate_registered_refs(definition, provenance)
        budget = self._resolve_budget(effective, call_budget)

        if effective.mode == "convert-approved":
            payload = self._convert_approved(effective, definition, provenance)
            errors = await self._validate_payload(definition, effective, payload)
            if errors:
                raise AuthoringEngineError(
                    "INCOMPATIBLE_APPROVED_ITEM",
                    "approved item did not convert to a valid payload",
                    stage="convert",
                    errors=errors,
                    provenance=provenance,
                )
            return AuthoringResult(
                work_order_id=effective.work_order_id,
                capability_id=definition.capability_id,
                native_path=definition.native_path,
                mode="convert-approved",
                payload=payload,
                provenance=provenance,
                transport_attempts=0,
                repair_attempts=0,
            )

        selected_provider = provider or self.provider
        if selected_provider is None:
            raise AuthoringEngineError(
                "NO_COMPATIBLE_CAPABILITY",
                "no provider configured for generate mode",
                stage="provider",
                retryable=True,
                provenance=provenance,
            )

        prompt = build_authoring_prompt(definition=definition, request=effective)
        raw, transport_attempts = await self._invoke_provider(
            selected_provider,
            definition=definition,
            request=effective,
            prompt=prompt,
            is_repair=False,
            base_attempt=1,
            provenance=provenance,
            budget=budget,
        )
        payload, errors, previous_output = await self._parse_and_validate(
            definition,
            effective,
            raw,
        )
        repair_attempts = 0
        while errors and repair_attempts < self.max_repair_attempts:
            if budget.remaining <= 0:
                break
            repair_attempts += 1
            repair_prompt = build_repair_prompt(
                definition=definition,
                request=effective,
                previous_output=previous_output,
                errors=errors,
            )
            raw, extra_transport_attempts = await self._invoke_provider(
                selected_provider,
                definition=definition,
                request=effective,
                prompt=repair_prompt,
                is_repair=True,
                base_attempt=1 + repair_attempts,
                provenance=provenance,
                budget=budget,
            )
            transport_attempts += extra_transport_attempts
            payload, errors, previous_output = await self._parse_and_validate(
                definition,
                effective,
                raw,
            )

        if errors:
            code = "REPAIR_EXHAUSTED" if self.max_repair_attempts > 0 else "INVALID_PAYLOAD"
            raise AuthoringEngineError(
                code,
                "provider output did not satisfy the selected definition",
                stage="repair" if code == "REPAIR_EXHAUSTED" else "validate",
                errors=errors,
                provenance=provenance,
                transport_attempts=transport_attempts,
                repair_attempts=repair_attempts,
            )

        return AuthoringResult(
            work_order_id=effective.work_order_id,
            capability_id=definition.capability_id,
            native_path=definition.native_path,
            mode="generate",
            payload=payload,
            provenance=provenance,
            transport_attempts=transport_attempts,
            repair_attempts=repair_attempts,
        )

    def _resolve_budget(
        self,
        request: AuthoringRequest,
        call_budget: CallBudget | None,
    ) -> CallBudget:
        if call_budget is not None:
            budget = call_budget
        elif self.call_budget is not None:
            budget = self.call_budget
        elif self.budget_ledger is not None:
            budget = self.budget_ledger.get_or_create(
                request.work_order_id,
                max_calls=self.max_provider_calls,
            )
        else:
            budget = CallBudget(
                work_item_id=request.work_order_id,
                max_calls=self.max_provider_calls,
            )
        if self.budget_ledger is not None:
            self.budget_ledger.persist(budget)
        return budget

    def _persist_budget(self, budget: CallBudget) -> None:
        if self.budget_ledger is not None:
            self.budget_ledger.persist(budget)

    def _resolve_definition(self, request: AuthoringRequest) -> AuthoringDefinition:
        definition = request.definition
        if definition is None:
            raise AuthoringEngineError(
                "MISSING_AUTHORING_DEFINITION",
                "authoring request has no selected definition",
                stage="definition",
            )
        if not definition.capability_id or not definition.native_path:
            raise AuthoringEngineError(
                "MISSING_AUTHORING_DEFINITION",
                "authoring definition is missing identity",
                stage="definition",
            )
        if not definition.payload_schema or not definition.instructions.strip():
            raise AuthoringEngineError(
                "MISSING_AUTHORING_DEFINITION",
                "authoring definition is incomplete",
                stage="definition",
            )
        return definition

    def _with_selected_mode(
        self,
        request: AuthoringRequest,
        definition: AuthoringDefinition,
    ) -> AuthoringRequest:
        modes = set(definition.modes)
        selected: AuthoringMode | None = request.mode
        if selected is None:
            selected = "convert-approved" if request.approved_item is not None else "generate"
        if selected not in modes:
            raise AuthoringEngineError(
                "NO_COMPATIBLE_CAPABILITY",
                f"mode {selected!r} is not permitted for {definition.capability_id!r}",
                stage="mode",
            )
        return AuthoringRequest(
            work_order_id=request.work_order_id,
            definition=definition,
            scoped_request=request.scoped_request,
            inputs=request.inputs,
            teaching_revision=request.teaching_revision,
            source_identities=request.source_identities,
            mode=selected,
            approved_item=request.approved_item,
            trace_id=request.trace_id,
            generation_id=request.generation_id,
            policy=request.policy,
        )

    def _validate_required_inputs(
        self,
        request: AuthoringRequest,
        definition: AuthoringDefinition,
        provenance: AuthoringProvenance,
    ) -> None:
        assert request.mode is not None
        missing = []
        for name in definition.required_inputs:
            if name.endswith("_when_converting") and request.mode != "convert-approved":
                continue
            if name not in request.inputs or _missing(request.inputs.get(name)):
                missing.append(name)
        if missing:
            raise AuthoringEngineError(
                "MISSING_AUTHORING_INPUT",
                f"missing required authoring input(s): {', '.join(missing)}",
                stage="inputs",
                errors=[
                    AuthoringValidationError(name, "missing required input")
                    for name in missing
                ],
                provenance=provenance,
            )

    def _validate_registered_refs(
        self,
        definition: AuthoringDefinition,
        provenance: AuthoringProvenance,
    ) -> None:
        unknown = [
            ref for ref in definition.validator_refs if ref not in self.registry.validators
        ]
        if unknown:
            raise AuthoringEngineError(
                "MISSING_AUTHORING_DEFINITION",
                f"unknown validator ref(s): {', '.join(unknown)}",
                stage="definition",
                provenance=provenance,
            )

    def _convert_approved(
        self,
        request: AuthoringRequest,
        definition: AuthoringDefinition,
        provenance: AuthoringProvenance,
    ) -> dict[str, Any]:
        if request.approved_item is None:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                "convert-approved mode requires an approved item",
                stage="convert",
                provenance=provenance,
            )
        converter_ref = definition.converter_ref
        if not converter_ref or converter_ref not in self.registry.converters:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                "no registered converter for selected definition",
                stage="convert",
                provenance=provenance,
            )
        try:
            return dict(self.registry.converters[converter_ref](definition, request))
        except AuthoringEngineError:
            raise
        except Exception as exc:
            raise AuthoringEngineError(
                "INCOMPATIBLE_APPROVED_ITEM",
                str(exc),
                stage="convert",
                provenance=provenance,
            ) from exc

    async def _invoke_provider(
        self,
        provider: AuthoringProvider,
        *,
        definition: AuthoringDefinition,
        request: AuthoringRequest,
        prompt: str,
        is_repair: bool,
        base_attempt: int,  # kept for call-site compatibility; budget owns attempt ids
        provenance: AuthoringProvenance,
        budget: CallBudget,
    ) -> tuple[object, int]:
        assert request.mode is not None
        _ = base_attempt
        attempts = 0
        last_classified = None
        while attempts < self.max_transport_attempts:
            attempts += 1
            try:
                reserved = budget.reserve()
            except BudgetExhaustedError as exc:
                raise AuthoringEngineError(
                    "BUDGET_EXHAUSTED",
                    str(exc),
                    stage="provider",
                    retryable=False,
                    provenance=provenance,
                    transport_attempts=attempts - 1,
                ) from exc
            self._persist_budget(budget)
            call = AuthoringProviderCall(
                work_order_id=request.work_order_id,
                capability_id=definition.capability_id,
                native_path=definition.native_path,
                mode=request.mode,
                attempt=reserved,
                is_repair=is_repair,
                prompt=prompt,
                output_schema=definition.payload_schema,
            )
            try:
                result = await provider.invoke(call)
            except AuthoringTransportError as exc:
                # Dispatch occurred (or ambiguous). Never release the slot as free.
                budget.mark_ambiguous(reserved)
                self._persist_budget(budget)
                self._record_model_call(
                    request=request,
                    definition=definition,
                    prompt=prompt,
                    attempt=reserved,
                    result=None,
                )
                last_classified = classify_provider_error(exc)
                if not last_classified.retryable or attempts >= self.max_transport_attempts:
                    raise AuthoringEngineError(
                        "NO_COMPATIBLE_CAPABILITY",
                        "provider transport attempts exhausted",
                        stage="provider",
                        retryable=last_classified.retryable,
                        provenance=provenance,
                        transport_attempts=attempts,
                    ) from exc
                await asyncio.sleep(0)
                continue
            except BaseException:
                budget.mark_ambiguous(reserved)
                self._persist_budget(budget)
                raise
            else:
                budget.mark_dispatched(reserved)
                self._persist_budget(budget)
                self._record_model_call(
                    request=request,
                    definition=definition,
                    prompt=prompt,
                    attempt=reserved,
                    result=result,
                )
                return result, attempts
        raise AssertionError("unreachable provider retry state")

    def _record_model_call(
        self,
        *,
        request: AuthoringRequest,
        definition: AuthoringDefinition,
        prompt: str,
        attempt: int,
        result: object | None,
    ) -> None:
        store = self.progress_store
        run_id = self.progress_run_id or request.trace_id or request.generation_id
        if store is None or not run_id:
            return
        tokens_in, tokens_out, cost_usd, model, provider_request_id = _extract_usage(result)
        policy = request.policy or {}
        composition_mode = None
        if isinstance(policy, Mapping):
            raw_mode = policy.get("composition_mode")
            composition_mode = str(raw_mode) if raw_mode is not None else None
            policy_hash = (
                str(policy.get("policy_hash"))
                if policy.get("policy_hash") is not None
                else None
            )
        else:
            policy_hash = None
        try:
            store.ensure_run(
                run_id,
                path=definition.native_path,
                owner_user_id=str((request.scoped_request or {}).get("user_id") or "system"),
                stage=self.progress_stage,
            )
            store.record_model_call(
                run_id,
                path=definition.native_path,
                stage=self.progress_stage,
                item_id=request.work_order_id,
                attempt=attempt,
                model=model,
                prompt_hash=prompt_hash_for(prompt),
                policy_hash=policy_hash,
                composition_mode=composition_mode,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                provider_request_id=provider_request_id,
            )
        except Exception:  # noqa: BLE001 — observability must never halt authoring
            return
        if self.trace_exporter is not None:
            store.export_traces(run_id, self.trace_exporter)

    async def _parse_and_validate(
        self,
        definition: AuthoringDefinition,
        request: AuthoringRequest,
        raw: object,
    ) -> tuple[dict[str, Any], list[AuthoringValidationError], object]:
        try:
            payload = _coerce_json_object(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            return {}, [AuthoringValidationError("", str(exc))], raw
        errors = await self._validate_payload(definition, request, payload)
        return payload, errors, payload

    async def _validate_payload(
        self,
        definition: AuthoringDefinition,
        request: AuthoringRequest,
        payload: Mapping[str, Any],
    ) -> list[AuthoringValidationError]:
        errors = validate_json_schema(definition.payload_schema, payload)
        if errors:
            return errors
        for ref in definition.validator_refs:
            validator = self.registry.validators[ref]
            result = validator(definition, request, payload)
            if inspect.isawaitable(result):
                result = await result
            if result:
                errors.extend(result)
        return errors

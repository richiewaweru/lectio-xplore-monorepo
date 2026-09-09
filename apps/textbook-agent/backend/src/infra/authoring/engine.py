from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from infra.authoring.models import (
    AuthoringDefinition,
    AuthoringEngineError,
    AuthoringMode,
    AuthoringProvider,
    AuthoringProviderCall,
    AuthoringProvenance,
    AuthoringRequest,
    AuthoringResult,
    AuthoringTransportError,
    AuthoringValidationError,
    Converter,
    Validator,
)
from infra.authoring.prompts import build_authoring_prompt, build_repair_prompt
from infra.authoring.validation import validate_json_schema


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        raise ValueError(f"expected JSON object, got {type(raw).__name__}")
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
            }
        ),
    )


@dataclass
class AuthoringRegistry:
    validators: dict[str, Validator] = field(default_factory=dict)
    converters: dict[str, Converter] = field(default_factory=dict)

    def with_validator(self, ref: str, validator: Validator) -> "AuthoringRegistry":
        self.validators[ref] = validator
        return self

    def with_converter(self, ref: str, converter: Converter) -> "AuthoringRegistry":
        self.converters[ref] = converter
        return self


class LLMAuthoringProvider:
    def __init__(self, *, node_name: str = "v3_block_writer_fast") -> None:
        self.node_name = node_name

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        from v3_execution.llm_helpers import run_structured_agent

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


@dataclass
class AuthoringEngine:
    registry: AuthoringRegistry = field(default_factory=AuthoringRegistry)
    provider: AuthoringProvider | None = None
    max_transport_attempts: int = 2
    max_repair_attempts: int = 1

    async def execute(
        self,
        request: AuthoringRequest,
        *,
        provider: AuthoringProvider | None = None,
    ) -> AuthoringResult:
        definition = self._resolve_definition(request)
        effective = self._with_selected_mode(request, definition)
        provenance = provenance_for(effective)
        self._validate_required_inputs(effective, definition, provenance)
        self._validate_registered_refs(definition, provenance)

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
        )
        payload, errors, previous_output = await self._parse_and_validate(
            definition,
            effective,
            raw,
        )
        repair_attempts = 0
        while errors and repair_attempts < self.max_repair_attempts:
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
        base_attempt: int,
        provenance: AuthoringProvenance,
    ) -> tuple[object, int]:
        assert request.mode is not None
        attempts = 0
        while attempts < self.max_transport_attempts:
            attempts += 1
            call = AuthoringProviderCall(
                work_order_id=request.work_order_id,
                capability_id=definition.capability_id,
                native_path=definition.native_path,
                mode=request.mode,
                attempt=base_attempt,
                is_repair=is_repair,
                prompt=prompt,
                output_schema=definition.payload_schema,
            )
            try:
                return await provider.invoke(call), attempts
            except AuthoringTransportError:
                if attempts >= self.max_transport_attempts:
                    raise AuthoringEngineError(
                        "NO_COMPATIBLE_CAPABILITY",
                        "provider transport attempts exhausted",
                        stage="provider",
                        retryable=True,
                        provenance=provenance,
                        transport_attempts=attempts,
                    )
                await asyncio.sleep(0)
        raise AssertionError("unreachable provider retry state")

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

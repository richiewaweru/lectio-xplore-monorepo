from __future__ import annotations

import json
from typing import Any, Mapping

from infra.authoring.models import (
    AuthoringDefinition,
    AuthoringRequest,
    AuthoringValidationError,
)

COMMON_AUTHORING_TEMPLATE = """You author one already-selected educational capability. Follow the
supplied AuthoringDefinition and exact output schema. Preserve block identity, objective, scope,
learner action, source ownership and assessment mode. Do not select another capability or redesign
the teaching plan.

Write final student-facing material using the supplied facts and terminology. Planning instructions
are not final content. For an activity, produce a meaningful prompt, task data, justified answer
relationships and useful feedback as required by the contract. Do not infer correctness from option
positions, number/word positions, example ordering or arbitrary defaults. Do not copy illustrative
examples as unrelated lesson content.

Treat approved items as authoritative content. Conversion must preserve their question and answer
meaning. Report incompatibility through the defined error path instead of guessing. Use supported
teacher-review only when the work order permits it.

Return exactly the selected output schema. Do not emit sibling schemas, markdown wrappers, internal
planning metadata or extra fields. If required information is absent, use the configured
missing-input mechanism; do not create placeholder content to satisfy structure."""

REPAIR_TEMPLATE = """Correct only the supplied failed result for this work order. Preserve the
original objective, source facts, selected capability and valid answer relationships. The original
scoped request and authoritative definition are attached, followed by the previous output and
errors with field paths.
Return the complete corrected payload in the same schema. Do not remove required tasks, replace the
activity type, invent a new answer key, or discard approved sources to make validation pass. If the
input is insufficient, use the configured missing-input/error contract. Repairs are bounded by the
engine; do not implement an unbounded self-retry loop."""


def _definition_prompt_payload(definition: AuthoringDefinition) -> dict[str, Any]:
    return {
        "capability_id": definition.capability_id,
        "native_path": definition.native_path,
        "modes": list(definition.modes),
        "instructions": definition.instructions,
        "payload_schema": dict(definition.payload_schema),
        "required_inputs": list(definition.required_inputs),
        "validator_refs": list(definition.validator_refs),
        "converter_ref": definition.converter_ref,
        "definition_hash": definition.definition_hash,
    }


def build_authoring_prompt(
    *,
    definition: AuthoringDefinition,
    request: AuthoringRequest,
) -> str:
    payload = {
        "mode": request.mode,
        "scoped_request": dict(request.scoped_request),
        "inputs": dict(request.inputs),
    }
    if request.approved_item is not None:
        payload["approved_item"] = dict(request.approved_item)
    return "\n\n".join(
        [
            COMMON_AUTHORING_TEMPLATE,
            "## PACKAGE CAPABILITY INSTRUCTIONS\n" + definition.instructions,
            "## AUTHORING DEFINITION\n"
            + json.dumps(_definition_prompt_payload(definition), indent=2, sort_keys=True),
            "## SCOPED REQUEST\n" + json.dumps(payload, indent=2, sort_keys=True, default=str),
            "Return JSON only for this capability payload.",
        ]
    )


def build_repair_prompt(
    *,
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    previous_output: object,
    errors: list[AuthoringValidationError],
) -> str:
    payload: Mapping[str, Any] = {
        "scoped_request": dict(request.scoped_request),
        "inputs": dict(request.inputs),
        "authoring_definition": _definition_prompt_payload(definition),
        "previous_invalid_output": previous_output,
        "validation_errors": [error.to_dict() for error in errors],
    }
    if request.approved_item is not None:
        payload = {**payload, "approved_item": dict(request.approved_item)}
    return "\n\n".join(
        [
            REPAIR_TEMPLATE,
            "## REPAIR PAYLOAD\n" + json.dumps(payload, indent=2, sort_keys=True, default=str),
            "Return JSON only for the corrected capability payload.",
        ]
    )

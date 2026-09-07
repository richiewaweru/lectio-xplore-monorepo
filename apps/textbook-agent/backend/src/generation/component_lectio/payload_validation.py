"""Final exact Lectio payload validation before block_ready checkpoints."""

from __future__ import annotations

from typing import Any

from generation.component_lectio.errors import WorkOrderIdentityError
from v3_blueprint.planning.work_orders import ExactWorkOrder
from v3_execution.runtime.lectio_validation import validate_lectio_field_payload


class ExactPayloadValidationError(ValueError):
    """Portable content failed the exact Lectio section_field contract."""

    def __init__(
        self,
        *,
        component_id: str,
        section_field: str,
        errors: list[str],
        block_id: str | None = None,
    ) -> None:
        self.component_id = component_id
        self.section_field = section_field
        self.errors = list(errors)
        self.block_id = block_id
        detail = "; ".join(self.errors) if self.errors else "invalid Lectio content"
        super().__init__(
            f"Lectio contract validation failed for {component_id} "
            f"(field={section_field}): {detail}"
        )


def section_field_for(order: ExactWorkOrder) -> str:
    field = getattr(order, "section_field", None)
    if isinstance(field, str) and field.strip():
        return field.strip()
    card = order.component_card if isinstance(order.component_card, dict) else {}
    nested = card.get("section_field") or card.get("sectionField")
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    raise ExactPayloadValidationError(
        component_id=order.locked_component_id,
        section_field="",
        errors=[f"ExactWorkOrder {order.block_id} is missing section_field"],
        block_id=order.block_id,
    )


def validate_exact_payload(
    order: ExactWorkOrder,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Assert identity + exact Lectio field schema before block_ready."""
    if not isinstance(payload, dict):
        raise ExactPayloadValidationError(
            component_id=order.locked_component_id,
            section_field=section_field_for(order),
            errors=["payload must be an object"],
            block_id=order.block_id,
        )

    payload_component = payload.get("component_id")
    if payload_component != order.locked_component_id:
        raise WorkOrderIdentityError(
            f"Writer attempted to change component_id from "
            f"'{order.locked_component_id}' to '{payload_component}'"
        )

    payload_block = payload.get("block_id")
    if payload_block != order.block_id:
        raise WorkOrderIdentityError(
            f"Writer attempted to change block_id from "
            f"'{order.block_id}' to '{payload_block}'"
        )

    content = payload.get("content")
    if not isinstance(content, dict):
        raise ExactPayloadValidationError(
            component_id=order.locked_component_id,
            section_field=section_field_for(order),
            errors=["content must be an object"],
            block_id=order.block_id,
        )

    section_field = section_field_for(order)
    validated, errors = validate_lectio_field_payload(section_field, content)
    # validate_lectio_field_payload returns trim warnings mixed with errors;
    # only hard validation failures start with the field path or are ValidationError msgs.
    hard_errors = [err for err in errors if not str(err).startswith("trimmed:")]
    if hard_errors:
        raise ExactPayloadValidationError(
            component_id=order.locked_component_id,
            section_field=section_field,
            errors=hard_errors,
            block_id=order.block_id,
        )

    out = dict(payload)
    out["content"] = validated
    out["section_field"] = section_field
    out["component_id"] = order.locked_component_id
    out["block_id"] = order.block_id
    return out


__all__ = [
    "ExactPayloadValidationError",
    "section_field_for",
    "validate_exact_payload",
]

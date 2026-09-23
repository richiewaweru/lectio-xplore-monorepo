"""Generic LLM document writer — one ordinary primitive per call.

Teaching Plan briefs are writer instructions, never copied as student text.
Figure writes caption/alt only; assets use the existing figure pipeline.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import ValidationError

from document.models import (
    DOCUMENT_PRIMITIVE_KINDS,
    CalloutNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
)
from document.writer_prompts import (
    document_writer_prompt,
    document_writer_prompt_hash,
)
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringRequest,
    AuthoringValidationError,
)
from infra.authoring.engine import AuthoringRegistry
from infra.execution.call_budget import CallBudget, CallBudgetLedger
from infra.execution.checkpoints import (
    CheckpointCompatibility,
    CheckpointStore,
    content_hash,
)

DocumentPrimitiveKind = Literal[
    "paragraph", "heading", "list", "figure", "table", "callout"
]


class DocumentWriterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


_PRIMITIVE_SCHEMAS: dict[str, dict[str, Any]] = {
    "paragraph": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "text"],
        "properties": {
            "kind": {"const": "paragraph"},
            "text": {"type": "string", "minLength": 1},
        },
    },
    "heading": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "text", "level"],
        "properties": {
            "kind": {"const": "heading"},
            "text": {"type": "string", "minLength": 1},
            "level": {"type": "integer", "minimum": 1, "maximum": 3},
        },
    },
    "list": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "ordered", "items"],
        "properties": {
            "kind": {"const": "list"},
            "ordered": {"type": "boolean"},
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
        },
    },
    "table": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "headers", "rows"],
        "properties": {
            "kind": {"const": "table"},
            "headers": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 1},
            },
            "rows": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
            },
            "caption": {"type": "string"},
        },
    },
    "callout": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "tone", "body"],
        "properties": {
            "kind": {"const": "callout"},
            "tone": {"type": "string", "enum": ["note", "warning", "tip", "important"]},
            "title": {"type": "string"},
            "body": {"type": "string", "minLength": 1},
        },
    },
    "figure": {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "caption", "alt"],
        "properties": {
            "kind": {"const": "figure"},
            "caption": {"type": "string", "minLength": 1},
            "alt": {"type": "string", "minLength": 1},
        },
    },
}

_FORBIDDEN_PLACEHOLDERS = (
    "content pending",
    "option a",
    "option b",
    "row 1",
    "row 2",
    "item / detail",
)


def _noop_validator(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


def _looks_like_brief_copy(text: str, brief: str) -> bool:
    a = " ".join(text.lower().split())
    b = " ".join(brief.lower().split())
    if not a or not b:
        return False
    if a == b:
        return True
    # Near-verbatim copy of a long brief is also forbidden.
    return bool(len(b) >= 40 and (a.startswith(b[:40]) or b.startswith(a[:40])))


def _payload_quality_errors(kind: str, payload: Mapping[str, Any], *, brief: str) -> list[str]:
    errors: list[str] = []
    blob = " ".join(str(v) for v in payload.values() if isinstance(v, (str, int, float))).lower()
    for token in _FORBIDDEN_PLACEHOLDERS:
        if token in blob:
            errors.append(f"forbidden placeholder content detected: {token!r}")
    if kind == "table":
        headers = [str(h).strip().lower() for h in (payload.get("headers") or [])]
        if headers == ["item", "detail"]:
            errors.append("generic table headers Item/Detail are forbidden")
        for row in payload.get("rows") or []:
            if isinstance(row, list) and row and str(row[0]).lower().startswith("row "):
                errors.append("placeholder table row labels are forbidden")
                break
    texts: list[str] = []
    if kind in {"paragraph", "heading"}:
        texts.append(str(payload.get("text") or ""))
    elif kind == "callout":
        texts.append(str(payload.get("body") or ""))
    elif kind == "figure":
        texts.extend([str(payload.get("caption") or ""), str(payload.get("alt") or "")])
    elif kind == "list":
        texts.extend(str(i) for i in (payload.get("items") or []))
    for text in texts:
        if _looks_like_brief_copy(text, brief):
            errors.append("learner-facing text must not copy the Teaching Plan brief")
            break
    return errors


def _definition_for(kind: DocumentPrimitiveKind) -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id=f"document-writer:{kind}",
        native_path="document",
        modes=("generate",),
        instructions=document_writer_prompt(),
        payload_schema=_PRIMITIVE_SCHEMAS[kind],
        required_inputs=("kind", "brief", "teaching_block"),
        validator_refs=("document.writer_schema", "document.writer_quality"),
        definition_hash=f"{document_writer_prompt_hash()}:{kind}",
    )


def _document_quality_validator(
    definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    del definition
    kind = str(request.inputs.get("kind") or "")
    brief = str(request.inputs.get("brief") or "")
    errors = _payload_quality_errors(kind, payload, brief=brief)
    if not errors:
        teaching_block = request.inputs.get("teaching_block")
        teaching_block_id = (
            str(teaching_block.get("id") or "validation-block")
            if isinstance(teaching_block, Mapping)
            else "validation-block"
        )
        try:
            _normalize_payload(
                kind,  # type: ignore[arg-type]
                payload,
                node_id="validation-node",
                teaching_block_id=teaching_block_id,
            )
        except (ValidationError, DocumentWriterError, TypeError, ValueError) as exc:
            errors.append(f"normalized document node is invalid: {exc}")
    return [AuthoringValidationError("", error) for error in errors]


def _normalize_payload(
    kind: DocumentPrimitiveKind,
    payload: Mapping[str, Any],
    *,
    node_id: str,
    teaching_block_id: str | None,
) -> dict[str, Any]:
    data = dict(payload)
    data["kind"] = kind
    data["id"] = node_id
    data["teaching_block_id"] = teaching_block_id
    # Validate against pydantic models for the six primitives.
    if kind == "paragraph":
        return ParagraphNode.model_validate(data).model_dump(mode="json")
    if kind == "heading":
        return HeadingNode.model_validate(data).model_dump(mode="json")
    if kind == "list":
        return ListNode.model_validate(data).model_dump(mode="json")
    if kind == "table":
        return TableNode.model_validate(data).model_dump(mode="json")
    if kind == "callout":
        return CalloutNode.model_validate(data).model_dump(mode="json")
    if kind == "figure":
        return FigureNode.model_validate(data).model_dump(mode="json")
    raise DocumentWriterError("UNSUPPORTED_KIND", f"unsupported kind {kind!r}")


async def write_document_primitive(
    *,
    kind: str,
    brief: str,
    teaching_block: Mapping[str, Any],
    lesson_context: Mapping[str, Any] | None = None,
    evidence: str | None = None,
    allowed_facts: Sequence[str] | None = None,
    sourcebook_entries: Sequence[Mapping[str, Any]] | None = None,
    terminology: Sequence[str] | None = None,
    neighbour_summaries: Sequence[Mapping[str, Any]] | None = None,
    teaching_block_id: str | None = None,
    node_id: str | None = None,
    role: str | None = None,
    reason: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    work_order_id: str | None = None,
    call_budget: CallBudget | None = None,
    budget_ledger: CallBudgetLedger | None = None,
    checkpoint_store: CheckpointStore | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
    progress_stage: str = "writing",
    durable_persist_hook: Any | None = None,
) -> dict[str, Any]:
    """Write one ordinary document node using the LLM authoring engine."""
    if kind not in DOCUMENT_PRIMITIVE_KINDS:
        raise DocumentWriterError("UNSUPPORTED_KIND", f"unsupported kind {kind!r}")
    if provider is None and (engine is None or engine.provider is None):
        raise DocumentWriterError(
            "NO_PROVIDER",
            "document writer requires an authoring provider — brief-copy stubs are forbidden",
        )

    nid = node_id or f"node-{uuid.uuid4().hex[:12]}"
    block_id = teaching_block_id or str(teaching_block.get("id") or "") or None
    ctx = dict(lesson_context or {})
    definition = _definition_for(kind)  # type: ignore[arg-type]
    order_id = work_order_id or f"write-{kind}-{uuid.uuid4().hex[:10]}"
    scoped = {
        "stage": "document_writing",
        "kind": kind,
        "role": role,
        "reason": reason,
        "lesson_context": ctx,
        "teaching_block": dict(teaching_block),
        "brief": brief,
        "evidence": evidence or teaching_block.get("evidence"),
        "allowed_facts": list(allowed_facts or ctx.get("allowed_facts") or []),
        "sourcebook_entries": [dict(entry) for entry in (sourcebook_entries or ctx.get("sourcebook_entries") or [])],
        "terminology": list(terminology or ctx.get("terminology") or []),
        "neighbours": list(neighbour_summaries or []),
        "objective": ctx.get("objective") or ctx.get("title"),
    }
    inputs = {
        "kind": kind,
        "brief": brief,
        "teaching_block": dict(teaching_block),
        "lesson_context": ctx,
        "allowed_facts": list(allowed_facts or []),
        "sourcebook_entries": [dict(entry) for entry in (sourcebook_entries or [])],
        "terminology": list(terminology or []),
        "role": role,
        "reason": reason,
        "neighbours": list(neighbour_summaries or []),
    }
    compatibility = CheckpointCompatibility(
        teaching_revision=int(ctx.get("teaching_plan_revision") or 1),
        input_hash=content_hash(inputs),
        definition_hash=str(definition.definition_hash or ""),
        composition_identity=order_id,
    )
    checkpoint_key = f"node:{order_id}"
    if checkpoint_store is not None:
        prior = checkpoint_store.get(checkpoint_key)
        if prior is not None and prior.status == "ready" and prior.payload is not None:
            # C01: validate compatibility BEFORE returning a cached ready payload.
            checkpoint_store.decide_resume(
                checkpoint_key,
                compatibility=compatibility,
            )
            return dict(prior.payload)

    request = AuthoringRequest(
        work_order_id=order_id,
        definition=definition,
        scoped_request=scoped,
        inputs=inputs,
        teaching_revision=int(ctx.get("teaching_plan_revision") or 1),
        source_identities=(block_id or "teaching-block",),
        mode="generate",
    )
    selected = engine or AuthoringEngine(
        registry=AuthoringRegistry().with_validator(
            "document.writer_schema", _noop_validator
        ),
        provider=provider,
        # Total provider dispatches for this work item: 1 initial + up to 2 repairs.
        max_repair_attempts=2,
        max_transport_attempts=1,
        call_budget=call_budget,
        budget_ledger=budget_ledger,
        max_provider_calls=3,
        progress_store=progress_store,
        progress_run_id=progress_run_id,
        progress_stage=progress_stage,
        durable_persist_hook=durable_persist_hook,
    )
    selected.registry.validators.setdefault("document.writer_schema", _noop_validator)
    selected.registry.validators.setdefault("document.writer_quality", _document_quality_validator)
    if durable_persist_hook is not None and getattr(selected, "durable_persist_hook", None) is None:
        selected.durable_persist_hook = durable_persist_hook
    if checkpoint_store is not None:
        checkpoint_store.begin(checkpoint_key, compatibility=compatibility)

    try:
        result = await selected.execute(
            request,
            provider=provider,
            call_budget=call_budget,
        )
    except AuthoringEngineError as exc:
        if checkpoint_store is not None:
            checkpoint_store.mark_ambiguous(checkpoint_key)
        raise DocumentWriterError(exc.code, str(exc)) from exc

    payload = dict(result.payload)
    payload["kind"] = kind
    normalized = _normalize_payload(
        kind,  # type: ignore[arg-type]
        payload,
        node_id=nid,
        teaching_block_id=block_id,
    )
    if checkpoint_store is not None:
        checkpoint_store.commit(
            checkpoint_key,
            payload=normalized,
            compatibility=compatibility,
        )
    return normalized



__all__ = [
    "DocumentWriterError",
    "write_document_primitive",
]

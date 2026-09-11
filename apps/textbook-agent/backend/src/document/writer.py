"""Generic LLM document writer — one ordinary primitive per call.

Teaching Plan briefs are writer instructions, never copied as student text.
Figure writes caption/alt only; assets use the existing figure pipeline.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Mapping, Sequence

from document.models import (
    DOCUMENT_PRIMITIVE_KINDS,
    CalloutNode,
    FigureNode,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
    document_node_adapter,
)
from document.writer_prompts import document_writer_prompt
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringRequest,
)
from infra.authoring.engine import AuthoringRegistry

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
    if len(b) >= 40 and (a.startswith(b[:40]) or b.startswith(a[:40])):
        return True
    return False


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
        validator_refs=("document.writer_schema",),
        definition_hash=f"document-writer-v1:{kind}",
    )


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
    terminology: Sequence[str] | None = None,
    neighbour_summaries: Sequence[Mapping[str, Any]] | None = None,
    teaching_block_id: str | None = None,
    node_id: str | None = None,
    role: str | None = None,
    reason: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
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
        "terminology": list(terminology or ctx.get("terminology") or []),
        "neighbours": list(neighbour_summaries or []),
        "objective": ctx.get("objective") or ctx.get("title"),
    }
    request = AuthoringRequest(
        work_order_id=f"write-{kind}-{uuid.uuid4().hex[:10]}",
        definition=definition,
        scoped_request=scoped,
        inputs={
            "kind": kind,
            "brief": brief,
            "teaching_block": dict(teaching_block),
            "lesson_context": ctx,
            "allowed_facts": list(allowed_facts or []),
            "terminology": list(terminology or []),
        },
        teaching_revision=int(ctx.get("teaching_plan_revision") or 1),
        source_identities=(block_id or "teaching-block",),
        mode="generate",
    )
    selected = engine or AuthoringEngine(
        registry=AuthoringRegistry().with_validator(
            "document.writer_schema", _noop_validator
        ),
        provider=provider,
        max_repair_attempts=2,
    )
    try:
        result = await selected.execute(request, provider=provider)
    except AuthoringEngineError as exc:
        raise DocumentWriterError(exc.code, str(exc)) from exc

    payload = dict(result.payload)
    payload["kind"] = kind
    quality = _payload_quality_errors(kind, payload, brief=brief)
    if quality:
        # Stage-local retry once with stricter feedback via a second execute.
        repair_request = AuthoringRequest(
            work_order_id=f"{request.work_order_id}-repair",
            definition=AuthoringDefinition(
                capability_id=definition.capability_id,
                native_path=definition.native_path,
                modes=("generate",),
                instructions=(
                    definition.instructions
                    + "\n\nPrevious attempt failed quality checks:\n- "
                    + "\n- ".join(quality)
                    + "\nRewrite learner-facing content. Do not copy the brief."
                ),
                payload_schema=definition.payload_schema,
                required_inputs=definition.required_inputs,
                validator_refs=definition.validator_refs,
                definition_hash=definition.definition_hash,
            ),
            scoped_request=scoped,
            inputs=request.inputs,
            teaching_revision=request.teaching_revision,
            source_identities=request.source_identities,
            mode="generate",
        )
        try:
            result = await selected.execute(repair_request, provider=provider)
        except AuthoringEngineError as exc:
            raise DocumentWriterError(exc.code, str(exc)) from exc
        payload = dict(result.payload)
        payload["kind"] = kind
        quality = _payload_quality_errors(kind, payload, brief=brief)
        if quality:
            raise DocumentWriterError("INVALID_PAYLOAD", "; ".join(quality))

    return _normalize_payload(
        kind,  # type: ignore[arg-type]
        payload,
        node_id=nid,
        teaching_block_id=block_id,
    )


__all__ = [
    "DocumentWriterError",
    "write_document_primitive",
]

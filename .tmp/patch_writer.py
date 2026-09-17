from pathlib import Path

p = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src\document\writer.py")
text = p.read_text(encoding="utf-8")
start = text.index("async def write_document_primitive")
end = text.index("\n__all__")
new_fn = '''async def write_document_primitive(
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
    work_order_id: str | None = None,
    call_budget: CallBudget | None = None,
    budget_ledger: CallBudgetLedger | None = None,
    checkpoint_store: CheckpointStore | None = None,
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
        "terminology": list(terminology or []),
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
    )
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
    quality = _payload_quality_errors(kind, payload, brief=brief)
    if quality:
        # Do not open a second AuthoringEngine.execute loop — that multiplies the
        # call budget. Surface quality failure so the durable repair path (same
        # work-item counter) can reserve another call explicitly.
        if checkpoint_store is not None:
            checkpoint_store.mark_ambiguous(checkpoint_key)
        raise DocumentWriterError("INVALID_PAYLOAD", "; ".join(quality))

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


'''
p.write_text(text[:start] + new_fn + text[end:], encoding="utf-8")
print("ok")

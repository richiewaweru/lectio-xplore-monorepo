# Cursor Run 08 — Projections, QC, Events, and Variant Safety

## Goal

Remove v2 dependencies on wide component fields and make the committed document observable and reviewable.

## Work

1. Add intent/object-based projection filters.
2. Keep v1 projection functions for v1 documents.
3. Route deterministic QC through canonical v2 validation.
4. Optionally install document QC prompt after deterministic gates.
5. Add block/document lifecycle events without changing v1 event payloads unexpectedly.
6. Update frontend progress handling for v2 events.
7. Add core-variant invariant tests.
8. Add one-variable variant support only where current data model can prove the changed axis.

## Gate

No v2 projection reads hardcoded component field names. QC uses committed document. Events support resume/reload. Variant test proves one-axis difference.

## Commit

`refactor(projections): consume ordered page blocks`

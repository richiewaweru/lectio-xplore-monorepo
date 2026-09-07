# P01 — Publish authoritative capability catalogues

Dependencies: P00.
Canonical owners: Shared vocabulary, @lectio/page, @lectio/learn and contract exporters.

## Entry
Read the master prompt, contract documents, previous phase report and current STATE.json. Confirm required predecessor gates are PASS at compatible revisions. Record new baseline and run only necessary baseline checks. Any substantive upstream change reopens affected gates.

## Work
1. Implement contracts/01_CAPABILITY_CONTRACT.md. Establish one neutral instructional vocabulary and generate compatibility views. Preserve canonical IDs unless an explicit migration is documented.
2. Complete Print form definitions and Learn content/interaction records with real selection, schema, runtime and evaluation semantics. Export teaching/action compatibility and web hints that were previously lost.
3. Register new interaction capabilities through normal module/export paths. Eliminate duplicate handwritten consumer metadata; retain generated adapters.
4. Fix inconsistent ShortResponse semantics and align old quiz/blank wrappers with shared evaluation. Complete supported text interactions; implement spatial contracts and authoring requirements or explicitly mark them unavailable.
5. Version manifests and readiness checks. Publish package contracts locally for consumer development; do not perform public npm publication.

## Acceptance gates
- [ ] P01-K01: Exports regenerate reproducibly and include all intended source metadata; deliberately change a source capability and prove generated selection/writer views update.
- [ ] P01-K02: Every supported intent/action ref exists; reverse maps are generated; examples validate against exact schemas.
- [ ] P01-K03: Invalid/duplicate/unknown response IDs and malformed configs fail. Numeric NaN/infinity and negative tolerance rejected.
- [ ] P01-K04: Renderer/evaluator golden examples pass for every activated interaction, including partial scoring and attempt limits where supported.
- [ ] P01-K05: Package-only consumer fixture imports public exports without native source-internal dependencies; incomplete capabilities absent from generation-ready view.
- [ ] P01-K06: Teaching view contains no native inventory/schema; selection view omits full writer payload contracts.

For each gate record a concrete test/command, expected behaviour, actual exit code, fixture identity and evidence location. A assertion of file presence or a mock that bypasses the changed handoff cannot satisfy a behaviour gate. Do not mark every gate passing from one broad test invocation unless its assertions actually cover each gate.

## Deliverables
Versioned capability exports, generated backend models, readiness inventory and package gate evidence.

## Failure and rollback
Keep last passing revision available. For data changes use additive schema and explicit old-record handling. Do not reset user data or delete unrelated changes. If gate fails, attribute to the responsible stage, repair locally and rerun that gate plus impacted dependencies. If blocked externally, record evidence and next unblock action; proceed with independent permitted work but never label dependent phases complete.

## Exit report
Copy tracking/PHASE_REPORT_TEMPLATE.md; attach per-gate results. Update STATE.json, GATE_RESULTS.csv and decision log. Record implementation commits where repository policy permits. Continue to the next eligible phase without routine confirmation.

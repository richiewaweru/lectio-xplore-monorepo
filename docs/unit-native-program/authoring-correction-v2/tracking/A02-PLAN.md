# A02 Plan — Reusable Authoring Engine

## Scope
Implement a shared backend authoring engine in `apps/textbook-agent/backend/src/infra/authoring/` that accepts adapter-supplied package definitions and scoped requests. Add Print and Learn adapters that translate existing A01 work orders into the common engine contract without replacing the current Print `dispatch_writer_async` or Learn ordered production entrypoints yet.

## Classification
Major backend foundation change. It introduces a shared execution interface and adapters across Print and Learn, but keeps production migration to A03/A04.

## Checklist
- [x] Read A02 pack materials, acceptance policy and project architecture rules.
- [x] Inspect existing Print `_write_validated_llm` repair flow and provider infrastructure.
- [ ] Define generic authoring request, definition, result, provenance and typed failure models.
- [ ] Implement shared async generate/convert/validate/repair engine with bounded transport retries and bounded invalid-output repairs.
- [ ] Implement validator and converter registries without print/learn pedagogy imports in `infra.authoring`.
- [ ] Add Print and Learn adapters that register domain validators/converters and preserve package-specific schemas.
- [ ] Add A02 regression tests under `tests/authoring_correction/` using mock providers only at the provider boundary.
- [ ] Run A02 gates and record durable evidence under `evidence/a02/`.
- [ ] Update `GATE_RESULTS.csv`, `STATE.json` and `A02-REPORT.md`.
- [ ] Commit only A02 files with `feat(authoring): shared generate/convert/repair engine`.

## Design Notes
- The engine owns execution mechanics only: definition resolution, required-input checks, mode choice, provider invocation, JSON coercion, schema validation, registered semantic validators, repair prompt composition, retry accounting and provenance.
- Adapters own domain mapping: Print form ids and validators stay in Print; Learn capability ids, Learn validators and approved-item conversion stay in Learn.
- Prompts will compose the common template, package capability instructions and the scoped request JSON. The request must not include full catalogues, sibling schemas, unrelated items or other-path configuration.
- Repairs will carry the original scoped request, selected definition, previous output and precise validation errors. Transport retries remain provider-call retries; malformed payload repairs remain separate and capped.
- Typed failures will use the required A02 codes and include stage and retryability. Failures must not synthesize placeholder content.

## Validation Plan
- Run `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a02_shared_authoring_engine.py`.
- Gate mapping:
  - A02-G01: Print and Learn adapters both call one shared provider/repair path with distinct schemas.
  - A02-G02: Captured prompts exclude sibling schemas, catalogues, other path settings and unrelated approved items.
  - A02-G03: Malformed output is repaired with original scope; exhausted repair raises/persists `REPAIR_EXHAUSTED`.
  - A02-G04: Missing inputs, missing definitions and missing provider fail with typed failures.
  - A02-G05: Provenance includes work order, sources, teaching revision, definition hash and input hash; retry counts are bounded.

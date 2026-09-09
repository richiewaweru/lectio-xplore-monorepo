# A01 Plan — Complete package authoring definitions

## Scope
- Extend the existing `FormWriterRecord` and `LearnWriterRecord` projections with the full A01 authoring contract instead of adding a second registry.
- Move Print writer instructions into package-owned resources under `packages/lectio-page`, keeping backend loaders able to resolve the same capability instructions.
- Add Learn-owned instruction resources for generation-ready interactions and generation-enabled content capabilities.
- Export regenerated package contracts and sync the generated views into the backend contract area using existing package tooling.
- Update backend work-order hash/readiness helpers so instruction, schema, modes, required inputs, validators and relevant constraints all affect `definition_hash`.

## Implementation Steps
1. Inspect current package exports, backend writer request builders, validator registries and contract sync behavior.
2. Add resource directories and package exports for Print and Learn instruction files.
3. Extend package types/projections:
   - Print: `definition_version`, `capability_id`, `native_path`, `lane`, `modes`, `instructions`, `schema_ref`, `payload_schema`, `field_guidance`, `required_inputs`, `validator_refs`, optional processing refs, and full `definition_hash`.
   - Learn: same contract shape while preserving teaching, selection and runtime view separation.
4. Add validation/readiness checks that fail explicitly on missing instruction resources or unknown validator refs.
5. Update backend loaders/request builders and work-order hash helpers to consume the complete exported authoring definition, including resolved instruction text.
6. Add focused tests for A01-G01 through A01-G04, including negative cases for missing resources and unknown validators.
7. Run export scripts and focused tests, store durable evidence under `evidence/a01/`.
8. Update `GATE_RESULTS.csv`, `STATE.json`, and write `A01-REPORT.md`.
9. Stage only A01-related files and commit with `feat(packages): complete authoring definitions and definition hashes`.

## Evidence Plan
- Capture package export outputs and focused test outputs in `docs/unit-native-program/authoring-correction-v2/evidence/a01/`.
- Record exact commands, exit statuses, and the resulting commit SHA in the report and gate table.

## Constraints
- Preserve existing dirty `.tmp`, P05 evidence, backend runtime logs, and data artifacts.
- Do not disable promised capabilities or move Learn imports into Print.
- Do not push.

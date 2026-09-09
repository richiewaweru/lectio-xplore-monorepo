# A04 Plan — Complete Learn content and interaction authoring

## Scope
- Stay in the Learn domain: `apps/textbook-agent/backend/src/learn/**`, Learn-focused authoring-correction tests, existing P06 Learn tests as needed, and A04 tracking/evidence.
- Do not edit Print/A03 surfaces, print rendering registries, Print executor, or A03 tracking.
- Use `packages/lectio-learn` contracts as the source of capability schemas and instructions; avoid package churn unless tests expose a missing contract.

## Checklist
- [ ] Route native Learn production through `run_learn_authoring` before ordered assembly for both content and interaction work orders.
- [ ] Make ordered assembly a pure consumer of validated authoring results; reject missing, mismatched, or unvalidated content/interaction results.
- [ ] Replace heuristic interaction payload generation with engine-backed conversion/generation for the eight core interactions.
- [ ] Preserve teacher-review short-response as pending review and keep spatial interactions unavailable.
- [ ] Add A04 tests using independently specified known-answer fixtures and mocked provider boundary only.
- [ ] Keep A00 arbitrary-answer and brief-as-content regressions passing, updating harnesses only for intentional API changes.
- [ ] Audit `payload_strategies.py` for reusable assets without restoring the wide SectionContent pipeline.
- [ ] Run focused A04/A00/P06 gates and record evidence under `evidence/a04/`.
- [ ] Update `GATE_RESULTS.csv`, `A04-REPORT.md`, and commit only Learn/A04 files.

## Implementation Approach
1. Add small Learn authoring helpers that run content and interaction work orders via the shared `AuthoringEngine`, wrap interaction configs into runtime contracts, and retain provenance.
2. Update `native_production.build_closed_learn_production` so normal native production authors all selected work orders first, then passes validated results into `assemble_ordered_learn_document`.
3. Update `ordered_assemble.py` to consume authoring results keyed by work order id and fail when selected content or interactions lack validated results. Keep ordering based on teaching blocks and work-order order.
4. Refactor `interaction_writer.py` so direct writer entry points use `run_learn_authoring` through a configured provider/engine. Conversion requires complete compatible approved data; generation requires provider output. Remove fallback guesses from brief parsing.
5. Add focused tests for the A04 gates: content is real authored payload, all eight core interaction convert/generate paths, known-answer regressions, evaluator validation, missing-result rejection, and content schema/order preservation.

## Evidence Plan
- Save pytest output for `apps/textbook-agent/backend/tests/authoring_correction` A00/A04 tests.
- Save pytest output for `apps/textbook-agent/backend/tests/print_learn/test_p06_learn_authoring_gates.py` if updated.
- Record any known deferred live/model-quality checks as NOT_RUN rather than PASS.

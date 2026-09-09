# A06 Plan — Integrated offline acceptance

## Scope
- Fix P07 runtime assembly to supply validated `authored_results` for closed Learn assembly.
- Inject optional Learn `provider`/`engine` through `produce_learn_from_approved_teaching` for P08 offline gates.
- Add `P08LearnMockProvider` (MOCK) returning schema-valid Learn payloads with teaching brief tokens preserved.
- Add `tests/authoring_correction/test_a06_integrated_offline.py` for dual-path, evaluation, invalid payload, publish immutability and definition regressions.
- Re-run P04/P06/P07/P08 and full `authoring_correction` suite; record evidence under `evidence/a06/`.
- Update `GATE_RESULTS.csv`, `STATE.json`, and `A06-REPORT.md`. Live verification remains DEFERRED.

## Checklist
- [x] P07 `_sequence_document` authors work orders before assembly.
- [x] `produce_learn_from_approved_teaching` accepts mocked provider/engine.
- [x] P08 integration gates inject Learn mock at provider boundary only.
- [x] A06 integrated offline tests and gate tracking artefacts.
- [x] Full offline gate re-run and evidence capture.

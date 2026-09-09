# A03 Plan — Print authoring engine migration

## Scope Guard
- Stay inside Print/A03 files only: `apps/textbook-agent/backend/src/print/**`, Print-focused `tests/authoring_correction/**`, and A03 tracking/evidence.
- Do not edit Learn generation, selection, ordered assembly, interaction writers, or A04 tracking.
- Preserve executor concurrency, checkpoints, resume decisions, targeted retry, pagination, and PDF behavior.

## Implementation Checklist
- Wire normal `dispatch_writer_async` for LLM-written Print forms through `print.generation.authoring_adapter.run_print_authoring` and the shared `infra.authoring` engine.
- Pass `PrintWorkOrder` identity and hashes from closed Print production planning into the writer path at execution time, using `build_print_writer_request` through the adapter.
- Consolidate active prompt construction on package-loaded authoring definitions and remove bypassed local prompt/contract mappings from the normal LLM path.
- Fail closed on missing package authoring contracts; remove advisory `_writer_contract` success-on-exception behavior.
- Remove table/figure broad exception fallback to stub writers so provider/repair exhaustion becomes a typed failure and never emits fixture leaves.
- Keep `assemble_questions` and `assemble_choices` as the exact approved conversion path for non-LLM conversion.
- Preserve explicit figure lifecycle: generated briefs may yield `visual_pending`, but failed briefs remain failed rather than completed assets.

## Tests And Evidence
- Add/adjust Print-focused tests under `apps/textbook-agent/backend/tests/authoring_correction/` for A03-G01 through A03-G05.
- Ensure the A00 table fallback regression now passes without weakening the original intent.
- Run focused A03 tests and relevant A00/A02 regressions from `apps/textbook-agent/backend`.
- Store command output under `docs/unit-native-program/authoring-correction-v2/evidence/a03/`.
- Update only A03 rows in `tracking/GATE_RESULTS.csv`, write `tracking/A03-REPORT.md`, and update `tracking/STATE.json` for A03 without overwriting concurrent A04 state.

## Commit Plan
- Stage only Print/A03 source, test, tracking, and evidence files.
- Commit with `fix(print): route writers through package authoring engine`.

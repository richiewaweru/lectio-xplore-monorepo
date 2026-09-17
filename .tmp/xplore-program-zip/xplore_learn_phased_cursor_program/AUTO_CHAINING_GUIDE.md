# Why Phase 0 Matters and How Reports Chain Forward

## Phase 0 is not busywork

The later phase packets describe *desired architecture*. Phase 0 converts that into *verified facts about the current checkout*.

Its outputs answer questions such as:
- Which Builder is canonical?
- Which persistence layer is already production-proven?
- Which component package/API is actually consumed?
- Which backend copy owns a diverged file?
- Which tests constitute the current Page and Component golden paths?
- Which repo/branch/SHA did the migration really start from?
- Which subsystems are already sufficient and must not be rebuilt?

Without Phase 0, later Cursor runs can correctly understand the product vision while still making the wrong file-level decision.

## What Phase 0 persists

It writes to the target repo:

```text
docs/xplore-program/
├── PROGRAM_STATE.md
├── BASELINE_REUSE_MANIFEST.json
├── CURRENT_ARCHITECTURE.md
└── reports/
    └── phase-00/
        └── PHASE_REPORT.md
```

## Do you feed Phase 0's report back to Cursor?

Normally **no**.

If Cursor continues working in the same checkout, Phase 1's prompt tells it to read those files directly.

If you create a completely fresh Cursor conversation, point it to:
`phases/01-consolidation/CURSOR_PHASE_PROMPT.md`

That prompt explicitly instructs it to recover `PROGRAM_STATE`, the baseline manifest, and Phase 0's report from the repo.

## What if Cursor is using a temporary/ephemeral environment?

Then copy/commit `docs/xplore-program/` into the real target repo before starting the next phase. The chain only works if the reports/state persist somewhere the next run can read.

## Why all later phase artifacts can be authored now

Later packets specify:
- product invariants,
- ownership boundaries,
- phase goals,
- acceptance outcomes.

They intentionally do **not** hard-code every future file path. Each phase must first read the current program state and inspect the actual checkout after previous phases.

This lets the program remain adaptive without allowing architectural drift.

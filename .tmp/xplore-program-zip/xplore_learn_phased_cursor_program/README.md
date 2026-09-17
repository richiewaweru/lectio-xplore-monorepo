# Xplore Learn Expansion — Phased Cursor Program

This package is a controlled implementation program for extending the existing Xplore/Lectio system into:

**Author → Edit → Student Preview → Explicit Publish → Distribute → Learn Runtime → Evidence → Insight**

It is intentionally phased. Do **not** ask Cursor to implement the whole program in one run.

## How to use

1. Place/unpack this package in or beside the target `lectio-xplore-monorepo` checkout.
2. Start with `phases/00-baseline/CURSOR_PHASE_PROMPT.md`.
3. Give Cursor access to the repositories/source checkouts named in `permanent/PROGRAM_CHARTER.md`.
4. Let Cursor complete that phase, run its gates, and write the required report/state artifacts into the target repo.
5. For the next run, point Cursor only to the next phase's `CURSOR_PHASE_PROMPT.md`.
6. Cursor must read `PROGRAM_STATE.md`, the baseline reuse manifest, and the previous phase report before acting.
7. Each phase stops after its acceptance gates pass. It must not begin the next phase.

You do **not** need to manually feed the previous report back to Cursor if it is working in the same repo/workspace. The program requires reports to be persisted under `docs/xplore-program/`, where the next phase can read them.

If you open a fresh Cursor conversation, simply point it at the next phase prompt. The prompt tells it where to recover prior state.

## Permanent implementation rule

> Inspect first. Reuse proven seams. Extend before replacing. Introduce a parallel subsystem only when the existing subsystem cannot satisfy the requirement through a bounded extension.

## Final target

- Existing Page Lectio continues to own Print/PDF.
- Existing Component Lectio becomes web-native `@lectio/learn`.
- Existing generation + Builder/editing/persistence are retained and extended.
- New capabilities are added for publishing, runtime, classes, assignments, evidence, and analytics.
- Page inline editing remains deferred.

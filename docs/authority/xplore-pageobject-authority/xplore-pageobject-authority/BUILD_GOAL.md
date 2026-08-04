# Cursor Master Execution Goal

You are implementing the native Lectio page-object integration for Xplore.

## Authority

The attached `xplore-pageobject-authority` pack is authoritative. Read, in order:

1. `README.md`
2. `AUTHORITY.md`
3. `DECISIONS.md`
4. `BASELINE.md`
5. `TARGET_ARCHITECTURE.md`
6. `PHASES.md`
7. `CURSOR_OPERATING_CONTRACT.md`

Earlier Claude build goals, stance patches, and separate intent/object selector prompts are historical context only. Where they conflict, this pack wins.

## Working location

Create/use the monorepo at:

`C:\Projects\lectio`

Expected imports:

- `packages\lectio-page` from `C:\Projects\lectio - Copy`
- `apps\textbook-agent` from `https://github.com/richiewaweru/text-book-generator`, branch `xplore`

Do not modify, move, or delete the original `C:\Projects\lectio - Copy`.

## Execution

Run the phase instructions under `cursor-runs/` in numerical order. Do not skip a failed dependency. For each run:

- inspect the live code before editing;
- update `docs/implementation-runs/PROGRESS.md`;
- write the required `RUN_XX_REPORT.md`;
- run the phase gate;
- commit with the specified message only when the gate is green or a clearly independent partial foundation is green;
- stop dependent work on blockers and document them precisely.

Continue through as many fully verifiable phases as the unattended session permits. Prefer four complete phases over ten partially connected ones.

## Core target

The first implementation proof is:

```text
approved first-exposure conceptual lesson
→ ordered native PlannedBlock sections
→ object-specific content
→ persisted LectioDocumentV2
→ application v2 renderer
→ A4 PDF
```

The v2 path must not construct the legacy wide `SectionContent` record.

## Non-negotiable decisions

- one section-level block planner for initial implementation;
- no `StanceSpec`;
- no two LLM calls per block;
- section title renders automatically; planner emits no heading blocks initially;
- questions remain behind the concept-card wall;
- pending figures own stable positions;
- v1 and v2 coexist;
- no early runtime rename or legacy deletion;
- package contracts are canonical and sync reproducibly into backend;
- no silent fallback after v2 starts.

## Paid calls

Do not make paid model calls unless the phase explicitly authorizes them and `ALLOW_PAID_LLM_TESTS=1` is present. Fixture and mocked gates are the default.

## Final unattended output

At session end, regardless of phase reached, leave:

- clean commits for completed phases;
- `PROGRESS.md` with accurate status;
- run reports with command evidence;
- `BLOCKERS.md` with unresolved decisions;
- no unreported architecture deviations;
- exact instructions for the next run.

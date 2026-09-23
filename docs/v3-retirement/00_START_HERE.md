# Lectio V3 Retirement & Native Architecture Cleanup
## Casa Grok Execution Pack

**Repository:** `richiewaweru/lectio-xplore-monorepo`  
**Default branch at proposal time:** `main`  
**Proposal date:** 2026-09-23  
**Status:** Execution proposal / migration pack

---

## Mission

Make the repository describe **one current Lectio architecture**.

The current native product path is already established:

```text
Unit / Path Lesson
        |
        v
   Preparation
        |
        v
 Structural Plan
        |
        v
 Teaching Plan
        |
  Teacher Approval
        |
        v
 Native Content Realization
        |
    +---+---+
    |       |
    v       v
  Learn    Print
```

The repository still contains older V3 execution, Studio, naming, and routing structures that coexist with the native path and make the system difficult to understand and safely change.

This undertaking must:

1. identify the exact current native dependency spine;
2. **move/rename** still-useful infrastructure out of `v3_*` namespaces;
3. **delete** genuinely retired V3 execution and UI paths;
4. move current native HTTP/UI code out of legacy `v3`/`studio` ownership;
5. preserve current behavior while doing so;
6. prove the native workflow end-to-end after the legacy architecture is physically removed;
7. leave a clean foundation for the next architecture change: the shared content writer + section continuity work.

---

## Core execution rule

> **MOVE survivors. DELETE architecture. Do not redesign behavior during this cleanup.**

Do not interpret "retire V3" as "delete every path containing v3". Some current native code still imports useful execution/planning machinery from `v3_execution` and `v3_blueprint`. Those pieces must first be moved into current domain ownership.

---

## Known current facts verified before this proposal

The following were confirmed on the repository's current `main` state at proposal time:

- The current Learn realization does **not** import the old V3 section writer.
- The current native Print whole-lesson realization does **not** import the old V3 section writer.
- The native Stage 2 route explicitly says not to run legacy section briefs, assembly, or component writers for native/shared preparation.
- The legacy Stage 2 back half is explicitly disabled for new lessons.
- The old `v3_execution.executors.section_writer.execute_section()` is still called by legacy V3 Studio/runtime paths.
- `v3_execution` still contains useful current dependencies, including:
  - structured LLM helpers/config used by current authoring/planning code;
  - item generation used before Teaching Plan generation;
  - visual execution used by current Learn/Print figure paths.
- `v3_blueprint` still contains current planning models/persistence used by Unit preparation.
- The current Unit lesson plan UI still uses some `/api/v1/v3/...` endpoints even when the backend operation is native.
- The giant `print/http/v3_studio/router.py` currently mixes native endpoints with legacy Studio endpoints.

Casa must **re-verify all of the above against HEAD before changing code**. The pack is authoritative on desired architecture and gates, but the repository is authoritative on exact current callers.

---

## Required working mode

Create a dedicated branch, for example:

```text
chore/retire-v3-legacy
```

Do not make one enormous final commit. Use phase-sized commits so a failed phase can be reverted cleanly.

Keep `07_RUNBOOK.md` updated as work progresses.

At every gate:

- run the required checks;
- record exact commands and results;
- fix failures before proceeding;
- do **not** waive failures to reach the next phase.

If a dependency is ambiguous, classify it by evidence, not by filename:
- used by current canonical native flow -> MOVE/KEEP;
- only used by legacy flow -> DELETE;
- mixed ownership -> split first, then move/delete.

---

## Strict non-goals

Do **not** combine this undertaking with:

- the new shared content writer;
- section-level continuity contracts;
- Print/Learn content-authoring convergence;
- new Teaching Plan semantics;
- new learner action types;
- UI redesign;
- database/schema redesign unless unavoidable for pure relocation;
- new product behavior.

Those are follow-up architecture changes after this cleanup has produced a clean native baseline.

---

## Read order

1. `01_CANONICAL_ARCHITECTURE.md`
2. `02_SCOPE_AND_INVARIANTS.md`
3. `03_MOVE_DELETE_MANIFEST.md`
4. `04_PHASED_EXECUTION_PLAN.md`
5. `05_VERIFICATION_GATES.md`
6. `06_E2E_ACCEPTANCE.md`
7. `07_RUNBOOK.md`
8. `08_CASA_STARTUP_PROMPT.md`
9. `09_CLOSEOUT_REPORT_TEMPLATE.md`

The startup prompt intentionally points Casa back to this pack rather than trying to duplicate all details in one message.

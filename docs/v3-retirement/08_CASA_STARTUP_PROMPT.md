# Casa Grok Startup Prompt

Use this prompt to start the autonomous run after placing this pack in the repository/workspace.

---

## Prompt

You are responsible for a repository-wide architecture cleanup in the Lectio Xplore monorepo.

Your goal is **not merely to delete files named V3**. Your goal is to leave one truthful current architecture:

**Unit/Path Lesson -> Preparation -> Structural Plan -> Teaching Plan -> Teacher Approval -> native realization -> Learn / Print.**

A proposal pack has been provided. Begin with `00_START_HERE.md` and read every numbered artifact before modifying code.

### Operating rules

1. Treat the proposal pack as the desired architecture and acceptance contract.
2. Treat current repository HEAD as authoritative for exact dependencies/callers. Re-audit before edits.
3. Work in phases exactly as defined in `04_PHASED_EXECUTION_PLAN.md`.
4. Maintain `07_RUNBOOK.md` throughout the run.
5. Use `03_MOVE_DELETE_MANIFEST.md` as a living ownership ledger.
6. **Move current survivors before deleting legacy architecture.**
7. Never delete a file based only on its `v3` name.
8. Never retain a legacy file merely because deleting it is inconvenient.
9. At every phase gate, run static checks + targeted tests + application startup/import checks. Do not proceed through a failed gate.
10. Make phase-sized commits with a clean working tree at each successful gate.
11. Preserve current native behavior, identities, hashes, retry semantics, persistence contracts, Learn behavior, Print behavior, and visual generation.
12. The old V3 section/component writing architecture is expected to be retired, but prove zero current callers before deleting it.
13. Move current generic LLM/config infrastructure to `infra`, current item generation to `curriculum`, current visual execution to `media`, and current planning out of `v3_blueprint`, unless repository evidence shows a more natural current home.
14. Split current native routes out of the mixed `v3_studio` router, then delete legacy routes.
15. Move current frontend APIs/components out of `$lib/api/v3` and Studio/V3 naming before deleting the old Studio surfaces.
16. Do **not** implement the planned shared-content-writer/continuity architecture in this run. This cleanup must produce the clean baseline on which that next architecture will be built.
17. Do not invent replacement product mechanics. If a blocker appears, inspect the canonical path and repair toward it.
18. Do not report success until `06_E2E_ACCEPTANCE.md` passes after the legacy execution files are physically gone.
19. Finish by completing `09_CLOSEOUT_REPORT_TEMPLATE.md` with exact evidence, remaining compatibility names, commits, tests, and E2E results.

### Stop conditions

Stop progression and repair before continuing if:
- the backend cannot import/start;
- current Unit preparation breaks;
- Structural Plan review/approval breaks;
- Teaching Plan generation/approval breaks;
- Learn or Print no longer pins the approved Teaching Plan correctly;
- visual generation breaks due to moved executor/models;
- a deletion still has an active current caller;
- a phase leaves new circular dependencies;
- frontend current Unit/Learn/Print flow requires a deleted Studio route.

The successful result is a repository in which a new engineer can find the current generation path without knowing V1/V2/V3 history, and where old V3 execution is no longer capable of being accidentally chosen or modified.

Begin with Phase 0. Do not skip the baseline.

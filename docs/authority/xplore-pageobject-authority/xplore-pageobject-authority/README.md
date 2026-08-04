# Xplore → Native Lectio Page Objects

**Status:** implementation authority pack  
**Version:** 1.0  
**Date:** 2026-08-05  
**Target workspace:** `C:\Projects\lectio`  
**Application source:** `richiewaweru/text-book-generator`, branch `xplore`  
**Page library source:** `richiewaweru/lectio-pageobject`, baseline commit `14ca43b5fac17f4c5a268eb626f3f96eac63a7be`

This pack is the implementation authority for repurposing the `xplore` branch so it plans, writes, persists, renders, and prints native Lectio page-object documents.

The first proof is not a selector dry-run. It is:

```text
approved path lesson
  → native ordered block plan
  → object-specific content
  → LectioDocumentV2
  → validation
  → application render route
  → A4 PDF
```

## Authority order

When instructions conflict, Cursor must follow this order:

1. `AUTHORITY.md`
2. `DECISIONS.md`
3. `PHASES.md`
4. the relevant file in `cursor-runs/`
5. the detailed specifications in this pack
6. existing code and tests, used as implementation evidence
7. earlier Claude build goals and stance patches, used only as historical context

The earlier `BUILD_GOAL.md`, `PATCH_resource_stance.md`, and two-selector prompts are not implementation authorities. Their useful parts were incorporated here; their conflicting parts are explicitly rejected in `SOURCE_REVIEW.md`.

## Start here

1. Read `AUTHORITY.md` and `DECISIONS.md` completely.
2. Run `cursor-runs/RUN_00_PREFLIGHT_AND_MONOREPO.md`.
3. Execute runs in numerical order. Never skip a failed gate.
4. After every run, write the required report under `docs/implementation-runs/` in the working repository.
5. The first overnight stopping point should be the highest fully green phase, not the largest amount of partially connected code.

## Pack map

| Artifact | Purpose |
|---|---|
| `AUTHORITY.md` | non-negotiable architecture and product invariants |
| `SOURCE_REVIEW.md` | what was accepted and rejected from the supplied Claude work |
| `BASELINE.md` | confirmed current code paths and known uncertainty |
| `TARGET_ARCHITECTURE.md` | final ownership boundaries and data flow |
| `MONOREPO_BOOTSTRAP.md` | safe import plan for `C:\Projects\lectio` |
| `PHASES.md` | ordered implementation plan and gates |
| `FILE_CHANGE_MATRIX.md` | add/modify/retain/delete map by repository path |
| `CONTRACTS.md` | Python planning contracts and document rules |
| `PIPELINE_SPEC.md` | complete runtime behavior from lesson preparation to PDF |
| `TEST_STRATEGY.md` | automated, fixture, browser, and print verification |
| `CUTOVER_AND_ROLLBACK.md` | coexistence, flags, migration, rollback, and cleanup |
| `CURSOR_OPERATING_CONTRACT.md` | unattended-agent rules and reporting format |
| `prompts/` | production prompt specifications for the new pipeline |
| `cursor-runs/` | pasteable, phase-specific Cursor execution goals |
| `examples/` | reference input, plan, and v2 document fixtures |
| `schemas/` | planning-output schemas independent of the renderer schema |
| `scripts/` | safe bootstrap and verification helpers |
| `manifests/` | machine-readable phase, file, and prompt inventories |

## Definition of started correctly

The project has started correctly only when:

- both repositories are present in one real root repository or in an explicitly documented temporary workspace;
- the canonical page contracts are synced into the backend reproducibly;
- the legacy v1 route remains runnable;
- the v2 path is feature-flagged and additive;
- no new `StanceSpec` domain model has been introduced;
- no component-to-page-object adapter has become the primary v2 architecture;
- the first implementation target is a generated, persisted, reloadable A4 lesson.

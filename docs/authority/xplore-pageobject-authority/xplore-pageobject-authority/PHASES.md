# Phased Implementation Plan

Each phase has a corresponding pasteable instruction under `cursor-runs/`. A phase is complete only when its acceptance gate is green and its run report is committed.

## Phase 0 — Workspace, evidence, and import

**Goal:** create the safe monorepo and map exact current owners.

Deliverables:

- imported repositories at requested paths;
- source SHAs and clean-state evidence;
- baseline backend/frontend/page-package test results;
- `BASELINE_MAP.md` resolving the ten unknown owners in `BASELINE.md`;
- root progress and blocker files.

No product code changes.

**Gate:** both projects run their existing tests from the new root; exact generation/render/PDF owners are documented.

## Phase 1 — Contract synchronization and heading contract

**Goal:** make the page contract consumable by Python and align section-heading behavior.

Add a reproducible contract-sync script that copies:

- document JSON Schema;
- intent catalogue;
- object catalogue;
- catalogue/contract versions;
- generated Python models or checked typed adapters.

In the page package, render `section.title` as the section heading and test that the initial generated document does not require a heading block.

**Gate:** contract drift test passes; a backend fixture validates against the synced schema; page package tests and fixture PDF pass.

## Phase 2 — Additive v2 planning contracts and candidate resolver

**Goal:** introduce native planning types without changing production behavior.

Add:

- `PlannedBlock`;
- section block-planner output model;
- `SectionPlan.blocks` additive field;
- document contract version discriminator;
- resource vocabulary schema;
- lesson vocabulary and skeleton candidate intents for the first slice;
- deterministic candidate matrix resolver.

Do not add `StanceSpec`.

**Gate:** legacy plans still parse; candidate tests cover non-empty intersections, exclusions, compatibility, heading exclusion, and catalogue drift.

## Phase 3 — V2 structural and section block planning

**Goal:** produce a fully validated block plan from a real approved lesson without writing content.

Add:

- v2 structural-planner prompt/agent that no longer expects component selections;
- section-block-planner prompt/agent;
- v2 branch in `planning/bridge.py` behind a creation feature flag;
- dry-run command that can use fixtures without paid calls and optionally real calls when explicitly enabled.

The planner sees resource context, actual prior knowledge, section purpose, narrowed candidates, catalogue tests, objective, card, and neighbouring section summaries.

**Gate:** a conceptual first-exposure fixture produces ordered blocks for all sections; every block is closed-set and compatible; no component selector is invoked on the v2 route.

## Phase 4 — Object-specific writers

**Goal:** turn block briefs into typed content for the first-slice objects.

Implement dispatcher and writers for:

- prose;
- list;
- table;
- worked-example;
- figure brief/pending asset;
- questions assembler from existing item IDs.

Object writers receive one fixed object and cannot choose another.

**Gate:** writer fixture suite produces schema-valid block content; prohibited scope and capacity failures are caught; question assembler proves it never uses section prose.

## Phase 5 — Native document assembly and persistence

**Goal:** create and reload the canonical v2 document.

Implement:

- stable block IDs;
- position normalization;
- section and document assembly;
- backend schema and semantic validation;
- canonical persistence using the current final-document owner resolved in Phase 0;
- reload endpoint/serializer with `document_version=2`.

No legacy `SectionContent` construction in this route.

**Gate:** one approved lesson produces a persisted document, process state can be reloaded, and bytes/normalized JSON are stable across reload.

## Phase 6 — Frontend rendering and A4 PDF

**Goal:** render persisted v2 documents in the application.

Add `@lectio/page` as a workspace dependency while retaining legacy `lectio`. Route by document version. Reuse the application’s existing print/export route and readiness protocol.

**Gate:** browser test loads the generated lesson; teacher and student modes render; Playwright creates A4 PDF; reloading the page does not reconstruct the document differently.

## Phase 7 — Question wall and visual completion

**Goal:** make questions and media production-safe inside ordered blocks.

- questions reference only item-generation outputs derived from the concept card;
- answer-key references remain stable;
- figure completion updates only the asset payload of the existing block;
- failed media remains a visible/diagnosable block state;
- document order is unchanged by async completion.

**Gate:** tests prove prose cannot affect generated items; pending-to-ready visual update preserves block ID/position; failed asset has an explicit render state.

## Phase 8 — Projections, QC, events, and variants

**Goal:** remove remaining v2 assumptions about wide component fields.

- projections filter blocks by intent/object;
- QC validates the committed document;
- SSE exposes block/document lifecycle without breaking v1 consumers;
- core variant remains reference; add one-variable variant handling only after invariant tests.

**Gate:** revision/teacher/student projections contain expected blocks; no v2 projection reads legacy component field names.

## Phase 9 — Controlled cutover and cleanup

**Goal:** make v2 creation the default for the first approved scope and remove only proven-dead code.

Requirements before deletion:

- production-like smoke green;
- v1 and v2 read regression green;
- rollback tag;
- no import references;
- telemetry or fixture evidence that the old creator is unused for the migrated route.

Potential cleanup:

- component selector on migrated approved-path route;
- component-specific v2 prompt branches;
- obsolete free-generation path if independently confirmed unused;
- old projection code for v2;
- runtime rename only as a separate mechanical PR.

**Gate:** feature flag defaults to v2 for first-slice scope; disabling it restores v1 creation without affecting existing v2 reads.

## Phase 10 — Expansion decision

Only after Phase 9, decide whether to expand by:

1. knowledge type;
2. lesson mode;
3. object set;
4. variant;
5. resource type.

Do not expand all axes at once. Each expansion gets fixtures and acceptance evidence.

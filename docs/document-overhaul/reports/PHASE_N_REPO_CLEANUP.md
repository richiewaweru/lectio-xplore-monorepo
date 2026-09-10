# Phase N — Repository and Package Cleanup Report

**Date:** 2026-09-11  
**Branch:** `refactor/document-model-overhaul`  
**Goal:** Make repo docs/scripts describe the document + interaction architecture.

## Done

### Architecture docs
- Updated `apps/textbook-agent/agents/project.md`:
  - Teaching Plan → explicit Print|Learn paths
  - Document primitives + retained interactions (no `component_lectio`)
  - `backend/src/document/` shared vocabulary
  - `@lectio/contracts` owns intents; `@lectio/page` is Print engine; `@lectio/learn` interaction UI only / app-owned document path
- Updated `docs/architecture/CURRENT_SYSTEM.md` to the same target flow
- Updated `docs/refactor-program/permanent/TARGET_ARCHITECTURE.md`:
  - Added `document/` package
  - Learn generation now lists document realizer / writer / assemble / interactions
  - Print generation notes document realizer
  - Frontend Learn notes app-owned document canvas
  - Packages clarify contracts / page / learn roles

### Root scripts / workspace
- Kept `learn:test` and `learn:export` in root `package.json` because `@lectio/learn` still ships retained interaction UI.
- **Deferred:** full `lectio-learn` package removal until interactions are fully moved to the app. Noted in `OVERHAUL_STATE.md`. Workspace remains intact.

### Domain guards / xplore-program
- Left `tools/xplore-program` zero-legacy / domain-boundary checks unchanged (still encode retired `component_lectio` surfaces; document path does not require an easy extension).

## Deferred debt — ordinary content components in `@lectio/learn`

Preferring not to mass-delete ExplanationBlock / DefinitionCard / SectionContent / templates from the package in this phase: they are still wired through:

- `packages/lectio-learn/src/lib/lectio/registry/components`
- `capabilities/content.ts` projection (one record per registered module)
- templates, schema validators, export policy, and many package tests

Production Learn generation no longer selects these IDs (backend `document/` denylist + LearnDocument v2 path). Full strip of ordinary content components from `@lectio/learn` (capability registry, templates, SectionContent) is **deferred debt** until interaction-only package cleanup.

## Acceptance

- Docs describe document primitives + independent Print|Learn realization.
- Workspace install/scripts still resolve `@lectio/learn` for interactions.
- No production `component_lectio` path restored.

# File Change Matrix

`CONFIRMED` means the path was observed. `RESOLVE` means Run 00 must locate the exact current owner before edits. Cursor may update path names in its baseline report, but not change the responsibility described here without a blocker.

## Root monorepo

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| ADD | `package.json` | 0 | root commands only; no business code |
| ADD | `pnpm-workspace.yaml` | 0 | package and frontend workspace |
| ADD | `.gitignore` | 0 | combined Python/Node outputs |
| ADD | `README.md` | 0 | monorepo run instructions |
| ADD | `docs/implementation-runs/` | 0 | evidence, reports, blockers |
| ADD | `scripts/verify-phase.ps1` | 0 | repeatable phase gates |

## Page package: `packages/lectio-page`

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| RETAIN | `contracts/lectio-document-v2.schema.json` | all | canonical document contract |
| RETAIN | `contracts/intent-catalogue.v1.json` | all | canonical intents |
| RETAIN | `contracts/object-catalogue.v1.json` | all | canonical objects/capacity |
| MODIFY | `src/lib/render/SectionView.svelte` or resolved equivalent | 1 | render `section.title` exactly once as h2 |
| MODIFY | `src/lib/render/LectioDocumentView.svelte` or resolved equivalent | 1 | ensure document h1/section h2 hierarchy and export API |
| MODIFY | `src/lib/contract/validation.ts` only if necessary | 1 | prevent duplicate auto-title + first-block heading ambiguity; do not forbid nested heading globally |
| ADD/MODIFY | tests for heading hierarchy | 1 | title visible without a heading block; nested heading remains supported |
| RETAIN | fixture PDF pipeline | 1,6 | contract and print gate |
| MODIFY | package exports | 6 | export `LectioDocumentView`, types, normalize/validate functions needed by app |

## Backend contract ingress

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| ADD | `apps/textbook-agent/tools/update_lectio_page_contracts.py` | 1 | canonical package → committed backend snapshots |
| ADD | `apps/textbook-agent/backend/contracts/lectio-page/` | 1 | synced schema/catalogues/version manifest |
| ADD | `apps/textbook-agent/backend/src/contracts/generated/lectio_page.py` | 1 | generated typed document models or validated adapter |
| ADD | `apps/textbook-agent/backend/src/contracts/lectio_page.py` | 1 | loader, version/hash checks, validation facade |
| ADD | `apps/textbook-agent/backend/tests/contracts/test_lectio_page_contracts.py` | 1 | drift, parity, and fixture validation |
| MODIFY | existing contract-sync docs/tests | 1 | include second package without breaking legacy Lectio sync |

## Resource and skeleton planning

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| MODIFY (CONFIRMED) | `backend/src/resource_specs/schema.py` | 2 | additive vocabulary and min/max block fields; no stance |
| MODIFY (CONFIRMED) | `backend/src/resource_specs/renderer.py` | 2 | render compact runtime resource context |
| ADD | `backend/src/resource_specs/candidates.py` | 2 | strict resource × skeleton candidate matrix |
| MODIFY (CONFIRMED) | `backend/resources/specs/lesson.yaml` | 2 | v2 lesson vocabulary; retain legacy component rules |
| DEFER | `backend/resources/specs/worksheet.yaml` | 10+ | not part of first slice |
| MODIFY (CONFIRMED) | `backend/resources/skeletons.yaml` | 2 | candidate intents and block bounds for conceptual first exposure; retain allowed components for v1 |
| ADD | `backend/tests/resource_specs/test_page_candidates.py` | 2 | closure, exclusion, compatibility, heading, empty intersection |

## Planning models and agents

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| MODIFY (CONFIRMED) | `backend/src/v3_blueprint/planning/models.py` | 2 | `PlannedBlock`, additive `SectionPlan.blocks`, version discriminator |
| MODIFY (CONFIRMED) | `backend/src/planning/models.py` | 2–3 | planner response models |
| MODIFY (CONFIRMED) | `backend/src/planning/agents.py` | 3 | v2 structural and section block planner calls |
| MODIFY (CONFIRMED) | `backend/src/planning/prompts.py` | 3 | prompt loaders |
| ADD | `backend/resources/path-structural-planner-page-v1.txt` | 3 | structure without components |
| ADD | `backend/resources/section-block-planner-v1.txt` | 3 | ordered intent/object block plan |
| MODIFY (CONFIRMED) | `backend/src/planning/bridge.py` | 3 | feature-flagged v2 path; v1 untouched |
| ADD | `backend/scripts/page_plan_dryrun.py` | 3 | fixtures by default; paid mode explicit |
| ADD | planning tests around bridge | 3 | prove component selector not invoked in v2 |

## Object generation

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| ADD | `backend/src/generation/page_objects/__init__.py` | 4 | module boundary |
| ADD | `backend/src/generation/page_objects/context.py` | 4 | immutable writer context |
| ADD | `backend/src/generation/page_objects/models.py` | 4 | writer output models/status |
| ADD | `backend/src/generation/page_objects/dispatcher.py` | 4 | fixed-object dispatch |
| ADD | `backend/src/generation/page_objects/writers/prose.py` | 4 | prose writer |
| ADD | `.../writers/list.py` | 4 | list writer |
| ADD | `.../writers/table.py` | 4 | table writer |
| ADD | `.../writers/worked_example.py` | 4 | worked example writer |
| ADD | `.../writers/figure.py` | 4 | pending figure block + request |
| ADD | `.../writers/questions.py` | 4 | deterministic item assembler, not LLM |
| ADD | `backend/resources/page-writers/*.txt` | 4 | prompts included in this pack |
| MODIFY/ADD (RESOLVE) | model-slot configuration | 4 | dedicated writer output types; do not reuse arbitrary component slots |
| ADD | `backend/tests/generation/page_objects/` | 4 | per-object contract tests |

## Document assembly and persistence

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| ADD | `backend/src/generation/page_objects/document_builder.py` | 5 | direct v2 document assembly |
| ADD | `backend/src/generation/page_objects/validation.py` | 5 | backend validation facade/semantic mirror |
| MODIFY (RESOLVE) | canonical generation state/persistence owner | 5 | store final v2 document and block statuses |
| MODIFY (RESOLVE) | generation read API/schema | 5 | return versioned document |
| ADD | `backend/tests/generation/test_page_document_lifecycle.py` | 5 | persist/reload/stability |
| RETAIN | legacy section builder | 5 | v1 only; no v2 calls |

## Frontend and PDF

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| MODIFY | `frontend/package.json` | 6 | add `@lectio/page: workspace:*`, retain `lectio` |
| MODIFY (RESOLVE) | generation document TypeScript model/API client | 6 | discriminated v1/v2 response |
| MODIFY (RESOLVE) | generated lesson viewer | 6 | route by document version |
| MODIFY (RESOLVE) | print route | 6 | v2 `LectioDocumentView`, readiness signal |
| MODIFY (RESOLVE) | PDF backend endpoint | 6 | reuse existing Playwright path |
| ADD | v2 viewer/browser tests | 6 | reload, audience, object rendering |
| ADD | PDF smoke fixture | 6 | application-generated document, not hand-authored only |

## Questions, visuals, projections, QC

| Action | Path | Phase | Purpose |
|---|---|---:|---|
| MODIFY (RESOLVE) | item assembler/output store | 7 | question IDs into blocks, wall preserved |
| MODIFY (RESOLVE) | visual request/writeback | 7 | pending figure asset updated in-place |
| MODIFY (RESOLVE) | `planning/projections.py` | 8 | intent/object filters for v2 |
| MODIFY (RESOLVE) | QC entry point | 8 | validate committed v2 document |
| MODIFY (RESOLVE) | SSE/event schemas and frontend consumer | 8 | block/document lifecycle |

## Deferred deletion list

No deletion is authorized before Phase 9. Candidates, after import/reference checks:

- v2 use of `run_component_selector` on the approved-path route;
- legacy component prompt branches used only by migrated creation scope;
- old v2 projection logic that reads wide fields;
- free-generation route if proven unused;
- runtime rename as a separate mechanical change.

The old renderer and legacy contracts stay while any v1 document is readable.

# CLEANUP_STATE

- current_phase: (complete)
- last_completed_phase: C5
- current_sha: 25db4a70a6a28e72f189a5d67a9711bab44440c9
- dirty_state: C0–C5 uncommitted on domain-refactor dirty tree

## Completed
- [x] C0 Reachability audit
- [x] C1 Canonical Unit-path wiring
- [x] C2 Complete domain separation
- [x] C3 Dead-code removal
- [x] C4 Repository/docs hygiene
- [x] C5 Guards + integration proof

## Canonical paths
- Unit → Print: `application.unit_lesson` prepare → `path_preparation` (native flag) → `print.http.v3_studio` approve → `print.generation.whole_lesson` → PDF
- Unit → Learn: prepare → units approve → `learn.generation.component_lectio` → Builder → `application.builder_print` (PDF optional) → `learn.publishing` LearnRelease → `learn.runtime`

## Remaining shims
- `generation/v3_studio`, learn top-level shims, `planning/*`, `generation` pdf/page_objects, `core/*`, `telemetry`, `learning/*`

## Remaining legacy-referenced items
- Mounted skeletons, blocks/generate, legacy-units, packs (FE still calls)
- v3 studio UX beyond Unit hops
- `.tmp/` local scratch

## Structural residuals
- `planning.bridge` implementation body
- Live browser Unit E2E not executed in C5

## Deferred product fixes
See `docs/cleanup-program/permanent/DEFERRED_PRODUCT_FIXES.md` plus `@lectio/learn` quiz evaluate test failure.

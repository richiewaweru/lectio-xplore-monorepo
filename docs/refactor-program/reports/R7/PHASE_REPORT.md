# R7 PHASE REPORT — Architecture Guards + Compatibility Cleanup

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- dirty state: R0–R6 complete in working tree

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| (new) | `tools/xplore-program/check_backend_domain_boundaries.py` | PLATFORM | Backend print/learn/curriculum/infra guards |
| (new) | `tools/xplore-program/tests/test_backend_domain_boundaries.py` | PLATFORM | CI/test coverage |
| `package.json` | add `program:domain-guards` | PLATFORM | Runs package + backend guards |

## Compatibility shims
All R1–R4 historical shims **retained** (call sites still use old paths). Explicit owners/removal:

| Shim family | Owner | Removal condition |
|---|---|---|
| Print (`planning.whole_lesson`, `generation.page_objects/pdf_export`, `resource_specs.candidates`, `core.pdf_export_runtime`, page_* planning) | Print | Migrate call sites to `print.*`; then delete |
| Learn (`learning.*`, `generation.component_lectio`, `units_dispatch`, `builder.service`, `component_candidates`, contracts.lectio*) | Learn | Migrate to `learn.*`; then delete |
| Curriculum (`planning.service/routes/…`) | Curriculum | Migrate to `curriculum.*`; then delete |
| Infra (`core.auth/llm/…`, `telemetry`, `core.database.session/migrations`) | Infra | Migrate to `infra.*`; then delete |
| `builder/routes.py` PDF edge | Composition | Extract PDF routes to composition root before deleting Learn→Print surface |

`v3_studio` **not** removed (still hosts Print HTTP; REMOVE_LATER after extract).

## Behavior changes
Expected: NONE. Observed: NONE.

## Tests
| Command | Result |
|---|---|
| `python tools/xplore-program/check_backend_domain_boundaries.py` | PASS 0 |
| `python tools/xplore-program/check_domain_boundaries.py` | PASS 0 |
| `pytest tools/xplore-program/tests/test_backend_domain_boundaries.py` | PASS 1 |

## Import/dependency checks
- No print→learn, learn→print, curriculum→product, infra→product violations in domain trees
- Shims excluded from scans by design

## Ending state
- safe for next phase: YES

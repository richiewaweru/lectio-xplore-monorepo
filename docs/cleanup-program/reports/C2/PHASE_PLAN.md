# C2 PHASE PLAN — Complete Domain Separation

Starting after C1 PASS on dirty `refactor/domain-ownership`.

## In scope
1. **Builder PDF extract** — move export/pdf + print-preflight (+ helpers) from `builder/routes.py` into `application/builder_print/routes.py` (application may orchestrate Learn lesson load + Print PDF). Mount from `app.py` with prefix `/api/v1/builder`. Remove print/pdf imports from `builder/routes.py`. Keep `print-document` GET in builder (no Print import).
2. **Print owns v3 studio HTTP package** — move `generation/v3_studio/` → `print/http/v3_studio/`; leave `generation/v3_studio` as shim re-export. Update `generation/routes.py` to import from `print.http.v3_studio.router`.
3. **Learn packaging** — relocate `release_routes` → `learn/publishing/`, `insight_service` → `learn/analytics/`, `runtime_routes`/`runtime_service`/`runtime_models` → `learn/runtime/` with shims at old paths; add empty `distribution/` + `evidence/` packages.
4. **application/unit_lesson** — keep prepare re-export (already C1).

## Out of scope
Deleting shims/v3 UX (C3), docs hygiene (C4), full bridge.py body move.

## Verify
domain-guards; builder/learn pytest; create_app import.

# R8 PHASE REPORT — Full Refactor Verification + Final Map

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- SHA base: `a5e68a2` (working tree contains R0–R8)
- dirty state: full domain refactor uncommitted

## Move plan executed
Verification-only phase (no additional product moves). Fixed one path-depth bug in `print/generation/page_blocks.py` discovered during verification (`parents[2]` → `parents[3]` after R4 move).

## Compatibility shims
All R1–R4 historical shims remain with documented removal criteria (see R7). None removed in R8.

## Behavior changes
Expected: NONE.
Observed: NONE (path-depth fix restores prior contract-file resolution; not a product behavior change).

## Tests
| Command | Result |
|---|---|
| Package domain boundaries | PASS 0 |
| Backend domain boundaries | PASS 0 |
| Alembic head + metadata | PASS head `20260906_0039`, 42 tables |
| Backend Print+Learn+Builder+runtime pytest suite | PASS 50 |
| `pnpm --filter @lectio/page test` | PASS 41 |
| `@lectio/learn` focused vitest | PASS 2 |
| Frontend focused vitest (shared + builder) | PASS 5 |

## Import/dependency checks
No unresolved cross-domain import violations in `print/`, `learn/`, `curriculum/`, `infra/`.

## Final tree (ownership map)

### Backend (`apps/textbook-agent/backend/src/`)
```text
print/          # paper/PDF realization
learn/          # interactive product (generation, authoring, runtime, analytics)
curriculum/     # units/paths/schedule semantics
infra/          # shared infrastructure (target name: platform/; stdlib clash)
app.py          # composition root
+ historical shims: planning/, generation/, core/, learning/, builder/, telemetry/, contracts/
+ leftover eras: v3_studio, v3_blueprint, v3_execution, v3_review, media/
```

### Frontend (`apps/textbook-agent/frontend/src/lib/`)
```text
shared/         # auth, config, settings, auth store
curriculum/     # units panels
print/          # studio, generation stream, print styles/components/stores
learn/
  authoring/    # builder + workspace
  student/      # shell + release API client
  distribution/ # placeholder
  insight/      # placeholder
+ residual seams: api/, types/, components/{pack,workspace,...}
```

### Packages
```text
packages/lectio-page   # @lectio/page
packages/lectio-learn  # @lectio/learn
```

## Unresolved ownership seams
1. `builder/routes.py` still mixes Learn CRUD with Print PDF (composition extraction pending)
2. `generation/v3_studio` still hosts Print HTTP (extract then REMOVE_LATER)
3. `v3_blueprint` / `v3_execution` / `v3_review` cross-product stacks
4. `core/database/models.py` monolith (+ residual core entities/routes)
5. `media/` providers vs print topology/QC
6. Frontend `lib/api` + `lib/types` mixed clients
7. Historical import shims still required until call-site migration

## Deferred product fixes → target paths
| Deferred fix (from charter) | Target home after refactor |
|---|---|
| Learner auth vs teacher JWT | `infra/auth/` + `learn/runtime/` |
| Server-side scoring authority | `learn/runtime/` + `learn/evidence/` |
| Concept bindings from LearnRelease | `learn/publishing/` + `learn/runtime/` |
| Attempt submission E2E | `learn/runtime/` + frontend `learn/student/` |
| Section completion events | `learn/runtime/` |
| Sequential navigation | `learn/student/` + `learn/runtime/` |
| Analytics class/assignment scope | `learn/analytics/` + `learn/distribution/` |
| ImageHotspot/DragLabel spatial | `packages/lectio-learn` + `learn/authoring/` |
| Float → Numeric scores | `infra/database` models / `learn/runtime` |
| Remove `v3_studio` | after Print HTTP extract → delete under `generation/v3_studio` |
| Remove Component-Lectio print helpers | `packages/lectio-learn/src/lib/print` (REMOVE_LATER) |
| PDF fixture process hang | `packages/lectio-page` pdf:fixture / `print/rendering/pdf` |

## Ending state
- safe for post-refactor vertical integration: YES
- recommended next program: migrate call sites off shims; extract Print HTTP from `v3_studio`; extract Builder PDF to composition root; then remove shims under R7 criteria

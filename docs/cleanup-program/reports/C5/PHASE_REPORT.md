# C5 REPORT — Architecture Guards + Full Integration Proof

Status: PASS

## Starting state
- after C4 PASS on dirty `refactor/domain-ownership` @ `25db4a7`

## Work performed
- Extended package domain guard with frontend ownership-prefix residual scan (`$lib/learn/shared`, `/print/studio`, …)
- Retained backend shim exclusions for remaining historical shims; added `generation/v3_studio`
- Ran integration/regression gates below; produced final tree + residuals

## Final tree (ownership)

### Backend `apps/textbook-agent/backend/src/`
```text
application/     # unit_lesson, builder_print
curriculum/
print/           # generation, rendering, resources, contracts, http/v3_studio
learn/           # authoring, generation, publishing, runtime, analytics,
                 # distribution/, evidence/ (placeholders), resources, contracts
infra/
app.py
+ historical shims: planning/, generation/, core/, builder/, learning/, telemetry/, contracts/
+ era stacks: v3_blueprint/, v3_execution/, v3_review/, media/, resource_specs/
```

### Frontend `apps/textbook-agent/frontend/src/lib/`
```text
shared/ curriculum/ print/ learn/
+ residual: api/, types/, components/, stores/
```

### Packages
```text
packages/lectio-page   # @lectio/page
packages/lectio-learn  # @lectio/learn
```

## Tests
| Command / flow | Result |
|---|---|
| `pnpm program:domain-guards` | PASS |
| ORM metadata | PASS 42 tables |
| Alembic heads | PASS `20260906_0039` |
| `pnpm page:test` | PASS 41 |
| `pnpm page:check` | PASS 0 errors |
| Backend builder + learn releases + runtime + component_lectio | PASS 31 |
| Frontend routing/path vitest | PASS |
| `@lectio/learn` `lectio.test.ts` | FAIL 1 pre-existing quiz “Not quite!” (deferred product) |
| Live Unit→Print E2E (prepare→PDF) | NOT RUN in this environment — admission unit-fixed in C1; full LLM/PDF path residual |
| Live Unit→Learn→Builder→Publish E2E | Partial via route pytest; full browser E2E residual |

## Residuals (structural vs product)
| Item | Kind |
|---|---|
| Historical shims still on disk | structural — migrate call sites then delete |
| Mounted skeletons / blocks/generate / legacy-units / packs | structural/product — FE still calls |
| v3 studio UX beyond Unit hops | structural — delete after Unit Print HTTP fully owned without studio UX |
| `planning.bridge` body still under planning | structural |
| `@lectio/learn` quiz evaluate test | product (deferred) |
| Full live Unit Print/Learn browser E2E | residual verification gap |

## Deferred product fixes
Unchanged — see `docs/cleanup-program/permanent/DEFERRED_PRODUCT_FIXES.md`.

## Ending state
- program C0–C5: COMPLETE (PASS with documented residuals)
- safe for follow-on product work: YES
- remaining issues are primarily product-quality / residual mounts, not ambiguous ownership of the Unit graphs

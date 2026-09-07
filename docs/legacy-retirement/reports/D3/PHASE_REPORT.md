# D3 Report — Retire Routes Jobs Telemetry Config

Status: PASS

## Starting state
- after D2 PASS @ `2aa7bdee` (dirty: D0–D2 code/docs uncommitted)
- Unit Print hop still on `/api/v1/v3/*` + `/studio?generation_id=…`
- Non-Unit mounts still present: packs, skeletons HTTP, legacy-units, blocks/generate, FE packs/legacy/builder/new

## Subsystems handled
Unmounted unsupported operational surfaces; preserved Unit Print hop.

### Backend unmounts
- `/api/v1/packs` (learn.routes) — removed from `app.py`
- `/api/v1/skeletons*` — not mounted
- `/api/v1/legacy-units` — not mounted
- `/api/v1/blocks/generate` — removed from `generation.routes` (only `v3_studio_router` remains under `/api/v1`)
- Skeleton **catalog** startup (`initialize_skeleton_catalog`) retained for Unit path shape

### Frontend retirement
- `/packs/*`, `/units/legacy/*`, `/builder/new` → redirect to `/units`
- Blank `/studio` (no `generation_id`) → `/units`; Unit Print with `generation_id` kept
- `units.ts` legacy/skeleton helpers reject; `ai-client.generateBlock` throws; `learning-pack.ts` retired stubs
- Builder pack link → `/units`

### Auth/testability fix
- `core.routes.capabilities` imports `infra.auth.middleware.get_current_user` (ghost `core.auth.middleware` caused 401 under overrides)

## Consumers migrated
- Capabilities route dependency → infra auth
- FE API helpers return retired errors instead of calling unmounted endpoints
- Capability + skeleton HTTP tests expect 404 for retired mounts

## Routes/jobs/telemetry/config retired
| Surface | Result |
|---|---|
| `/api/v1/packs` | unmounted (404) |
| `/api/v1/legacy-units` | unmounted (404) |
| `/api/v1/skeletons*` | unmounted (404) |
| `/api/v1/blocks/generate` | unmounted (404) |
| FE `/packs*`, `/units/legacy*`, `/builder/new` | redirect `/units` |
| FE blank `/studio` | redirect `/units` |
| `/api/v1/v3/*` Unit Print | **retained** |
| Telemetry router | retained (Unit/infra; not legacy-only) |

## DB impact
None (D4).

## Deletions
- Legacy-only HTTP test `tests/routes/test_blocks_generate.py` removed earlier in phase
- No legacy tree deletions (D5)

## Compatibility shims retained
- D1/D2 shims; `generation.routes` thin mount of v3_studio; FE stub modules for retired APIs
- Studio generation/print viewers kept for Unit Print hop

## Tests
| Command | Result |
|---|---|
| `pnpm program:domain-guards` | PASS |
| Focused Unit-path pytest (path_bridge/routes, builder, learn releases/runtime, component_lectio, capabilities, skeletons HTTP retired) | PASS 71 + 5 learn_runtime |
| Vitest `units.test.ts` + legacy redirect page | PASS 10 |

## Residual risks
- `/api/v1/v3/packs*` and studio UX still live for Unit Print approve/PDF (D4/D5 ownership cleanup)
- `generation/`, `planning/`, `builder/`, `core` ORM, `resource_specs`, `v3_*` trees remain on disk
- Builder `AiBlockAssist` UI may still call retired `generateBlock` (throws; surface not Unit path)
- Pack/legacy page files remain as redirect stubs until D5 delete

## Ending state
- safe for next phase: YES
- Next: D4 — classify/move/drop DB via Alembic; ORM ownership toward infra; preserve migration history

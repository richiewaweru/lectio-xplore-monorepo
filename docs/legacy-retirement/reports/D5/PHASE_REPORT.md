# D5 Report — Delete Legacy Trees Completely

Status: PASS

## Starting state
- after D4 PASS; Alembic head `20260907_0040`; ORM in `infra.database.models` (41 tables)
- Temporary shims still present: `planning/`, `generation/`, `builder/`, `learning/`, `telemetry/`

## Subsystems handled
### Deleted packages (zero production imports after retarget)
- `builder/` → `learn.authoring.builder`
- `learning/` → `learn.*`
- `telemetry/` → `infra.telemetry`
- `generation/` (mount collapsed into `app.py` → `print.http.v3_studio`; canonical → `learn.generation.canonical`)
- `planning/` (residuals moved; shims removed)

### Moved residuals before delete
| From | To |
|---|---|
| `generation/canonical.py` | `learn/generation/canonical.py` |
| `planning/projections.py` | `application/projections.py` |
| `planning/llm_contract_errors.py` | `curriculum/llm_contract_errors.py` (print-free) |
| `planning/planner_diagnostics.py` | `curriculum/planner_diagnostics.py` |
| `planning/structural_validation.py` | `curriculum/structural_validation.py` |
| `planning/models.py` | `curriculum/path_models.py` |
| `planning/model_tiers.py` | `print/generation/model_tiers.py` |
| (catalogue already under print) | `print/generation/catalogue_projections.py` |

### Frontend
- Deleted redirect stubs: `/packs*`, `/units/legacy*`, `/builder/new`
- Retargeted studio pack navigations → `/units`
- Kept `/studio*` for Unit Print hop

### Guards
- Added `tools/xplore-program/check_zero_legacy.py`
- Wired into `pnpm program:domain-guards`

## Consumers migrated
All production imports of deleted packages retargeted to `application` / `curriculum` / `print` / `learn` / `infra`.

## Routes/jobs/telemetry/config retired
- `generation.routes` removed; `app.py` mounts `v3_studio_router` at `/api/v1` directly
- Shadow gate script deleted

## DB impact
None beyond D4.

## Deletions
- Packages: `planning/`, `generation/`, `builder/`, `learning/`, `telemetry/`
- FE stubs: packs, units/legacy, builder/new
- Legacy-only tests/scripts tied to deleted modules
- Orphan BOM bytes stripped from rewrite fallout files

## Compatibility shims retained
**None** of the five deleted package roots. Remaining justified exceptions (not shims):

| Exception | Why |
|---|---|
| `core/` | Platform HTTP routes + entities/repos still live |
| `contracts/` | Shared Lectio/document contracts |
| `resource_specs/` | Unit Print/Learn resource legality |
| `media/` | Unit Print image pipeline |
| `v3_blueprint/`, `v3_execution/`, `v3_review/` | Unit prepare + Print/Learn execution/QC |
| FE `/studio*` | Unit Print UX |

## Final backend tree (src/)
```
app.py
application/
contracts/
core/
curriculum/
infra/
learn/
media/
print/
resource_specs/
v3_blueprint/
v3_execution/
v3_review/
```

Canonical six are present; exceptions listed above are explicit and Unit-path-justified.

## Tests
| Command | Result |
|---|---|
| `pnpm program:domain-guards` (incl. zero-legacy) | PASS |
| `create_app()` + v3 router | PASS (44 routes) |
| Focused Unit-path pytest | PASS 64 |

## Residual risks
- `v3_*` / `contracts` / `media` / `resource_specs` / `core` remain MIGRATE_AND_DELETE debt toward stricter six-root purity (future program)
- Pack/item DB tables remain ACTIVE for Unit Print (D4 classification)
- Broad test suites under `tests/planning` / `tests/generation` still named historically but import canonical owners

## Ending state
- safe for next phase: N/A (program complete)
- D0–D5 chain: **COMPLETE**

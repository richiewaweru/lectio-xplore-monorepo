# D2 Report — Evacuate Live Consumers

Status: PASS

## Starting state
- after D1 PASS @ `2aa7bdee`
- `application/unit_lesson` owned prepare/dispatch; planning.bridge / generation.path_preparation were shims

## Subsystems handled
Evacuated live Unit consumers into canonical owners (no DB drops; studio/packs mounts retained for D3):

### Wave A
- Rewired `print.http.v3_studio` + `v3_execution.runtime.runner` telemetry imports → `infra.telemetry.*`
- Learn route tests: `learning.*` → `learn.*`
- Moved `builder/routes.py` → `learn/authoring/builder/routes.py` (shim left at `builder/routes.py`)
- `app.py` + `application.builder_print` import learn builder routes

### Wave B
- Moved `generation/contracts.py` → `learn/generation/contracts.py`
- Moved `generation/pipeline_dispatch.py` → `learn/generation/pipeline_dispatch.py`
- Moved `generation/units_routes.py` → `learn/generation/units_routes.py`
- Updated `application.unit_lesson.dispatch`, component_lectio, units_dispatch, `app.py`

### Wave C
- Moved `planning/validation.py` → `curriculum/validation.py`
- Moved `planning/prompts.py` → `curriculum/prompts.py`; added `print/generation/prompts.py` facade for print consumers
- Moved `planning/agents.py` → `curriculum/agents.py`
- Updated curriculum routes/service, `application.unit_lesson.prepare`, v3 component_selector

### Auth consumer rewire (testability / infra ownership)
- Learn publishing/runtime/analytics/routes + builder_print + units_routes use `infra.auth` / `infra.database.session` / `infra.dependencies` instead of `core.auth` ghost bindings
- Matching test overrides updated

## Consumers migrated
Backend Unit Learn/Print/Curriculum callers listed above. Frontend unchanged (D3).

## Routes/jobs/telemetry/config retired
None unmounted. Telemetry production imports rewired to infra (package shim remains).

## DB impact
None (D4).

## Deletions
None of legacy trees (D5). Bodies moved; historical paths retained as temporary shims.

## Compatibility shims retained
- `builder/routes.py`, `generation/{contracts,pipeline_dispatch,units_routes,path_preparation}.py`
- `planning/{bridge,agents,validation,prompts}.py`
- Prior D0/D1 shims; `telemetry/`, `learning/` packages

## Tests
| Command | Result |
|---|---|
| `pnpm program:domain-guards` | PASS |
| Focused Unit-path pytest (path_bridge/routes, builder, learn releases/runtime, component_lectio) | PASS 61 |

## Residual risks
- `planning.projections` still real under planning (curriculum→print answer-key coupling)
- Print prompt function bodies still defined in `curriculum.prompts` (print facade re-exports)
- `planning.llm_contract_errors` / `planner_diagnostics` still under planning
- Studio/blocks/skeletons/packs/legacy-units still mounted (D3)
- `resource_specs`, `media`, `v3_*`, `core` ORM not fully evacuated

## Ending state
- safe for next phase: YES

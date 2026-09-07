# LEGACY_STATE

- current_phase: D5 complete (program finished)
- last_completed_phase: D5
- current_sha: 2aa7bdee9f3a36483c99920b3a2ea243153ccb3f
- dirty_state: D0–D5 docs + retirement code uncommitted; .tmp/ logs data/ untracked
- alembic_head: 20260907_0040
- orm_tables: 41
- zero_legacy_guard: PASS

## Completed
- [x] D0
- [x] D1
- [x] D2
- [x] D3
- [x] D4
- [x] D5

## Remaining legacy roots
**Deleted:** `planning/`, `generation/`, `builder/`, `learning/`, `telemetry/`

**Justified exceptions (Unit path still requires):**
- `core/` — auth/profile/prompts/shares routes + entities/repos
- `contracts/`, `resource_specs/`, `media/`
- `v3_blueprint/`, `v3_execution/`, `v3_review/`
- FE `/studio*` Unit Print hop + `/api/v1/v3/*`

## Remaining shims
- `core.database.models` → `infra.database.models`
- Other historical `core.*` → infra re-exports where still present
- `learn.runtime.runtime_models` → infra ORM classes

## Data-retirement items
- ACTIVE retained: learning_packs, pack_items, generation_steps, v3_trace_*, concept_cards
- DROPPED (D4): skeleton_shadow_records

## Unknown blockers
- none

## Canonical backend shape (achieved + exceptions)
```
app.py
application/
curriculum/
print/
learn/
infra/
# justified exceptions: contracts, core, media, resource_specs, v3_*
```

Program status: **D0–D5 PASS. STOP.**

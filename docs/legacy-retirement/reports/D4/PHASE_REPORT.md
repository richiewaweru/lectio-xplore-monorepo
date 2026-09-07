# D4 Report — Database Dependency Retirement

Status: PASS

## Starting state
- after D3 PASS @ `2aa7bdee` (dirty tree)
- ORM lived in `core/database/models.py` (42 tables); Alembic head `20260906_0039`
- D0 suspects: learning_packs, pack_items, skeleton_shadow_records, generation_steps, v3_trace_*

## Classification (inspect-proven)

| Table | Class | Notes |
|---|---|---|
| users, student_profiles, units*, path_*, teaching_*, unit_groups, resource_compositions, lesson_actuals, marks_entries, concepts, concept_cards, lesson_provenance, generations, editable_lessons, learn_releases, learn_* runtime, llm_calls, lesson_shares, prompt_overrides, v2_audit_events | **ACTIVE** | Unit curriculum / Print / Learn |
| learning_packs | **ACTIVE** | Unit prepare + Unit Print `/api/v1/v3` |
| pack_items | **ACTIVE** | Unit Print + curriculum approved_items/outcomes |
| generation_steps | **ACTIVE** | Unit Learn component_lectio + Print planning persistence |
| v3_trace_runs / v3_trace_events | **ACTIVE** | Unit Print hop telemetry |
| skeleton_shadow_records | **DROP_SAFE** (was HISTORICAL_DATA_ONLY) | Optional writer; readers retired D3 |

No MIGRATE_DATA_THEN_DROP items this phase — pack/item schema still required by Unit Print hop.

## Subsystems handled
1. Moved ORM ownership to `infra/database/models.py`; `core/database/models.py` re-export shim
2. Inlined Learn runtime ORM into infra (domain-guard safe); `learn.runtime.runtime_models` re-exports
3. Disabled `v2_skeleton_shadow_enabled` default; noop `v3_blueprint.shadow`
4. Alembic `20260907_0040` drops `skeleton_shadow_records` (history preserved; prior migrations intact)
5. Migrated live DB to head

## Consumers migrated
- Alembic `env.py` → `infra.database.models.Base`
- `infra.database` package exports from infra models
- Learn runtime consumers unchanged via shim

## Routes/jobs/telemetry/config retired
- Shadow write path removed from stage1 retry; flag default False
- No route unmounts (D3 already did)

## DB impact
- Tables: **41** in ORM metadata (was 42)
- Dropped: `skeleton_shadow_records`
- Head: `20260907_0040`
- Migration history: **preserved** (no version files deleted)

## Deletions
- ORM class `SkeletonShadowRecordModel`
- Shadow persistence body (noop stubs remain for import compatibility until D5)

## Compatibility shims retained
- `core.database.models` → infra
- `learn.runtime.runtime_models` → infra Learn ORM classes
- ACTIVE pack/item/trace tables retained for Unit Print

## Tests
| Command | Result |
|---|---|
| `pnpm program:domain-guards` | PASS |
| `alembic upgrade head` | PASS → `20260907_0040` |
| Focused Unit-path + shadow + capabilities pytest | PASS 77 |

## Residual risks
- learning_packs / pack_items / concept_cards remain ACTIVE until Unit Print is re-owned without pack tables (post-D5 product work)
- `core.database.models` shim still exists for import churn (D5)
- Scripts like `run_v2_shadow_gate.py` are obsolete (D5 delete)

## Ending state
- safe for next phase: YES
- Next: D5 — delete proven-retired trees + zero-legacy guards

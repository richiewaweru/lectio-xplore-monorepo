# P02 Report — Stage contracts and safe admission

## Baseline / implementation
- Reviewed baseline: `a6b75e33`
- Parent tip before phase: `1a1a5ed7` (P01)
- Implementation: uncommitted on `fix/lectio-reliability-health` at report time; SHA stamped after commit

## Intent
Admit Learn before provider work; caller-scoped admission/effect keys; domain stage graphs; additive migration; Builder save/publish effect idempotency.

## Files changed
- `application/unit_lesson/stage_registry.py` (new) — Print/Learn stage graphs; approval waits not claimable
- `application/unit_lesson/effect_keys.py` (new) — caller effect key store
- `application/unit_lesson/realizations.py` — admission_request_key + payload conflict
- `application/unit_lesson/realize_learn_handoff.py` / `realize_print_handoff.py` — wire keys; 409 on conflict
- `learn/generation/native_execution.py` — admit-before-provider (from earlier P02 work)
- `learn/generation/units_routes.py`, `print/http/v3_studio/router.py` — `Idempotency-Key`
- `learn/authoring/builder/routes.py` — `expected_updated_at` + save effect keys
- `learn/publishing/release_routes.py` — publish effect keys
- `infra/database/models.py` — admission columns + `CallerEffectKeyModel`
- Migration `20260913_0042` (infra + core mirrors)
- `tests/application/test_p02_admission_stages.py`

## Migrations
- Additive: `native_realizations.admission_request_key`, `admission_payload_hash`; partial unique index when key present (Postgres)
- New table `caller_effect_keys`
- Rollback: drop index/columns/table (documented in Alembic downgrade)
- Existing realizations remain readable with NULL keys

## Commands
| cwd | command | exit | log |
|---|---|---|---|
| `apps/textbook-agent/backend` | `uv run pytest tests/application/test_p02_admission_stages.py tests/application/test_p03_realization_gates.py -q --tb=short` | 0 | `docs/lectio-reliability-health/evidence/p02-pytest.txt` (11 passed) |

## Gate results
| Gate | Result | Evidence |
|---|---|---|
| G05 | PASS | stage registry unknown/illegal/approval-wait tests |
| G06 | PASS | additive migration; create_all + existing admit identity tests still green |
| G07 | PASS | request-key replay, payload conflict, concurrent one-row |
| G08 | PASS | effect key replay/conflict; builder expected_updated_at; publish key storage |

## Failures / fixes
None in focused suite after implementation.

## Unresolved
Full backend validate_repo not re-run in this phase window (deferred to phase closeout / P06). Product depth for orchestration run/item/attempt/event tables deferred — extended existing realization + effect-key records instead.

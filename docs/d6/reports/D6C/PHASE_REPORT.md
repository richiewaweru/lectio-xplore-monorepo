# D6C Report — Learn Distribution + Runtime

Status: PASS

## Starting state
- after D6B PASS
- branch: `refactor/domain-ownership`
- sha: `c2f8a5cf0202bb1d52658a077a20de68f77e38d7`

## Test flow implemented
Publish LearnRelease A/B → create class + learners A/B → rolling assignment on A → assert recipient/instance linkage → load intended release → submit attempt → complete → analytics overview + lesson overview → cross-learner 403 → self-started instance on release B documents LRN-007 over-broad class aggregation.

## Production services exercised
- `learn.publishing` releases
- `learn.runtime.class_service` classes/assignments/`ensure_assignment_instance`
- `learn.runtime.runtime_service` attempts/complete
- `learn.analytics.insight_service` class/lesson overview

## External dependencies mocked
- None beyond test auth/session overrides (no LLM)

## Assertions
- Assignment creates recipient rows with `learning_instance_id`
- Instance `learn_release_id` matches assigned release; document hash stable
- Attempts/progress persist; completion updates recipient under current semantics
- Analytics endpoints return for the tested class/release
- Learner B cannot read learner A instance (403)
- Learner A can hold both assigned + self-started instances (LRN-007 documented)

## Failures found
| Failure | Classification | Canonical owner | Debt ID |
|---|---|---|---|
| `from learn.runtime_service import _utcnow` fails (`import *` skips `_` names) | refactor wiring regression (minimal fix) | `learn/runtime/runtime_routes` | LRN-010 |
| Analytics includes self-started instances for class learners | pre-existing product defect (asserted as-is) | `learn/analytics` | LRN-007 |

## Minimal fixes made
- [`runtime_routes.py`](apps/textbook-agent/backend/src/learn/runtime/runtime_routes.py): import `_utcnow` from `learn.runtime.runtime_service`.
- Added `tests/routes/test_d6c_learn_runtime_chain.py`.

## Commands/results
```
uv run pytest tests/routes/test_d6c_learn_runtime_chain.py -q
→ 1 passed
```

## Ending state
- safe for next subphase: YES

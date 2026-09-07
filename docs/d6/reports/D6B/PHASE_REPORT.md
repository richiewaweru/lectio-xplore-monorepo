# D6B Report — Unit → Learn → Builder → Publish

Status: PASS

## Starting state
- after D6A PASS
- branch: `refactor/domain-ownership`
- sha: `c2f8a5cf0202bb1d52658a077a20de68f77e38d7`

## Test flow implemented
Unit prepare (`grade4-photosynthesis-path.json`) → assert `control.pipeline=component_lectio` → admit Learn-compatible structural plan on the Unit-owned generation → `run_component_lectio_execution` with deterministic executors → validate Learn document → Builder GET/PUT/reload → draft preview non-mutation → Publish v1 → edit → Publish v2 (v1 immutable) → Units open-builder.

## Production services exercised
- `application.unit_lesson.prepare_path_lesson` / `dispatch.initialise_path_generation`
- `learn.generation.component_lectio.service.run_component_lectio_execution`
- `learn.authoring.builder` HTTP CRUD
- `learn.publishing` release publish/list/get
- `learn.generation.units_routes` status + open-builder

## External dependencies mocked
- Path structural planner / component selector
- Component Lectio section/question/visual executors (`_exec_kwargs`)
- Test DB session factory bound into Component Lectio persistence

## Assertions
- Unit prepare admits Component Lectio
- Generated document passes `validate_lesson_document`
- Builder edit persists across reload
- Draft GET does not change release/instance/attempt counts
- v1 hash/body unchanged after v2 publish

## Failures found
| Failure | Classification | Canonical owner | Debt ID |
|---|---|---|---|
| Prepare `native_whole_lesson` context overwrite clobbered form/signals | refactor wiring regression (minimal fix applied) | `application/unit_lesson/dispatch` | ARCH-004 |
| Print skeleton roles (organise/guided/…) are not Learn resource-spec roles | pre-existing product/architecture | `application/unit_lesson`, `learn/generation` | ARCH-005 |

## Minimal fixes made
- [`application/unit_lesson/dispatch.py`](apps/textbook-agent/backend/src/application/unit_lesson/dispatch.py): stop shallow-replacing `context` when setting Print native flags; merge `native_whole_lesson` into preserved context.
- Added `tests/routes/test_d6b_unit_learn_publish.py`.

## Commands/results
```
uv run pytest tests/routes/test_d6b_unit_learn_publish.py -q
→ 1 passed
```

## Ending state
- safe for next subphase: YES

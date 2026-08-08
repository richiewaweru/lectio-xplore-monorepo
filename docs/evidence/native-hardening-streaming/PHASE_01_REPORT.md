"""Phase 01 report — path terminology + legality projection.

## Files changed
- `apps/textbook-agent/backend/src/planning/models.py` — draft/canonical scope gain `terminology`
- `apps/textbook-agent/backend/src/planning/validation.py` — normalize/dedupe terminology
- `apps/textbook-agent/backend/src/planning/service.py` — persist + round-trip terminology (no wipe)
- `apps/textbook-agent/backend/resources/prompts/path-planner.md` — prompt populates terminology
- `apps/textbook-agent/backend/src/planning/whole_lesson/legality.py` — `project_slot_intent_policy`
- `apps/textbook-agent/backend/src/planning/whole_lesson/teaching_agent.py` — prompt/repair get policy
- `apps/textbook-agent/backend/tests/planning/test_phase01_terminology_legality.py` — C01–C08

## Tests
```
pytest tests/planning/test_phase01_terminology_legality.py
8 passed
```

## Before / after
- Before: `persist_path_plan` always set `UnitScopeContractModel.terminology = []`
- After: persists `plan.scope.terminology`; `canonical_plan_from_version` round-trips it
- Before: teaching repair lacked exact legal options projection
- After: `slot_intent_policy` derived from same `LessonLegalitySnapshot`/hash for prompt + repair

## Retry budget
Unchanged.

## Remaining risks
- Live path planner must actually emit non-empty terminology when domain vocab exists (prompt-only; no schema minimum).
- Brief grounding still falls back to must_establish tokens when terminology is legitimately empty.
"""
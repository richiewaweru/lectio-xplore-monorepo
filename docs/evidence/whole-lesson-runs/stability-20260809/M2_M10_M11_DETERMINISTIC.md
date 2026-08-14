# M2, M10, and M11 deterministic evidence (2026-08-09)

## Scope

This gate covers deterministic native-only reachability, telemetry plumbing, and
current-revision reload proof. It does not claim the required authenticated browser,
provider, PDF-inspection, visual-provider, or worker-restart evidence.

## M2 native-only product boundary

Implemented product decisions:

- `/units` is the authenticated Home and the only current New Lesson destination.
- `/lessons` is redirect-only; blank `/studio` redirects to `/units` without starting work.
- Studio has no Builder conversion/action or direct contract-v1 creation surface.
- Path preparation always persists native contract v2, independent of rollout flags.
- Direct contract-v1 start returns `410` before persistence.
- Approval requires native v2 plus immutable path provenance before state/task mutation.
- Variant children inherit native identity and contract v2.
- Builder rejects native/current source generation IDs.
- Historical v1 regenerate and retry-section are read-only (`409`); native retry maps to
  the native checkpoint endpoint.

Frontend integrated command:

```powershell
pnpm --dir apps/textbook-agent/frontend test -- "src/lib/auth/routing.test.ts" "src/lib/components/workspace/NewLessonSplitButton.test.ts" "src/routes/page.test.ts" "src/routes/dashboard/page.test.ts" "src/routes/settings/page.test.ts" "src/routes/lessons/page.test.ts" "src/routes/units/page.test.ts" "src/routes/studio/page.test.ts" "src/routes/studio/generations/[id]/page.test.ts"
```

Result: **9 files passed, 46 tests passed**. `pnpm check` separately reported zero errors
and three pre-existing unused-CSS warnings in `routes/units/[id]/+page.svelte`.

Backend gate evolution:

1. The first integrated run exposed four stale tests that patched removed legacy retry code
   or expected legacy regeneration to succeed: 67 passed, 4 failed, 1 deselected.
2. Those tests were converted to the read-only/no-mutation contract and native retry API.
3. Integrated M2 selection then passed: **48 passed, 1 deselected**.
4. The final deselected stale `resume_stage2` test was replaced with a native v2 teaching
   timeout regression. Full `test_v3_chunked_lifecycle.py`: **25 passed**, no deselection.

The broader combined backend command (M2 plus telemetry) passed **71 tests** while the last
stale lifecycle test was still deselected; the subsequently changed lifecycle file passed all
25 tests. Changed backend files and tests pass Ruff.

Static current-product reachability audit:

- no current navigation link to `/builder` or blank `/studio`;
- no Studio imports/calls to `createBuilderLesson`, `startChunkedPlan`, or
  `v3StructuralPlanToBuilderDocument`;
- historical `/builder/**` and `/units/legacy/**` routes remain direct/read-only compatibility
  surfaces and are not linked from the current workspace;
- the historical API helper `startChunkedPlan` remains unused, while its server endpoint is
  quarantined with `410`.

## M10 telemetry plumbing

Implemented:

- `run_llm` no longer synthesizes a generation ID from a trace ID;
- pre-generation constructor, path plan/edit, and path preparation publish unique
  `TraceRegisteredEvent` / `TraceClosedEvent` pairs with the known user;
- native structural preparation receives that trace;
- failed call events include error class; the existing `llm_calls` ledger persists retryability
  and preserves class in the existing error text (no parallel telemetry system/schema redesign).

Command:

```powershell
uv run pytest tests/core/test_llm_runner.py tests/services/test_telemetry_service.py tests/planning/test_planning_trace_events.py -q --tb=short
```

Result: **8 passed**, one pre-existing Pydantic warning.

Coverage status: constructor/path/structural use registered pre-generation user traces; items,
teaching, form, and page writers pass actual generation IDs where available. The image-provider
visual dispatch itself is not yet represented as an `llm_calls` row and remains an explicit live
coverage gap for M10 acceptance.

## M11 visual-safe reload proof

Implemented:

- any pending/failed/retried/material visual mutation invalidates prior final and candidate hashes;
- final visual completion remains `awaiting_visuals` until the current revision is persisted,
  loaded through a fresh session, validated, canonically hashed, and compared under revision lock;
- only equal current-revision hashes transition the generation to `ready`.

Results:

- visual completion + document fencing: **12 passed**;
- delivery, visual dispatch, and visual/PDF routes: **22 passed**;
- resume and assembly: **7 passed**;
- Ruff: all changed repository/test files pass.

## Remaining acceptance

- Browser proof B for Home/New native-only flow.
- Live telemetry rows with zero relevant dropped-attribution warnings, including visual coverage.
- Live post-visual equal hashes exposed in status/evidence.
- M3-M9 targeted scenarios and the four final browser runs.

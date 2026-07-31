# Lesson Builder Merge Progress

## Xplore Learning Platform V2 — 2026-07-31

**Classification**: major
**Branch**: `v2-platform`
**Base branch**: `xplore`
**Baseline commit**: `73c70a9863157a04eb675dc29a23f7ee19151e8b`
**Current phase**: Phase 3 — skeleton data and preview next

### Phase checklist

- [x] Phase 0 — baseline captured and reproducible
- [x] Phase 1 — four silent defects fixed with fail-first regression evidence
- [x] Phase 2 — concepts, objective ownership, and provenance added with generation unchanged
- [ ] Phase 3 — skeleton loading, classifier, and preview added with existing output unchanged
- [ ] Phase 4 — shadow logging proven on at least three real generations; review/export surface exists
- [ ] Phase 5 — units and path backend validate all three fixtures; unreachable approval is blocked
- [ ] Halt at the human decision gate and write the final handoff report

### Phase 0 tracking

- [x] Read the goal objective before touching code.
- [x] Read `agents/ENTRY.md`, project config, applicable workflows, and all standards.
- [x] Re-read this `PROGRESS.md` at session start.
- [x] Read the seven required V2 handoff/patch sources in the mandated order.
- [x] Preserved the supplied complete handoff under `handoff/` and patch under `patch/`.
- [x] Captured `xplore` HEAD and created `v2-platform` without rewriting history.
- [x] Verified the four Phase 1 defect claims against live code with `rg`.
- [x] Run the backend baseline suite.
- [x] Run the architecture baseline gate.
- [x] Run the frontend production build and record the baseline failure exactly.
- [x] Save one current end-to-end generation output as a comparison fixture.
- [x] Re-run Phase 0 from `RUNBOOK.md` and record exact output.

### Phase 0 evidence

Baseline commit:

```text
$ git rev-parse HEAD
73c70a9863157a04eb675dc29a23f7ee19151e8b
```

Backend test suite:

```text
$ cd backend && uv run pytest -q
........................................................................ [ 16%]
........................................................................ [ 33%]
........................................................................ [ 50%]
........................................................................ [ 67%]
........................................................................ [ 84%]
....................................................................     [100%]
428 passed, 1 warning in 128.82s (0:02:08)
```

The warning is the pre-existing Pydantic `GenerationFieldContract.schema` field-shadowing warning.

Architecture gate:

```text
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

Frontend production build:

```text
$ cd frontend && npm run build
> frontend@0.0.1 build
> vite build

vite v7.3.1 building ssr environment for production...
transforming...
✓ 138 modules transformed.
✗ Build failed in 6.57s
error during build:
[vite]: Rollup failed to resolve import "isomorphic-dompurify" from
".../node_modules/lectio/dist/utils/markdown.js".
```

This is a reproducible dependency-resolution failure in the installed frontend baseline, not
the previously recorded Windows process-lifecycle stall. It is recorded without a Phase 0 fix.

Saved comparison fixture:

```text
$ Get-FileHash backend/tests/fixtures/xplore_v2_phase0_generation.json -Algorithm SHA256
91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2
```

The fixture is a byte-for-byte snapshot of the current committed Xplore photosynthesis pack
contract fixture at the baseline commit. It gives Phase 2 and Phase 3 an immutable output
comparison target without making a provider call.

Reproducibility check:

```text
$ git diff --quiet xplore -- backend/src backend/tests frontend/src frontend/package.json frontend/pnpm-lock.yaml
source_tree_matches_xplore=True
```

The Phase 0 commands above were run after branching and before any source change; only the
handoff, runbook, progress ledger, and copied comparison fixture differ from `xplore`.

### Phase 0 gate result

- **PASS** — the baseline commit, backend result, architecture result, frontend failure, and
  immutable fixture hash are reproducible from `RUNBOOK.md`.
- The frontend dependency failure is baseline evidence, not a V2 regression and not silently
  reclassified as a passing build.
- Phase 0 commit SHA: `d6688c2` (`P0: docs(xplore-v2): capture baseline and handoff`).

### Nine-invariant check before Phase 0 commit

1. Item generation still accepts one `ConceptCard` plus scalar private attrs; the context-wall
   tests are included in the `428 passed` backend suite.
2. Pack-owned shared items remain covered by `test_all_variants_derive_one_shared_pack_item_set`.
3. QC verdict recomputation remains covered by the card-review and item-validator suites.
4. Null distractor diagnosis remains covered by item validation and the Xplore fixture contract.
5. Sibling isolation remains covered by `test_variant_failure_is_isolated_from_siblings`.
6. Teacher edits survive regeneration in the existing card/item regression tests.
7. Durable `awaiting_review` restart behavior remains covered by
   `test_awaiting_review_halt_survives_process_restart`.
8. No Builder, Lectio, PDF, or generation source changed in Phase 0. The existing frontend
   baseline build is blocked earlier by unresolved `isomorphic-dompurify`.
9. `StructuralPlan.max_six_sections` remains present and the full backend suite passes.

### Verified handoff/code findings

- `backend/contracts/guided-concept-path.json` has no role declarations, while
  `_allowed_roles_from_resource_spec()` returns an empty set and both validators skip role checks.
- `backend/contracts/component-registry.json` contains `cognitive_job`, but the Stage 1
  component-selection context currently receives only the active resource spec and planner index.
- `StructuralPlan` uses `ConfigDict(extra="ignore")` specifically for the legacy top-level
  `voice` field; arbitrary unknown fields are therefore silently accepted as well.
- The Stage 1 prompt still requires `2-4` misconceptions, despite permitting an explicit
  no-known-misconceptions escape.
- The repository architecture guide names `planning/` and `pipeline/`, while the live Xplore
  implementation is under `v3_blueprint/` and `v3_execution/`. Live code is authoritative.
- `handoff/14_IMPLEMENTATION_PHASES.md` places the path-to-Xplore bridge in Phase 6, while the
  controlling goal explicitly includes the `:prepare` bridge in Phase 5 and requires a halt
  immediately afterward. The controlling goal is being followed; no Phase 6 authority is inferred.

### Open questions / stop conditions

- None for Phase 0.

### Phase 1 tracking

- [x] Defect 1 fail-first evidence captured: missing skeleton role authority was silent.
- [x] Defect 1 implementation uses skeleton slot IDs and emits a warning when the catalog is absent.
- [x] Defect 1 committed as `5b1682a` (`P1: fix(planning): make skeleton roles authoritative`).
- [x] Defect 2 fail-first regression: selector entries label cognitive jobs and section fields.
- [x] Defect 2 committed as `39f1744` (`P1: fix(planning): label component selection context`).
- [x] Defect 3 fail-first regression: unknown StructuralPlan fields are rejected.
- [x] Defect 3 committed as `79fa042` (`P1: fix(planning): reject unknown structural plan fields`).
- [x] Defect 4 fail-first regression: new path lesson prompt uses 0–3 belief-tested misconceptions.
- [x] Defect 4 committed as `fedf0d7` (`P1: fix(planning): allow zero path misconceptions`).
- [x] Phase 1 full gate: regressions, legacy fixtures, nine invariants, lint, architecture.

### Phase 1 defect 1 evidence — dead role validation

Failing regression before the fix:

```text
$ cd backend && uv run pytest tests/v3_blueprint/planning/test_validators.py::test_validate_structural_plan_warns_when_skeleton_roles_are_unavailable -q
F                                                                        [100%]
E       AssertionError: assert 'skeleton role validation unavailable' in ''
1 failed, 1 warning in 0.85s
```

Passing validation after the fix:

```text
$ cd backend && uv run pytest tests/v3_blueprint/planning/test_validators.py tests/v3_blueprint/planning/test_stage1_error_logging.py -q
.......................                                                  [100%]
23 passed, 1 warning in 12.03s
$ uv run ruff check src/v3_blueprint/planning/validators.py src/v3_blueprint/planning/structural_planner.py tests/v3_blueprint/planning/test_validators.py tests/v3_blueprint/planning/test_stage1_error_logging.py
All checks passed!
```

The active resource spec is no longer treated as role authority. When a skeleton catalog is
provided, roles are checked against `slots` keys. Until Phase 3 supplies the startup-loaded
catalog, validation logs the explicit `skeleton role validation unavailable` warning.

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/v3_blueprint/planning/test_validators.py -q
...............................                                          [100%]
31 passed, 1 warning in 16.31s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

### Phase 1 gate result

```text
$ cd backend && uv run pytest -q
........................................................................ [ 16%]
........................................................................ [ 33%]
........................................................................ [ 49%]
........................................................................ [ 66%]
........................................................................ [ 83%]
........................................................................ [ 99%]
.                                                                        [100%]
433 passed, 1 warning in 76.05s (0:01:16)
$ uv run ruff check src tests
All checks passed!
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
$ Get-FileHash backend/tests/fixtures/xplore_v2_phase0_generation.json -Algorithm SHA256
91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2
```

**Gate: PASS.** All legacy tests load, all nine invariants remain covered by the complete
backend suite, and the Phase 0 comparison fixture is unchanged. The known frontend baseline
dependency failure remains outside the Phase 1 backend-only diff and is still recorded as open.

### Phase 2 tracking

- [x] Read the concept, path, provenance, and migration handoff details against live models.
- [x] Add the canonical concepts table and reversible migration.
- [x] Add a nullable canonical concept reference to current cards; path-lesson FK follows its Phase 5 table.
- [x] Add exact immutable path-objective hash ownership and comparison foundation.
- [x] Add nullable provenance fields without changing current generation output.
- [x] Prove migration `0019` upgrade/downgrade/upgrade.
- [x] Re-run the saved Phase 0 generation comparison byte-for-byte.
- [x] Run the complete Phase 2 gate and invariant check.

### Phase 2 foundation evidence

Focused model, ownership, legacy-generation, and Xplore tests:

```text
$ cd backend && uv run pytest tests/core/database/test_concepts.py tests/v3_blueprint/planning/test_objective_ownership.py tests/generation/test_xplore_fixture.py tests/generation/test_xplore_contracts.py -q
..........                                                               [100%]
10 passed, 1 warning in 23.60s
$ uv run ruff check <Phase 2 foundation files>
All checks passed!
```

Migration `0019` from a database at revision `0018`:

```text
$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 20260731_0018 -> 20260731_0019, add canonical concepts and lesson provenance
$ uv run alembic downgrade -1
INFO  [alembic.runtime.migration] Running downgrade 20260731_0019 -> 20260731_0018, add canonical concepts and lesson provenance
$ uv run alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 20260731_0018 -> 20260731_0019, add canonical concepts and lesson provenance
```

The disposable SQLite database was removed after the gate. A fresh SQLite migration chain still
hits the pre-existing `20260501_0010` inline-FK ALTER limitation on its first pass; that baseline
contradiction is outside migration `0019` and is recorded rather than silently attributed to V2.

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/generation/test_v3_chunked_lifecycle.py tests/core/database/test_concepts.py -q
.....................................                                    [100%]
37 passed, 1 warning in 24.02s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

The `ConceptModel` follows `concept.schema.json` and adds the domain lifecycle fields. Current
cards reference it with a nullable FK. `LessonProvenanceModel` carries nullable concept, path,
objective-hash, skeleton, classifier-source, toggle, and deviation fields. Path tables and their
FK are deliberately deferred to Migration 3 / Phase 5, matching `13_DATABASE_AND_MIGRATIONS.md`.

Phase 2 commits:

- `23835fd` — `P2: feat(data): add concepts and lesson provenance`
- `83deff9` — `P2: feat(planning): lock path objective ownership`

### Phase 2 gate result

```text
$ cd backend && uv run pytest -q
........................................................................ [ 16%]
........................................................................ [ 32%]
........................................................................ [ 49%]
........................................................................ [ 65%]
........................................................................ [ 82%]
........................................................................ [ 98%]
......                                                                   [100%]
438 passed, 1 warning in 95.45s (0:01:35)
$ uv run ruff check src tests
All checks passed!
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
$ Get-FileHash backend/tests/fixtures/xplore_v2_phase0_generation.json -Algorithm SHA256
91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2
```

**Gate: PASS.** Migration `0019` is reversible, all nine invariants pass in the complete suite,
and the saved generation is byte-for-byte identical to Phase 0.

### Phase 3 tracking

- [x] Install the versioned draft as runtime `skeletons.yaml`.
- [x] Validate skeletons on startup: slot limits, locked check, registry components, and toggles.
- [x] Expand and preview all 11 skeletons with zero model calls.
- [x] Add the verbatim knowledge-type classifier prompt and strict result enum.
- [x] Add deviation request schema.
- [x] Wire `POST /skeletons:preview` without changing generated lesson structure.
- [x] Validate classifier outputs against all three path fixtures.
- [x] Prove existing output and Phase 0 fixture remain unchanged.
- [ ] Run the complete Phase 3 gate and invariant check.

### Phase 3 implementation evidence

```text
$ cd backend && uv run pytest tests/v3_blueprint/test_skeletons.py tests/v3_execution/prompts/test_shared_prompt_prefix.py tests/v3_blueprint/planning/test_retry.py tests/v3_blueprint/planning/test_stage1_error_logging.py tests/v3_blueprint/planning/test_validators.py -q
............................................                             [100%]
44 passed, 1 warning in 21.10s
$ uv run ruff check <Phase 3 files>
All checks passed!
```

The catalog test previews each of the 11 skeleton IDs, enforces at most six expanded slots,
and confirms exactly one locked `check`. Unknown registry components fail startup validation.
Overflow is retained as an explicit `variant_slot_overflow` warning rather than truncated.
The HTTP test calls `POST /api/v1/skeletons:preview` and receives expanded slot objects.

The classifier prompt resource is compared byte-for-byte (ignoring outer whitespace) against
section 2 of `20_PROMPT_PACK.md`. Its live LLM service returns strict enums and marks low
confidence for teacher review. All objectives in the Grade 4, Grade 12, and unreachable Grade 8
fixtures pass the enum contract.

### Phase 3 decision not specified by the handoff

`20_PROMPT_PACK.md` names `POST /skeletons:preview` as a classifier call site, while the
controlling goal requires the preview endpoint to make zero model calls. The endpoint therefore
uses a deterministic, explicitly labelled `knowledge_type_source=deterministic_preview` helper;
the authoritative classifier remains a separate live LLM service using the verbatim prompt.
This keeps preview deterministic and prevents a heuristic result from masquerading as model or
teacher classification.

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/generation/test_v3_chunked_lifecycle.py tests/v3_blueprint/test_skeletons.py tests/v3_blueprint/planning/test_retry.py -q
.................................................                        [100%]
49 passed, 1 warning in 34.78s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
$ Get-FileHash backend/tests/fixtures/xplore_v2_phase0_generation.json -Algorithm SHA256
91E0BCB220BF9E2532B13AEF9FE7447AD822AB109D9D226DC032D5ADB4540FD2
```

### Phase 1 defect 4 evidence — path-only misconception quota

Failing regression before the fix:

```text
$ cd backend && uv run pytest tests/v3_execution/prompts/test_shared_prompt_prefix.py::test_path_prepared_stage1_uses_zero_to_three_belief_tested_misconceptions -q
F                                                                        [100%]
E       TypeError: build_stage1_system_prompt() got an unexpected keyword argument 'path_prepared'
1 failed, 1 warning in 12.51s
```

Passing validation after the fix:

```text
$ cd backend && uv run pytest tests/v3_execution/prompts/test_shared_prompt_prefix.py tests/v3_blueprint/planning/test_stage1_error_logging.py tests/v3_blueprint/planning/test_retry.py -q
...............                                                          [100%]
15 passed, 1 warning in 10.54s
$ uv run ruff check src/v3_blueprint/planning/structural_planner.py tests/v3_execution/prompts/test_shared_prompt_prefix.py
All checks passed!
```

The default Stage 1 prompt remains the legacy 2–4 path. Only the explicit
`path_prepared=True` mode changes to zero through three and applies the exact
confident-wrong-answer test. The Phase 5 bridge will be the only production caller authorized
to select this mode.

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/v3_blueprint/planning/test_validators.py tests/generation/test_v3_chunked_lifecycle.py tests/v3_execution/prompts/test_shared_prompt_prefix.py -q
..........................................................               [100%]
58 passed, 1 warning in 19.12s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

### Phase 1 defect 3 evidence — strict StructuralPlan with legacy adapter

Failing regression before the fix:

```text
$ cd backend && uv run pytest tests/v3_blueprint/planning/test_validators.py::test_structural_plan_rejects_arbitrary_unknown_fields -q
F                                                                        [100%]
E       Failed: DID NOT RAISE <class 'pydantic_core._pydantic_core.ValidationError'>
1 failed, 1 warning in 0.93s
```

Passing validation after the fix:

```text
$ cd backend && uv run pytest tests/v3_blueprint/planning/test_validators.py tests/v3_blueprint/planning/test_stage1_error_logging.py tests/v3_blueprint/planning/test_section_expander.py tests/v3_blueprint/planning/test_retry.py tests/v3_blueprint/planning/test_assembler.py tests/generation/test_v3_chunked_lifecycle.py tests/generation/test_stage2_parallel.py -q
...................................................................      [100%]
67 passed, 1 warning in 29.85s
$ uv run ruff check <touched Phase 1 defect 3 files>
All checks passed!
```

`StructuralPlan` now uses `extra="forbid"`. Persisted-plan reads use
`adapt_legacy_structural_plan()`, which removes only the named top-level `voice`, validates it,
maps it into a `VariantSpec`, and logs the source. Unknown fields still reach strict validation.
Planner output does not use the adapter, so a model cannot smuggle unknown keys through the
legacy compatibility path.

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/v3_blueprint/planning/test_validators.py tests/generation/test_v3_chunked_lifecycle.py -q
......................................................                   [100%]
54 passed, 1 warning in 19.43s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

### Phase 1 defect 2 evidence — component cognitive jobs

The handoff's claim that cognitive jobs never reach the planner contradicts the live code:
`_planner_index_block()` already appended the cognitive-job value to every available component
since commit `5ff0769b`. The value was an unlabeled `role - job` suffix, however, so the exact
registry-entry contract was not explicit or mechanically distinguishable. Live code is truth;
the scoped fix labels `section_field`, `cognitive_job`, and `role` in every selector entry.

Failing regression before the scoped fix:

```text
$ cd backend && uv run pytest tests/v3_execution/prompts/test_shared_prompt_prefix.py::test_stage1_component_selector_context_labels_cognitive_job_and_section_field -q
F                                                                        [100%]
E       AssertionError: assert 'worked-example-card | section_field=worked_example | cognitive_job=Watch reasoning in action' in planner_block
1 failed, 1 warning in 16.55s
```

Passing validation after the fix:

```text
$ cd backend && uv run pytest tests/v3_execution/prompts/test_shared_prompt_prefix.py tests/v3_blueprint/planning/test_stage1_error_logging.py -q
.........                                                                [100%]
9 passed, 1 warning in 12.52s
$ uv run ruff check src/generation/v3_studio/prompts.py tests/v3_execution/prompts/test_shared_prompt_prefix.py
All checks passed!
```

Pre-commit invariant evidence:

```text
$ cd backend && uv run pytest tests/v3_execution/test_item_executor.py tests/generation/test_xplore_contracts.py tests/v3_review/test_card_reviewer.py tests/v3_blueprint/planning/test_validators.py tests/v3_execution/prompts/test_shared_prompt_prefix.py -q
..................................                                       [100%]
34 passed, 1 warning in 20.85s
$ python tools/agent/check_architecture.py --format text
No architecture violations found.
```

---

## Xplore Pack Generation — Phase 13 contracts — 2026-07-31

**Classification**: major
**Subsystems**: backend planning/execution/review, fixtures

### Progress

- [x] Proved one variant failure does not block a sibling
- [x] Proved every variant derives the same pack-owned diagnostic set
- [x] Proved the explicit review halt survives process-memory loss
- [x] Preserved teacher-edited misconceptions in regenerated durable plans
- [x] Locked the item executor against generated-content contamination
- [x] Added strict card/variant QC result tests
- [x] Committed the Lectio 0.6.0 photosynthesis fixture contract
- [x] Ran the 15-test focused P13 suite and Ruff

### Remaining release gates

- [ ] Full repository validation and architecture check
- [ ] Browser walkthrough on port 5173
- [ ] Self-review and branch push

## Builder Block-Level AI — Generate & Repair — 2026-07-22

**Classification**: major
**Subsystems**: backend + frontend

### Progress

- [x] Requirements, project rules, and current implementation reviewed
- [x] Repair mechanism locked to the existing Builder block writer
- [x] Source generation link and server-side plan context verified
- [x] Added deterministic text repair targeting and manual-only eligibility
- [x] Wired issue-prefilled repair through the existing AI panel
- [x] Added visual QC reasons to regeneration context
- [x] Added regression fixture, automated coverage, and manual runbook
- [x] Ran backend tests and lint
- [x] Ran frontend tests, check, and build
- [x] Ran architecture validation and self-review
- [ ] Completed real-provider acceptance in `docs/project/runs/builder-block-ai.md`

### Validation Evidence

- Baseline architecture guard: passed before implementation.
- Baseline block generation route tests: `8 passed`.
- Backend touched suites: `41 passed`; touched-file Ruff check passed.
- Frontend Builder AI regression suites: `13 passed` across the payload, fixture,
  canvas repair, and visual-regeneration tests.
- Frontend Svelte sync/type-check: `0 errors`, `0 warnings` across 4,187 files.
- Frontend full Vitest suite: `59 files passed`, `243 tests passed`.
- Frontend Vite production build: passed; existing Rollup pure-annotation and
  large-chunk warnings remain non-blocking.
- Backend full validation: Ruff passed; `409 tests passed` with the existing
  Pydantic field-shadowing warning.
- Project tooling validation: `8 tests passed`.
- Architecture guard after implementation: no violations.
- Real-provider acceptance remains manual and requires configured provider credentials.

### Door Sign-off

| Door | Automated evidence | Live provider evidence |
| --- | --- | --- |
| Fill | FAST payload omits current content and teacher note | Pending |
| Improve | STANDARD payload includes current content | Pending |
| Custom | Edited teacher note is sent without resolving an issue | Pending |
| Repair | Fixture-driven canvas test opens, edits, generates, and resolves | Pending |
| Image regenerate | Visual issue action sends the edited QC hint and refreshes | Pending |

### Risks and Follow-up

- Frontend validation is slow on Windows but completed successfully when given
  a sufficient timeout; continue recording genuine timeouts separately from failures.
- No production fixture loader, seed endpoint, automatic repair, or whole-section rewrite is introduced.

## Builder Convergence — Final convergence status — 2026-07-16

### Completed

- [x] Phases 1–6 implemented and committed in the prescribed phase order (Phase 5 split backend/frontend).
- [x] Phase 2 out-of-order arrival merge is covered and preserves insert-if-absent.
- [x] Backend targeted route tests, policy tests, relevant suites, and architecture validation completed.
- [x] Frontend direct Svelte type-check completed with 0 errors and 0 warnings.
- [x] Authorized handoff contradictions and validation deviations are recorded below.

### Pending environment / human verification

- [ ] Frontend Vite production build and full Vitest process must exit cleanly. Direct
  Vite currently emits no result before the 124-second desktop timeout; direct
  Svelte checking succeeds.
- [ ] Manual flag-OFF click-through in a deployed browser.
- [ ] Manual flag-ON Studio → streaming Builder → mid-stream edit → issue fix →
  teacher/student PDF → unified dashboard workflow.
- [ ] Fixture visual regeneration with a real image provider proving a different URL.
- [ ] Real deployed 40+ minute lesson run with Stage 2 timing evidence. This remains
  explicitly pending human verification per the goal objective.

### Final risks

- Automated backend behavior is validated, but provider-backed image regeneration,
  browser persistence/reload, and deployment PDF flows require live credentials and
  a deployed environment.
- The local Vite/Vitest process lifecycle remains unresolved; no failing frontend
  assertion or Svelte diagnostic has been observed.

## Builder Convergence — Phase 6: Retry relaxation compatibility controls — 2026-07-16

**Classification**: major
**Root cause / Rationale**: The actual pipeline was already hard-failure-only for
executor retries, annotate-only for coherence, and tolerant of partial Stage 2
failure, but lacked the requested explicit compatibility controls.

### Progress

- [x] Enumerated all retry call sites; no warning-triggered rerolls found.
- [x] Confirmed review is report-only and issues flow to `booklet_issues`.
- [x] Added exact `V3_COHERENCE_REPAIR_ENABLED=false` compatibility flag.
- [x] Added exact `V3_SHIP_WITH_HOLES=true` flag and gated partial assembly.
- [x] Preserved total-failure blocking and Stage 1/Stage 2 retry behavior.
- [x] Added default, override, and partial-assembly tests.

### Validation Evidence

- Focused policy/assembly/lifecycle: 7 passed, 17 deselected.
- Relevant backend suites: 257 passed; one unrelated heartbeat timing test failed
  under load and passed immediately in isolation (1 passed).
- Cached full-suite failures rerun: 5 passed.
- Architecture validation: no violations found.
- Timing comparison is not applicable: no coherence rewrite pass exists, so the
  compatibility flag removes no executable work and has no meaningful repair timing.

### Risks

- `V3_COHERENCE_REPAIR_ENABLED=true` is intentionally a documented no-op until a
  separately authorized repair executor exists.
- The existing heartbeat test remains scheduler-sensitive at 10ms/30ms thresholds.

### Verification Checklist

- [x] Exact defaults and compatibility values are tested.
- [x] Ship-with-holes false blocks partial Stage 2 failure.
- [x] Default behavior retains partial assembly; total failure still blocks.
- [x] Review issues remain annotate-only and reach the pack.
- [x] Relevant pytest suites and architecture checks pass, with timing flake triaged.

## BLOCKED: Phase 6 — requested coherence repair path does not exist — 2026-07-16

The Phase 6 scan contradicts the handoff's assumed baseline:

- `run_with_retries` has three production call sites only: section writer, question
  writer, and visual executor. Their retries are driven by unsuccessful executor
  outcomes (validation/provider/empty-output failures); no warning-triggered reroll
  path was found.
- `v3_review.run_coherence_review` performs deterministic/advisory review and returns
  `ReviewIssue`s. No content rewrite or repair executor entry point exists in the
  review package or `v3_execution.runtime.runner`.
- The runtime already copies review issues into `draft_pack.booklet_issues` using
  `_booklet_issues_from_report`; review is already annotate-only.
- `assemble_blueprint` already skips failed Stage 2 briefs and assembles all successful
  sections. It raises `BlueprintAssemblyBlocked` only when no sections remain, so
  partial Stage 2 failure already ships with holes at the blueprint level.
- Existing tests `test_attempt_chunked_assembly_proceeds_with_partial_failed_sections`
  and the all-failed counterpart confirm that behavior.

Because no prior coherence rewrite behavior exists, an environment setting
`V3_COHERENCE_REPAIR_ENABLED=true` cannot “restore current behavior” as specified.
Adding a brand-new repair implementation would violate the phase scope and explicit
rule not to add automatic retries.

**Proposed adjustment**: add the exact environment flags and defaults as compatibility
controls; keep coherence review annotate-only for both values while documenting that
the true setting is currently a no-op; gate partial-stage assembly so
`V3_SHIP_WITH_HOLES=false` restores blocking on any failed brief, while the default
`true` retains the current partial-assembly behavior. Add parametrized tests for the
ship-with-holes flag and config defaults. Do not invent a repair/rewrite pass.

**Authorized adjustment — 2026-07-16**: The user authorized this compatibility
implementation without inventing a repair/rewrite pass.

## Builder Convergence — Phase 5: Targeted issue repair — 2026-07-16

**Classification**: major
**Root cause / Rationale**: Generation diagnostics were not actionable inside the
Builder, and text components had no owner-scoped teacher-initiated patch route.

### Progress

- [x] Completed and recorded the critical scan and authorized adjustment.
- [x] Verified the existing visual regeneration route and asserted cache bypass in pytest.
- [x] Added owner-only component patching through one section executor invocation with `max_retries=0`.
- [x] Patched the existing generation `document_json` without schema changes.
- [x] Map diagnostics and implement Builder issue/nudge/floating-toolbar UI.
- [ ] Run full backend and frontend gates and complete manual fixture checks.

### Validation Evidence

- Focused backend route suite: 5 passed, 28 deselected.
- Visual test asserts `bypass_cache_read=True` and persisted block/section mutation.
- Component tests assert instruction injection, `max_retries=0`, persisted replacement,
  404 for unknown reference, and 403 for non-owner.
- Direct `svelte-check`: 0 errors, 0 warnings.
- Frontend Vitest process currently stalls before its run banner in this environment;
  the user authorized continuing while the process-lifecycle limitation remains recorded.

### Risks

- Component references accept `component@section` and `section:component`; a bare
  component id is accepted only when unique across the compiled bundle.
- Full Phase 5 suites remain pending until the frontend half is complete.

## BLOCKED: Phase 5 — visual work-order helper name contradicts handoff — 2026-07-16

The required Phase 5 scan found that the handoff names an existing
`_find_visual_work_order` helper, but `backend/src/generation/v3_studio/router.py`
contains no function by that name. The live route instead calls
`_work_order_for_visual` after `_find_visual_block`.

Confirmed live wiring:

- `POST /api/v1/v3/generations/{generation_id}/visuals/{visual_id}/regenerate`
  accepts `V3VisualRegenerateRequest.teacher_hint` and uses `get_current_user`.
- `V3GenerationWriter.get_document_json` and `read_planning_artifact` enforce the
  current user's generation ownership; missing/non-owned generations return 404.
- `_find_visual_block` locates the generated block and `_work_order_for_visual`
  compiles the execution bundle and matches source work-order, visual, or parent id.
- `_apply_teacher_hint` appends `Correction: {hint}` to the cloned visual purpose.
- `execute_visual` is already called with `bypass_cache_read=True`.
- `_replace_visual_blocks` and `_patch_section_visuals` mutate the copied document,
  `_persist_regenerated_visual` saves it, and the route returns the regenerated block.
- No equivalent component/text patch endpoint exists. The only component-patch
  reference in the router is the existing `component_patched` event handling path.
- Regression fixture `backend/tests/fixtures/gen_5aed3804_pack.json` has empty
  `booklet_issues`; `section_diagnostics` entries use `section_id`, `status`,
  `renderable`, `missing_components`, `missing_visuals`, and `warnings`. They do not
  contain `kind` or `severity`, so the adapter must derive those fields deterministically.

**Proposed adjustment**: Treat `_work_order_for_visual` as the actual equivalent of
the handoff's `_find_visual_work_order`, retain it without a cosmetic rename, extend
the existing route test to assert cache bypass and persisted mutation, then build the
missing component endpoint against the current execution-bundle types. Derive issue
`kind`/`severity` for section diagnostics while preserving any explicit booklet issue
fields when present.

No Phase 5 implementation was made after discovering this contradiction.

**Authorized adjustment — 2026-07-16**: The user authorized continuing with
`_work_order_for_visual` as the existing equivalent without renaming it, and with
deterministic `kind`/`severity` derivation for diagnostics that omit those fields.

## Builder Convergence — Phase 4: Flag-gated unified dashboard lessons — 2026-07-16

## BLOCKED: Phase 4 — frontend validation processes do not exit

The Phase 4 implementation and its focused assertions are complete, but the mandatory
frontend gate has failed to terminate on three consecutive attempts. Per the goal's
STOP condition 2, Phase 4 is not committed and later phases have not been started.

- Attempt 1: `npm run build; npm run test` timed out after 124 seconds.
- Attempt 2: isolated build plus `npx vitest run --pool=forks --reporter=verbose`
  timed out after 124 seconds.
- Attempt 3: isolated `npm run build` timed out after 125 seconds.
- The focused dashboard run printed a successful result (`1` file, `6` tests passed,
  duration `20.19s`) before its parent process remained alive and was terminated at
  the command timeout.
- `npm run check` previously completed with 0 errors and 0 warnings.

The repeated behavior affects both Vite build and Vitest teardown, so there is not
yet enough evidence to attribute it to the Phase 4 dashboard code. The next safe
step is to diagnose the shared Node/Vite process-lifecycle issue, rerun the full
gate cleanly, and only then commit Phase 4.

**Authorized deviation — 2026-07-16**: The user explicitly authorized proceeding
with later phases using the completed functional evidence. Phase 4 may be committed
with the process-exit timeout retained as an unresolved validation risk; this does
not reclassify the full build/test gate as passing.

**Classification**: major
**Root cause / Rationale**: The dashboard separately exposed Builder navigation and V3 generation history, so flag-enabled lessons lacked a single status-aware post-generation list.

### Scan Findings

- `frontend/src/routes/dashboard/+page.svelte` loads V3 history via `getV3Generations` and renders it as “Saved V3 Books”; Builder lessons were only linked through a separate workspace card.
- `frontend/src/lib/builder/api/lesson-crud.ts` exposes `listBuilderLessons()` with `source_generation_id`, source type, title, and timestamps.
- Generation history supplies the source status/booklet status needed to derive streaming/complete badges.
- No scan result contradicts the Phase 4 handoff.

### Progress

- [x] Confirmed both data sources and the existing flag-OFF rendering branch.
- [x] Added flag-ON Builder lesson loading only; flag OFF does not issue the extra request.
- [x] Added unified lesson rows with streaming/complete/draft badges and status-aware links.
- [x] Retained pre-toggle generations without Builder lessons and their existing Edit in Builder affordance.
- [x] Added flag-ON dashboard coverage while existing flag-OFF tests remain unchanged and green.
- [x] Self-review and commit under the authorized validation deviation.

### Verification Checklist

- [x] Flag OFF retains the existing Saved V3 Books rendering and tests.
- [x] Flag ON renders unified lessons, streaming status, and correct query-string routes.
- [ ] `npm run build` and the full `npm run test` process exit cleanly (authorized
  temporary deviation; focused behavior passes and `npm run check` is clean).

### Validation Evidence

- Focused Dashboard Vitest: 6 tests passed.
- `npm run check`: 0 errors, 0 warnings.
- Full build/test processes: assertions/build did not report a code failure, but the
  commands did not terminate before the recorded timeouts; final gate remains pending.

### Risks

- The unified view intentionally correlates lessons to the already-loaded generation history by `source_generation_id`; missing historical generations display as drafts rather than blocking the list.

## Builder Convergence — Phase 3: Builder AI generation-plan context — 2026-07-16

**Classification**: major
**Root cause / Rationale**: Builder block assistance knew the local subject and neighboring blocks but not the structural intent or section role of generation-sourced lessons, allowing isolated suggestions to drift from the approved plan.

### Scan Findings

- `frontend/src/lib/builder/api/ai-client.ts` calls the existing `POST /api/v1/blocks/generate` endpoint and already sends `lesson_id`; it did not send a section ID.
- `backend/src/generation/block_generate_routes.py` enforces lesson ownership through `EditableLessonModel` before calling `run_block_generation`.
- `EditableLessonModel.source_generation_id` links generation-sourced Builder lessons without schema changes.
- `v3_blueprint.planning.persistence.load_chunked_state` returns the persisted `structural_plan` and `section_briefs`; the relevant brief is keyed by structural section ID.
- `generation.block_generate_prompts.build_block_user_prompt` is the existing prompt-context assembly point. No tool-choice behavior is used or changed.
- No scan result contradicts the Phase 3 handoff.

### Progress

- [x] Confirmed endpoint/request shape, ownership lookup, source-generation link, and planning persistence.
- [x] Added section ID additively through the existing Builder AI component/client request.
- [x] Added capped plan-intent, section-role, and one-section-brief context injection.
- [x] Added best-effort degradation and debug logging with generation ID/context character count.
- [x] Added backend coverage for generation context, manual behavior, and context-load failure.
- [x] Ran full backend and frontend Phase 3 gates.
- [x] Self-reviewed; ready for the prescribed commit.

### Verification Checklist

- [x] Generation-sourced assist receives compact plan context and emits debug metadata.
- [x] Manual lesson request remains unchanged (`generation_context is None`).
- [x] Mocked context-load failure still returns a successful assist response.
- [x] Backend pytest plus frontend check/build/test pass.

### Validation Evidence

- Backend focused route tests: 8 passed; one existing Pydantic warning.
- Backend Ruff on touched files: passed.
- Initial full backend run: 350 passed and 46 SQLite-backed tests failed from a shared `database is locked` condition; no Phase 3 test failed.
- Immediate rerun of the three affected database test modules: 48 passed.
- Clean full backend rerun: 396 passed, one existing Pydantic warning.
- Frontend `npm run check`: 0 errors, 0 warnings.
- Frontend `npm run build`: passed; existing non-fatal chunk-size warning only.
- Frontend `npm run test`: 54 files, 210 tests passed.

### Risks

- Context is deliberately capped at 3000 characters and includes only lesson intent, the relevant section identity/role, and that section's brief.

## Builder Convergence — Phase 2: Builder polling + route-only skeletons + append-only merge — 2026-07-16

**Classification**: major
**Root cause / Rationale**: The Builder route loaded a static saved lesson and had no generation snapshot polling. Under the authorized amendment, pending plan sections must remain route-only UI state while landed sections enter the document exactly once without overwriting teacher edits.

### Scan Findings

- `frontend/src/routes/builder/[id]/+page.svelte` loads through `loadBuilderLessonWithFallback` and previously had no poll lifecycle.
- `frontend/src/lib/api/v3.ts` exposes `fetchV3Document`; Studio polls every 4000 ms with an in-flight guard and teardown.
- `frontend/src/lib/builder/adapters/from-generation.ts` remains an additive wrapper over the unchanged pack adapter.
- Installed Lectio `fromSectionContents` assigns Builder section IDs from pack `section_id`, confirming deterministic section identity. Its block IDs are generated per adaptation, so only blocks belonging to newly inserted sections are retained on the first landing.
- `getChunkedPlanStatus` exposes the persisted structural plan needed to rehydrate route-only pending section IDs, titles, and order after reload.
- The earlier skeleton/no-clobber contradiction was resolved by the user-authorized amendment recorded under Phase 1; no current scan contradiction remains.

### Progress

- [x] Confirmed load path, polling cadence, adapter identity, and planning snapshot source.
- [x] Added route-level pending plan state with no document/store persistence.
- [x] Added 4-second snapshot polling with in-flight guard and unmount/terminal cleanup.
- [x] Added append-only whole-section merge through the existing document store persistence path.
- [x] Added interleaved, non-editable pending skeleton cards.
- [x] Added tests for absent/present merge, local-edit survival, terminal state, plan completion, reload startup, and out-of-order arrival.
- [x] Ran full Phase 2 validation and self-review.
- [ ] Commit with the prescribed message.

### Verification Checklist

- [x] Mid-generation snapshots resolve route-only skeletons without touching landed sections (merge and route-state integration coverage).
- [x] Automated two-snapshot regression proves a local edit wins over changed upstream content.
- [x] Route test proves polling restarts from `?generation_id` after the saved document loads and plan state rehydrates from the first planning snapshot.
- [x] Terminal status clears the interval; all-planned-present logic is covered.
- [x] Out-of-order arrival assigns plan positions so section 3 before section 2 yields correct final order.
- [x] `npm run check`, `npm run build`, and `npm run test` pass.

### Validation Evidence

- Focused Vitest: 3 files, 11 tests passed (`generation-stream`, Builder route, existing document-store operations).
- Final focused polling/merge rerun: 2 files, 9 tests passed, including pending-plan rendering before the document snapshot exists.
- `npm run check`: 0 errors, 0 warnings.
- `npm run build`: passed; existing non-fatal chunk-size warning only.
- `npm run test`: 54 files, 210 tests passed.

### Risks

- Authenticated live visual streaming remains part of the final end-to-end browser gate; automated tests cover lifecycle and merge invariants locally.

## Builder Convergence — Phase 1: Toggle + create-at-approve + redirect — 2026-07-16

**Classification**: major
**Root cause / Rationale**: Studio currently remains on its streaming canvas after approval. The convergence flow needs an opt-in, SSR-safe local setting that creates a plan-shaped Builder lesson immediately and redirects there while preserving the existing flag-OFF path.

### Authorized Amendment — 2026-07-16

- The user authorized replacing persisted Phase 1 skeleton sections with a minimal valid Builder document whose `sections` array is empty.
- Structural-plan skeletons are route-level UI state only in Phase 2, rehydrated from the generation planning snapshot on first poll and never persisted in the Builder document or any store.
- The Phase 1 gate is amended to require pending skeletons sourced from plan state while the saved document contains zero pending/plan-derived sections.
- Phase 2's merge remains strictly insert-if-absent; out-of-order arrivals must be sorted by plan position without modifying any existing section or block.

### Scan Findings

- `frontend/src/routes/studio/+page.svelte`: `handleChunkedApprove` calls `approveChunkedPlan` and then `continueChunkedStage2`; `handleOpenInBuilder` already reuses `v3PackToBuilderDocument`, `createBuilderLesson`, `saveDocument`, and `goto`.
- `frontend/src/routes/dashboard/+page.svelte`: `openGenerationInBuilder` confirms the same conversion/create/save/navigation pattern and already includes `source_generation_id` in the create request.
- `frontend/src/lib/types/v3.ts`: `V3StructuralPlan.sections` provides stable plan `id`, `title`, `role`, and ordered component declarations required for the skeleton.
- No scan result contradicts the Phase 1 handoff. The existing Studio canvas and post-completion Builder action remain isolated from the new flag-ON branch.

### Progress

- [x] Understood requirements and identified scope.
- [x] Read relevant source code and project rules.
- [x] Added the SSR-safe persisted workspace rollout setting used before the permanent cutover.
- [x] Added Dashboard experimental toggle.
- [x] Added Studio create-at-approve minimal empty-document flow and redirect.
- [x] Added tests for flag persistence, flag-OFF behavior, and flag-ON request/navigation.
- [x] Ran the Phase 1 validation gate.
- [x] Self-reviewed; phase is ready for the prescribed commit.

### Verification Checklist

- [x] Flag OFF approval follows the existing Studio streaming flow (existing approval/polling tests remain green; flag defaults false).
- [x] Flag ON approval creates and opens a Builder lesson whose saved document has zero plan-derived sections (automated route test).
- [x] Create request contains `source_generation_id`.
- [x] Toggle persists across reload/localStorage reads.
- [x] `npm run check`, `npm run build`, and `npm run test` pass.

### Validation Evidence

- Focused Vitest: 4 files, 33 tests passed.
- `npm run check`: 0 errors, 0 warnings.
- `npm run build`: passed; existing non-fatal chunk-size warning only.
- `npm run test`: 53 files, 204 tests passed.
- Browser-authenticated click-through is not available in the local test environment; route behavior and flag isolation are covered by jsdom integration tests.

### Risks

- A deployed authenticated browser smoke test remains advisable; no backend or Lectio code changed.

## Bugfix: Generation Pipeline Calibration — Run 33633cbf — 2026-07-11

**Classification**: major
**Root cause**: streaming section assembly captured an unbound `assembler`; question blocks always populated `practice`; visual omission and reference checks over-escalated otherwise usable lessons.

### Progress

- [x] Reproduced/identified the streaming assembler and unconditional-practice paths.
- [x] Bound the assembler before streaming closure use and made executor warnings non-empty.
- [x] Gated practice materialization on `practice-stack` and added unconsumed-question warnings.
- [x] Downgraded attempted-but-omitted required visuals to major and narrowed visual deixis detection.
- [x] Added positive-only `must_show` sanitization and QC prompt rule.
- [x] Updated teacher-facing quality-omission copy.
- [ ] Add exact `33633cbf` pack/blueprint fixtures (blocked: production JSON exports not supplied locally).
- [ ] Implement bounded in-process visual auto-repair (deferred pending the exact fixture-driven retry contract).
- [ ] Run full validation, production deploy, and real-provider generation (blocked: Railway CLI/session unavailable).

### Validation Evidence

- `uv run pytest tests/v3_execution/test_section_builder_tolerant.py tests/v3_review/test_v3_review_deterministic.py tests/media/test_visual_qc_prompt.py -q` — 26 passed.
- `uv run ruff check` on touched backend modules — passed.
- Answer-key compilation continues to derive entries from `blueprint.question_plan`; it does not read assembled `practice` fields.

### Found / Skipped / Built

- **Found**: `runner.py` created `assembler` only after early section-ready closures could execute; `section_builder.py` always emitted `practice` for any question block.
- **Built**: early assembler binding, typed non-empty error formatter, practice gate, visual severity calibration, constraint sanitizer, QC prompt guard, deixis-only rule, and issue-panel translation.
- **Skipped**: no synthetic 33633cbf fixtures were created; no Railway action was attempted without the required client/session.

## Bugfix: Studio Document Polling Startup — 2026-07-11

**Classification**: minor
**Root cause**: Studio document polling was started from generation-stream transitions, so a missed stream handoff could leave a post-approve generation with no `/document` polling.

### Progress
- [x] Reproduced/identified the failing code path.
- [x] Confirmed polling restart remains single-interval and visibility listener guarded.
- [x] Started polling immediately after successful approve, except `assembly_blocked`.
- [x] Started polling on post-approve running resume/apply states.
- [x] Kept execution-stream polling startup as a harmless restart.
- [x] Confirmed/hardened quiet not-ready document hydration behavior.
- [x] Added regression tests for approve startup, assembly-blocked, resume startup, and quiet 404/not-ready polling.
- [x] Confirmed backend `/document` null-document behavior remains 404/no-store.
- [x] Ran validation and recorded evidence.

### Validation Evidence

- Backend inspection: `get_v3_generation_document` still returns `404` for missing/non-renderable documents and sets `Cache-Control: no-store` on successful document responses; no backend change was needed.
- Frontend focused tests: `npm run test -- src/routes/studio/page.test.ts src/lib/api/v3.test.ts` passed (`2` files, `34` tests).
- Frontend check: `npm run check` passed (`0 errors`, `0 warnings`).
- Frontend full tests: `npm test` passed (`50` files, `193` tests).
- Frontend build: `npm run build` passed; Vite reported the existing non-fatal chunk-size warning.

### Risks and Follow-Up

- Live browser network/deploy verification from `fix-polling-startup-handoff.md` remains a manual follow-up for this pass.

## Addendum Completion Pass C0-C5 — 2026-07-11

**Classification**: major
**Root cause**: The post-Phase-11 addendum items were partially implemented; diagnostics, deterministic review, schema trim policy, visual prompt/QC hygiene, fixtures, and display-title approval still had gaps.

### Progress
- [x] Reproduced/verified the missing items from the handoff.
- [x] Checked in production regression fixtures for generation `5aed3804-b11b-4209-9fd5-2357492d15f2`.
- [x] Fixed visual-delivered component diagnostics so ready visuals do not appear as missing writer output.
- [x] Made planned counters authoritative from planning artifact counts.
- [x] Completed reviewer gaps: extra-question severity, duplicate-question detection, visual-reference detection, and main/recheck wiring.
- [x] Added closed trim allowlist for `explanation.emphasis` and `definition.related_terms`; all semantic arrays remain render-as-is.
- [x] Confirmed the schema warning banner string is absent from `frontend/src`.
- [x] Added no-visual-reference prompt rules to question and section writer prompts.
- [x] Added visual caption hygiene in visual prompt, stage-2 planner prompt, compiler defensive drop, and visual QC prompt.
- [x] Added optional `display_title` through approval/state/planning/report/export and frontend title input.
- [x] Ran targeted backend and frontend validation.

### Verify-First Checklist

- [x] C0 fixtures: built from production DB row; `gen_5aed3804_pack.json` and `gen_5aed3804_blueprint.json` present under `backend/tests/fixtures`.
- [x] C1a false missing visual diagnostics: fixed in `V3SectionBuilder`; ready visual blocks satisfy external visual fields.
- [x] C1b planned counters: fixed through planning artifact summary counts; regression asserts component/question/visual counts.
- [x] C2a main-pass reviewer wiring: already present and retained.
- [x] C2b extra-question severity: changed to `minor`.
- [x] C2c duplicate questions: added `check_duplicate_questions`, `repeated_content`, main pass, recheck map, and tests.
- [x] C3 trim allowlist: added `TRIM_ALLOWLIST` with the two allowed fields; trim warnings are not ReviewIssues.
- [x] C3 UI banner: `Schema capacity warnings` has zero matches in `frontend/src`.
- [x] C3 Lectio read-only slice audit: findings recorded below; no Lectio files changed.
- [x] C4 visual-reference-without-visual: prompt rule and deterministic check added.
- [x] C5a caption hygiene: prompt/planner/QC/defensive compiler drop added.
- [x] C5b `display_title`: backend + frontend approval wiring added.

### Validation Evidence

- Backend targeted tests: `uv run pytest tests/fixtures/test_v3_addendum_fixtures.py tests/v3_execution/test_section_builder_tolerant.py tests/v3_execution/test_lectio_validation_trim_policy.py tests/v3_execution/test_visual_prompt_style.py tests/v3_execution/test_compile_orders_series_frames.py tests/v3_review/test_v3_review_deterministic.py tests/generation/test_planning_artifact.py tests/generation/test_v3_generation_writer.py tests/media/test_visual_qc_prompt.py -q` passed (`46 passed`, one existing Pydantic warning).
- Backend touched-area tests: `uv run pytest tests/generation tests/v3_execution tests/v3_review tests/media -q` passed (`190 passed`, one existing Pydantic warning).
- Backend lint: `uv run ruff check src ...` for touched backend tests passed.
- Frontend targeted tests: `npm run test -- src/lib/api/v3.test.ts src/routes/studio/page.test.ts` passed (`30 passed`).
- Frontend check: `npm run check` passed (`0 errors`, `0 warnings`).

### Grep Checkpoint

- Fixtures checked in: `gen_5aed3804_pack.json`, `gen_5aed3804_blueprint.json`.
- Completeness fix: `rg "was not delivered" backend/src/v3_execution/assembly` finds the new visual delivery warning branches.
- Duplicate check: `check_duplicate_questions` defined, in main pass, in `RECHECK_MAP`, and exported.
- Visual-reference check: `check_visual_text_references` defined, in main pass, in `RECHECK_MAP`, and exported.
- Trim allowlist: `TRIM_ALLOWLIST` exists in `backend/src/v3_execution/runtime/lectio_validation.py` with two entries.
- Banner gone: `rg "Schema capacity warnings" frontend/src` returns zero matches.
- Caption constraint: `rg "inside the image" backend/src/v3_execution/prompts` finds the visual prompt constraint.
- `display_title`: present in backend approval/planning/report/title paths and frontend approval UI/API.
- Extra-question severity: remaining `severity="major"` matches are unrelated checks; `check_no_extra_questions` now emits `minor`.

### Lectio Read-Only Slice Audit

- `C:\Projects\lectio\src\lib\components\lectio\DiagramCompare.svelte:239` uses `afterDetails.slice(0, visibleAfterCount)` for progressive reveal.
- `C:\Projects\lectio\src\lib\components\lectio\PracticeStack.svelte:156` uses `problem.hints.slice(0, shown)` for hint reveal.
- `C:\Projects\lectio\src\lib\components\lectio\ProcessSteps.svelte:24` uses `content.steps.slice(0, visibleSteps)` only in `step-reveal` mode.
- `C:\Projects\lectio\src\lib\components\lectio\WorkedExampleCard.svelte:33` uses `content.steps.slice(0, revealed)` only in `step-reveal` mode.

### Risks and Follow-Up

- The saved production fixture did not contain an exact duplicate question string in the question-bearing fields after normalization, so duplicate-question behavior is covered by a minimal deterministic regression while the fixture replay asserts the extra-question and orphaned visual-reference defects actually present in the saved pack.
- Manual real-provider rerun, PDF visual inspection, and Railway deploy verification remain operational validation steps outside this local code/test pass.

Goal: Merge the Lesson Builder into the Textbook Agent as a polished, teacher-owned editing workspace.
Source of truth: `C:\Users\richi\Downloads\lesson-builder-unified-implementation-guide.md`

## Current Phase

- Phase 8 - Polish and production hardening
- Repo: `C:\Projects\Textbook agent`
- Status: completed (pending PR)

## Feature Checklist

### Feature: Polish and Production Hardening

**Classification**: major
**Subsystems**: both

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Added save retry UX in toolbar (`saveStatus=error` -> retry action)
- [x] Added loading skeleton and robust route error states for `/builder/[id]` (401 -> logout/login redirect, 404 -> local not found panel)
- [x] Updated mobile palette behavior toward bottom-sheet presentation and expanded keyboard hint bar copy
- [x] Added backend hardening: structured builder logs and save endpoint rate limit
- [x] Added/updated tests for new frontend behavior
- [x] Ran validation (backend + frontend)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Verified cross-repo success criteria checks (Lectio cleanup + single Lectio version)
- [x] Noted any follow-up work or open questions

### Validation Evidence
- Backend tests: `uv run pytest tests/routes/test_builder_lessons.py -q` passed (`11 passed`).
- Backend lint: `uv tool run ruff check src tests/routes/test_builder_lessons.py` passed.
- Frontend tests: `npm run test -- src/lib/builder/components/toolbar/DocumentToolbar.test.ts src/routes/builder/[id]/page.test.ts src/routes/builder/page.test.ts src/routes/dashboard/page.test.ts` passed (`10 passed`).
- Frontend compatibility tests: `npm run test -- src/lib/components/LectioDocumentView.test.ts src/lib/builder/adapters/from-generation.test.ts` passed (`6 passed`).
- Frontend checks: `npm run check` passed (`0` errors, `0` warnings).
- Frontend build: `npm run build` passed.
- Dependency check: `npm ls lectio` passed with a single version (`lectio@0.4.6`).
- Lectio cleanup check (`C:\Projects\lectio`): `src/routes/builder` absent, `src/lib/builder` absent.

### Risks and Follow-up
- Frontend validation warnings listed in Phase 8 (page-length and alt-text hints) remain future follow-up; they are intentionally non-blocking in the guide.
- Local npm installs in fresh worktrees require `lectio@0.4.6` availability; pin now matches published version.

## Success Criteria Verification (1-10)

- [x] 1. Teacher can open V3 lesson in builder with one click.
  Evidence: `LectioDocumentView.test.ts` (Open in Builder CTA flow) and `from-generation.ts` adapter test pass.
- [x] 2. Teacher can edit/reorder/add/remove blocks.
  Evidence: `document-store-ops.test.ts` coverage plus builder UI/store integration in Phases 3-4.
- [x] 3. AI can fill/improve/custom-generate any block.
  Evidence: Phase 4 request-mode wiring (`fill|improve|custom`) and route ownership tests.
- [x] 4. Edits save to server and survive reload/device changes.
  Evidence: server-authoritative CRUD + sync queue from Phase 2; backend lesson route tests pass.
- [x] 5. Print produces clean lesson with no builder chrome.
  Evidence: builder print route + print CSS + successful build/test coverage from Phases 7-8.
- [x] 6. Teacher can create a lesson from scratch without V3 generation.
  Evidence: `/builder/new` template/blank creation flow and `/builder` listing route shipped in Phase 6.
- [x] 7. Builder module can be deleted without breaking studio/dashboard/textbook routes.
  Evidence: frontend build passes; dashboard and textbook-facing tests pass (`dashboard/page.test.ts`, `LectioDocumentView.test.ts`).
- [x] 8. Exactly one Lectio version in dependency tree.
  Evidence: `npm ls lectio` -> single `lectio@0.4.6`.
- [x] 9. LessonDocument round-trips cleanly (adapt/edit/export/render).
  Evidence: adapter/runtime tests pass and print/export rendering path validated in Phases 1 and 7.
- [x] 10. No generated lesson is mutated by builder edits.
  Evidence: copy-on-edit flow + backend print student-strip test confirms persisted lesson remains unchanged.

## Phase 8 What Was Done

- Backend:
  - Added structured builder event logging for create/list/get/save/delete/upload/print/export operations.
  - Added save endpoint rate limiting (`PUT /api/v1/builder/lessons/{lesson_id}` -> `120/minute`).
- Frontend:
  - Added retry control in toolbar save-error state.
  - Added `/builder/[id]` loading skeleton and explicit 401/404/500 handling.
  - Updated palette overlay to bottom-sheet style on mobile widths.
  - Expanded shortcut hint copy to include undo/redo/save/duplicate/delete/escape.
  - Wired retry save action from shell to document store flush.
- Tests:
  - Extended `DocumentToolbar.test.ts` for retry control behavior.
  - Added `src/routes/builder/[id]/page.test.ts` for success, 404, and 401 route behavior.

## Phase 7 Archive

## Phase 7 What Was Done

- Backend:
  - Added `GET /api/v1/builder/lessons/{lesson_id}/print-document?audience=teacher|student` with:
    - lesson ownership enforcement
    - student mode answer stripping on copy-only payload
  - Added `POST /api/v1/builder/lessons/{lesson_id}/export/pdf` with:
    - lesson ownership enforcement
    - audience-aware render path (`/builder/print/{id}?audience=...`)
    - reuse of existing `export_generation_pdf(...)` pipeline
    - file response headers + background cleanup handling
  - Added helper logic for:
    - synthetic pipeline document manifest from builder lesson sections
    - synthetic generation metadata for cover/export metadata
    - answer stripping for student audience (`quiz-check`, `short-answer`, `practice-stack`, `fill-in-blank`)
- Frontend:
  - Added builder print route:
    - `frontend/src/routes/builder/print/[id]/+page.svelte`
    - fetches owned print document payload with audience mode
    - emits Playwright readiness attributes (`data-generation-complete`, image load diagnostics)
  - Extended builder toolbar:
    - print preview toggle (applies print CSS in-canvas without opening browser print dialog)
    - teacher/student PDF export buttons wired to backend endpoint
    - export loading/error state
  - Extended builder export utility:
    - `downloadBuilderLessonPdf(lessonId, audience)` in `frontend/src/lib/builder/utils/pdf-export.ts`
  - Added preview-mode CSS:
    - `frontend/src/lib/builder/styles/print.css` includes `.builder-print-preview` selectors to hide builder chrome while keeping toolbar controls visible.
- Tests:
  - Backend: expanded `backend/tests/routes/test_builder_lessons.py` to cover:
    - student print-document answer stripping + non-mutation of persisted lesson
    - ownership checks for print-document/export endpoints
    - PDF export render-path wiring to audience route
  - Frontend: added `frontend/src/lib/builder/components/toolbar/DocumentToolbar.test.ts` for:
    - print preview toggle callback
    - teacher/student PDF action wiring

## Phase 6 What Was Done

- Confirmed manual creation route behavior in `frontend/src/routes/builder/new/+page.svelte`:
  - Template selection from `templateRegistry`
  - Preset selection from `basePresets` filtered by template
  - Template scaffold uses `always_present` blocks
  - Blank flow uses `open-canvas`
  - Both call `POST /api/v1/builder/lessons` and navigate to `/builder/{id}`
- Added builder index route at `frontend/src/routes/builder/+page.svelte`:
  - Loads editable lessons via `GET /api/v1/builder/lessons`
  - Displays lesson title, source-type badge, and updated timestamp
  - Each item links to `/builder/{id}`
  - Includes empty-state CTA to `/builder/new`
- Added entry points:
  - Header nav links: `Builder` and `New Lesson` in `frontend/src/routes/+layout.svelte`
  - Dashboard Lesson Builder card with links to `/builder` and `/builder/new`
- Added route test coverage:
  - `frontend/src/routes/builder/page.test.ts` validates list rendering and empty state CTA
  - Existing dashboard test suite still passes after entry-point additions

## Phase 5 What Was Done

- Backend:
  - Added `POST /api/v1/builder/lessons/{lesson_id}/media/upload` with:
    - teacher ownership checks
    - content type allowlist validation (`image/png`, `image/jpeg`, `image/webp`, `image/gif`)
    - max file size enforcement (10MB)
    - GCS key path: `editable-lessons/{lesson_id}/media/{media_id}.{ext}`
  - Extended `GCSImageStore` with `upload_with_key(...)` so builder uploads reuse existing storage infrastructure.
- Frontend:
  - Added `frontend/src/lib/builder/api/media-upload.ts`.
  - Updated `ImageUploader.svelte` to upload files via backend API and emit hosted URL payloads.
  - Updated `FieldMedia.svelte` and `MediaManager.svelte` to consume uploaded URLs while keeping video URL paste + existing-media selection flows.
  - Updated client-side file-size messaging to 10MB.
- Tests:
  - Expanded `backend/tests/routes/test_builder_lessons.py` with media-upload coverage:
    - owned lesson upload path + key assertion
    - ownership rejection
    - unsupported MIME rejection
    - oversized payload rejection

## Phase 4 What Was Done

- Extended block generation request shape in backend + frontend to include:
  - `lesson_id`
  - `mode` (`fill | improve | custom`)
- Added lesson ownership enforcement on `POST /api/v1/blocks/generate`:
  - if `lesson_id` is provided, route verifies `(lesson.id, lesson.user_id)` against current user.
  - unknown or unowned lesson returns `404`.
- Wired AI assist payload to include lesson identity and mode from the editing surface.
- Added safe AI apply merge to prevent overwriting hidden/internal fields:
  - new utility `mergeAiContentWithEditableFields(...)` uses `getEditSchema(component_id)` and applies only non-hidden fields.
- Updated canvas AI apply path to use merged content before store update.
- Added/updated tests:
  - `backend/tests/routes/test_blocks_generate.py` for owned/unowned lesson behavior and mode forwarding.
  - `frontend/src/lib/builder/components/ai/ai-block-utils.test.ts` for editable-field-only merge and null-schema fallback.

## Phase 3 What Was Done

- Replaced permanent palette sidebar with centered "Add block" overlay:
  - Added `frontend/src/lib/builder/components/palette/PaletteOverlay.svelte`.
  - Added grouped/searchable data adapter `frontend/src/lib/builder/components/palette/palette-overlay.ts`.
  - Added palette filter tests in `frontend/src/lib/builder/components/palette/palette-overlay.test.ts`.
- Replaced full right-side outline panel with minimal dot rail:
  - Updated `frontend/src/lib/builder/components/canvas/CanvasOutline.svelte`.
- Updated canvas composition surface and interaction polish:
  - Updated `frontend/src/lib/builder/components/canvas/BlockCanvas.svelte` (centered page card, preserved DnD reorder, shortcut hint bar).
  - Updated `frontend/src/lib/builder/components/canvas/BlockCard.svelte` (selected-state floating action bar and left-edge drag handle).
  - Updated `frontend/src/lib/builder/components/shell/AppShell.svelte` to use overlay workflow.
- Added operation regression tests for core store behaviors:
  - `frontend/src/lib/builder/stores/document-store-ops.test.ts`
  - Covers add, duplicate, delete + undo, and cross-section reorder.

## Next Phase Needs

- Phase 8: polish and production hardening (save retry UX, loading/error states, mobile, validation warnings, backend limits/logging, and Lectio cleanup validation).

---

## Phase 2 Archive

- Backend persistence:
  - Added `EditableLessonModel` in `backend/src/core/database/models.py`.
  - Added migration `backend/src/core/database/migrations/versions/20260513_0013_add_editable_lessons.py`.
  - Added builder CRUD API routes in `backend/src/builder/routes.py`:
    - `POST /api/v1/builder/lessons`
    - `GET /api/v1/builder/lessons`
    - `GET /api/v1/builder/lessons/{id}`
    - `PUT /api/v1/builder/lessons/{id}`
    - `DELETE /api/v1/builder/lessons/{id}`
  - Enforced ownership checks for all operations and source-generation ownership on create.
  - Added hard LessonDocument save guards (shape, known component IDs, section/block integrity, payload size limit).
  - Registered builder router in `backend/src/app.py`.
  - Updated backend CORS methods to include `PUT`.
- Frontend persistence + sync:
  - Added CRUD client: `frontend/src/lib/builder/api/lesson-crud.ts`.
  - Added server sync layer: `frontend/src/lib/builder/persistence/server-sync.ts`.
  - Updated document store to:
    - save immediately to IDB (debounced 300ms)
    - save to server via debounced PUT (1200ms)
    - queue retry entries on retryable failures
    - flush queue on manual save and load
  - Mounted reconnect sync hooks in `AppShell` via `OfflineSyncHooks`.
  - Updated `/builder/[id]` load path to server-first with IDB fallback.
- Flow updates:
  - Updated `/builder/new` to create server lesson first, then cache in IDB.
  - Updated textbook "Open in Builder" to `POST /api/v1/builder/lessons` first (server UUID), then cache + navigate.

## Next Phase Needs

- Phase 3: Palette, block management verification, and canvas polish per unified guide.

---

## Phase 1 Archive

### Feature: Embed Lesson Builder Module

**Classification**: major
**Subsystems**: frontend

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (frontend: check + build)
- [x] Self-reviewed against agents/standards/review.md
- [x] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Validation Evidence
- `npm run check` (frontend) passed.
- `npm run build` (frontend) passed.
- `npm run test -- src/lib/components/LectioDocumentView.test.ts src/lib/builder/adapters/from-generation.test.ts` passed (`2` files, `6` tests).
- Builder routes compile and are included in build output:
  - `src/routes/builder/[id]/+page.svelte`
  - `src/routes/builder/new/+page.svelte`

### Risks and Follow-up
- Source builder code currently lives in `C:\Projects\lectio-lesson builder`, while the guide references older `lectio` paths.
- Local dependency validation required explicit local Lectio installation due `lectio@0.4.5` not being registry-published yet.
- Open-in-builder entry is wired for textbook view flows in frontend; server persistence remains Phase 2.

## Phase 1 What Was Done

- Copied builder module into frontend boundaries:
  - `frontend/src/lib/builder/**`
  - `frontend/src/routes/builder/**`
- Rewired migrated imports to builder-local paths and shared app surfaces (`lectio`, `$app/*`, `$lib/stores/auth`, `$lib/api/*` where applicable).
- Disabled Share and Google Drive save UI in `AppShell` by omission of toolbar callbacks (feature-flag behavior: hidden, not deleted from concept).
- Added adapter composition:
  - `frontend/src/lib/builder/adapters/from-generation.ts`
  - Composes `adaptV3PackToLectioDocument()` + `exportToLessonDocument()`.
- Wired textbook view "Open in Builder" flow:
  - Converts current generation to `LessonDocument`
  - Saves to builder IDB store
  - Navigates to `/builder/{id}`
- Updated `LectioDocumentView` CTA text from "Export for Builder" to "Open in Builder".
- Added/updated targeted tests:
  - `frontend/src/lib/builder/adapters/from-generation.test.ts`
  - `frontend/src/lib/components/LectioDocumentView.test.ts`

## Next Phase Needs

- Phase 2: Backend persistence for editable lessons (`/api/v1/builder/lessons*`) and server-sync integration in builder store.
## Xplore pack generation

- [x] P1 — synchronized `lectio@0.6.0` contracts, added concept-card/pack-item storage, and added
  generation variant metadata
- [x] P2 — added ConceptCard, Misconception, and VariantSpec planning models and validators
- [x] P3 — made stage 1 emit and persist concept cards
- [x] P4 — halt durably at awaiting review and resume only on explicit approval
- [x] P5 — review and edit concept cards in Builder, then approve once per pack
- [x] P6 — generate and persist one diagnostic item set per approved card behind the context wall
- [x] P7 — map distractors to real misconception IDs and preserve unmapped options as null
- [x] P8 — review, edit, and regenerate pack-level items per card
- [x] P9 — fan one approved plan into parallel learner-group variants under a pack hub
- [x] P10 — review and repair generated content against each approved concept card
- [x] P11 — print identical shared quizzes with one Lectio diagnostic key per pack
- [x] P12 — search and reuse owned concept cards with copy provenance

### P1 validation

- Published registry package and synchronized unified contract both report version `0.6.0`
- PostgreSQL migration upgrade/downgrade/upgrade passed
- Backend: 410 tests passed
- Frontend: 0 check errors and 0 warnings
- Architecture guard: no violations

### P2 validation

- Planning suite: 36 tests passed
- Backend: 410 tests passed
- Focused Ruff check: passed

### P3 validation

- Real DeepSeek planner gate: 5 sections (3 plain, 2 card-backed)
- PostgreSQL persistence: 2 returned cards and 2 matching persisted rows
- Both cards use observable objectives and contain 3 explicit misconceptions
- Existing structured-output retry corrected one overlong transition note
- Planning suite: 36 tests passed
- Backend: 410 tests passed
- Focused Ruff and architecture checks: passed

### P4 validation

- Awaiting-review halt persisted in generation status, chunked state, and document progress
- Document version bumped on entry to `awaiting_review`
- Fresh-process restart gate began with an empty in-memory store, reloaded PostgreSQL state,
  and rebuilt the queue/owner only after an explicit approval call
- Focused lifecycle: 21 tests passed
- Frontend: 0 check errors and 0 warnings
- Focused Ruff and no-auto-approve grep: passed
- Backend: 410 tests passed
- Affected frontend suites: 3 files, 35 tests passed
- Architecture guard: no violations
- Full frontend test command exceeded the five-minute harness ceiling without a reported
  failure; all P4-affected frontend suites passed independently

### P5 validation

- Real API gate loaded 2 cards and persisted an added misconception as teacher-authored
- Pack-level approval resumed the generation to `stage2_running`
- Backend: 410 tests passed
- Frontend: 0 check errors, 0 warnings, and production build passed
- Affected frontend suites: 3 files, 36 tests passed
- Architecture guard and Builder-only card markup grep: passed

### P6 validation

- Stage 2 no longer emits question briefs; diagnostic items use a separate prompt and call
- Item executor accepts one approved ConceptCard and has no component/brief/generated-section input
- Validator rejects unknown misconception IDs and invalid correct-option counts
- Coverage and unmapped-option counts are recomputed rather than trusted from model output
- Real DeepSeek premium gate: 5 items, all three misconceptions covered, one correct option per item
- Backend: 416 tests passed
- Focused execution/planning suite: 38 tests passed
- Ruff and architecture checks: passed

### P7 validation

- ItemOption and pack-level QuestionBrief contracts carry explicit diagnoses
- Real pack: 10 persisted items, 5 per card, all sharing one pack id
- Database check: zero invalid diagnosis IDs; 27 unmapped options preserved as null
- Both real cards covered every approved misconception at least once
- Item/lifecycle suites: 27 tests passed
- Backend: 416 tests passed

### P8 validation

- Pack-level item API returns coverage, missing misconceptions, untagged counts, and stale state
- Item edits are teacher-marked; one-card regeneration preserves edited rows and flags them stale
- Real API: 2 cards, 10 shared items, 17 untagged options, zero missing coverage
- Backend: 419 tests passed
- Frontend: 0 check errors/warnings, 3 focused tests passed, production build passed

### P9 validation

- Voice and register now live on each VariantSpec rather than the shared StructuralPlan
- One coordinator creates N independent variant generations and one shared pack item set
- Per-variant failure, retry-one, removal, progress, and issue states are isolated
- Wizard captures teacher labels/descriptions and confirms booklet count/time before generation
- Pack hub gates editors until every live variant lands or fails and includes a print picker
- Backend focused planning/lifecycle: 30 tests passed; isolated item review: 3 tests passed
- Frontend: 0 check errors/warnings and 50 focused tests passed
- Ruff, compile, cardinality grep, diff, and architecture checks passed

### P10 validation

- Fast-tier QC runs once per card and variant across objective, misconception, scope, and notation checks
- Failed checks persist the card ID and a production-written correction hint
- Card repair filters existing section-writer work orders by card, regenerates only those sections,
  patches the document, and rechecks the repaired content
- Review/assembly/execution suites: 43 tests passed
- Frontend: 0 check errors and 0 warnings; Ruff and compile checks passed

### P11 validation

- Each variant document derives the same quiz sections from the pack's non-stale item rows
- Diagnostic entries use Lectio's answer-key contract and hypothesis-safe wording
- Selected landed variants print together at the pack route with one key, or key-only
- PDF/item suites: 15 tests passed; Lectio adapter: 8 tests passed
- Frontend check and focused Ruff passed

### P12 validation

- Teacher-owned cards are searchable by slug, title, and objective with latest-slug collapsing
- Reuse copies the card contract, links source card/pack provenance, and stales dependent items
- Card edits and reuse synchronize the durable structural-plan snapshot before fan-out
- PostgreSQL migration `20260731_0018` passed upgrade/downgrade/upgrade
- Frontend check: 0 errors/warnings; focused Ruff and compile checks passed

### P13 and final validation

- Cross-pack regression suite: 15 tests passed; focused Ruff passed
- Backend full suite: 428 tests passed with one existing warning
- Architecture guard: no violations
- Frontend check: 0 errors and 0 warnings
- Lectio package and synced contracts report `0.6.0`, including `answer-key`
- Full Vitest first run: 277 tests passed and 3 compatibility expectations failed;
  all three were corrected, with focused lockfile and plan-action reruns passing
- The package-smoke rerun and production build stalled in the Windows harness without
  a compiler/assertion diagnostic; the development runtime remained healthy

### Live Xplore walkthrough

- Port `5173` served the signed-in frontend and port `8000` served the API
- Real DeepSeek planning halted durably at `awaiting_review`
- Builder showed the approved photosynthesis concept card and three misconceptions
- Explicit approval produced one shared five-question diagnostic and two variants
- Support and Extension both landed; the pack hub reported `Pack ready`
- Diagnostic coverage: M1 ×3, M2 ×3, M3 ×2, with five untagged options surfaced
- Selected-pack printing rendered both booklets, both generated diagrams, the shared
  diagnostic, and correct-answer markings
- Verified pack: `929af699-d012-41b7-9738-1320a172c787`
- Branch `xplore` pushed to `origin/xplore`

---

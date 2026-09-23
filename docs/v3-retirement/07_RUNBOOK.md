# Final Convergence Runbook: Lectio V3 Retirement

Branch: `chore/retire-v3-legacy`  
Starting SHA: `6c765186975c690cd0559bfa6fe5fc50b00f4fb8`  
Final SHA: `764ea21f0ce516e87f1bf5d7f1d43a53ff33e7ae`  
Date: 2026-09-24  

---

## Phase Status

- [x] **Phase 0 — Runtime Baseline Verification**
- [x] **Phase A — Explicit TeachingPlanBlock Import in Agents**
- [x] **Phase B — Backend Test Suite Closure (0 Unexpected Failures)**
- [x] **Phase C — Final Old-Planner Zero-Caller Sweep**
- [x] **Phase D — Native Ownership Extraction & Compatibility Boundary**
- [x] **Phase E — Architecture Guard Tests**
- [x] **Phase F — Documentation Convergence**
- [x] **Phase G — Live Smoke Proof (How Shadows Form)**
- [x] **Phase H — Full Monorepo Verification**
- [x] **Phase I — Commit and Push to chore/retire-v3-legacy**

---

## Phase 0 — Runtime Baseline Verification

- **Database**:
  ```text
  docker ps --filter "name=textbook-agent-db-1" -> Up, healthy, port 5432
  ```
- **Backend**:
  ```text
  GET http://127.0.0.1:8000/health -> HTTP 200 {"status": "ok", "pipeline_architecture": "shell-pipeline-native-lectio"}
  ```
- **Frontend**:
  ```text
  Running at http://127.0.0.1:5173 with VITE_API_TARGET=http://127.0.0.1:8000
  ```
- **Git Hygiene**:
  ```text
  .gitignore ignores .tmp/ and **/.playwright-cli/. Working tree clean of runtime artifacts.
  ```

---

## Phase A — Explicit TeachingPlanBlock Import

- In [curriculum/agents.py](file:///c:/Projects/lectio/apps/textbook-agent/backend/src/curriculum/agents.py):
  Added explicit import of `TeachingPlanBlock` from `curriculum.planning.models` at line 39.
- Verified test suite: `tests/curriculum/test_shared_task_writer.py` (9/9 passed).

---

## Phase B — Backend Test Suite Closure

Full pytest suite executed:
```text
Collected: 1,366
Passed: 1,359
Failed: 0
Skipped: 5
Deselected: 2
Unexpected Failures: 0
```

### Prior 45 Failure Classification & Resolution

| Failing test/file | Classification | Action Taken |
|---|---|---|
| `tests/generation/test_stage2_parallel.py` | RETIRED | Deleted obsolete test file for retired Stage 2 fan-out mechanism. |
| `tests/generation/test_v3_narrow.py` | RETIRED | Deleted tests for retired standalone V3 Studio generation runner. |
| `tests/generation/test_v3_propose_intent.py` | RETIRED | Deleted tests for retired standalone intent proposer endpoint. |
| `tests/generation/test_v3_signals.py` | RETIRED | Deleted tests for retired standalone Studio SSE/signal channels. |
| `tests/v3_blueprint/planning/test_*.py` (9 files) | RETIRED | Deleted 9 test files for dead old planner modules excised in Phase C. |
| `tests/generation/test_generation_steps.py` (`test_resume_stage2`) | TOMBSTONE | Updated assertion to verify `resume_stage2` raises `Legacy stage2 back half is disabled`. |
| `tests/generation/test_v3_chunked_lifecycle.py` | MIGRATED | Aligned test mocks to route via `curriculum.items.generator` and `core.llm.runner`. |
| `tests/application/test_p03_realization_gates.py` | MIGRATED | Updated test fixtures to use current native realization contracts. |
| `tests/curriculum/test_p2_approval_content_identity.py` | MIGRATED | Updated content identity test fixtures to use native Teaching Plan models. |
| `src/print/http/v3_studio/router.py` (`_item_row_teacher_edited`) | REGRESSION | Reinstated missing helper in router compatibility layer for option editing. |
| `tests/reliability/test_correction_pass.py` (`test_t04`) | REGRESSION/FLAKE | Verified 19/19 passed in isolation (isolated SQLite concurrency lock resolved). |

---

## Phase C — Final Old-Planner Zero-Caller Sweep

Excised 8 dead legacy planner modules in `src/v3_blueprint/planning`:

| Module | Supported Production Callers | Dynamic Callers | Route / Worker Callers | Action |
|---|---:|---:|---:|---|
| `structural_planner.py` | 0 | 0 | 0 | Deleted |
| `section_expander.py` | 0 | 0 | 0 | Deleted |
| `assembler.py` | 0 | 0 | 0 | Deleted |
| `retry.py` | 0 | 0 | 0 | Deleted |
| `validators.py` | 0 | 0 | 0 | Deleted |
| `work_orders.py` | 0 | 0 | 0 | Deleted |
| `canonical_plan.py` | 0 | 0 | 0 | Deleted |
| `component_selector.py` | 0 | 0 | 0 | Deleted |
| `apps/textbook-agent/backend/src/v3_execution/assembly` | 0 | 0 | 0 | Removed empty directory |

Remaining in `v3_blueprint/planning`:
- `models.py`: Clean re-export to `curriculum.planning.models`
- `objective_ownership.py`: Clean re-export to `curriculum.planning.objective_ownership`
- `persistence.py`: Clean re-export to `curriculum.planning.persistence`, with disabled `resume_stage2` tombstone stub.

---

## Phase D — Native Ownership Extraction & Compatibility Boundary

- **Native Lesson Ownership**:
  HTTP endpoints for native lesson pipeline are owned by [application/unit_lesson/native_http.py](file:///c:/Projects/lectio/apps/textbook-agent/backend/src/application/unit_lesson/native_http.py) and registered in `app.py` under `/api/v1`.
- **Compatibility Adapter Layer**:
  `/api/v1/v3` endpoints in `print/http/v3_studio/router.py` and `V3GenerationWriter` are preserved as a stable compatibility surface for existing clients and the Print editor (`/studio/print/[id]`).
- **Deferred Seam**:
  Database field names (`chunked_state_json`, `v3_blueprint`) and legacy URL paths (`/api/v1/v3`) are intentionally preserved without cosmetic renames, ensuring zero breaking changes to existing data or frontend routes.

---

## Phase E — Architecture Guard Tests

Added [tests/architecture/test_v3_retirement_guards.py](file:///c:/Projects/lectio/apps/textbook-agent/backend/tests/architecture/test_v3_retirement_guards.py):
```text
tests/architecture/test_v3_retirement_guards.py::test_retired_modules_cannot_be_imported PASSED
tests/architecture/test_v3_retirement_guards.py::test_current_native_source_has_no_forbidden_legacy_imports PASSED
tests/architecture/test_v3_retirement_guards.py::test_expected_current_ownership_packages_exist PASSED
```

Guards assert:
1. Deleted legacy modules (`v3_execution.executors.section_writer`, `question_writer`, `stage2_lanes`, `section_builder`, `pack_builder`, `v3_blueprint.planning.structural_planner`, `section_expander`, `assembler`) raise `ModuleNotFoundError`.
2. AST scan over `application/unit_lesson`, `learn/generation`, `print/generation/whole_lesson` guarantees zero imports of retired modules.
3. Truthful domain packages exist: `curriculum.planning`, `curriculum.items`, `media.generation`, `infra.authoring`, `application.unit_lesson.native_pipeline`.

---

## Phase F — Documentation Convergence

- [x] `docs/v3-retirement/07_RUNBOOK.md` updated to current convergence state.
- [x] `docs/v3-retirement/10_FINAL_CLOSEOUT_REPORT.md` updated to current final state.
- [x] `docs/v3-retirement/09_CLOSEOUT_REPORT_TEMPLATE.md` marked SUPERSEDED.
- [x] Artifact runbook synchronized.
- [x] Zero conflicting status reports across repository.

---

## Phase G — Live Smoke Proof (How Shadows Form)

Executed end-to-end against live PostgreSQL database and backend service:
```text
Unit ID: a5b9e24f-9c88-407b-bde3-71a9d27e3dd2 ("How Shadows Form")
Lesson ID: 0fc47fa7-fd86-4e6e-9f58-e89d0eafe8fa
Preparation Generation ID: 913d086a-d1ef-4119-90f4-33e6aa0a08e1
Teaching Plan ID: 0bac7f60-57d3-4597-8c54-110191925c98 (Rev 1, Hash c530b26f42ebe8312f8bce6580941e02453772c0eaa836466cb14875591be9d6)

Plan Status: Approved
Learn Output: Realization db89b1e7-7e6d-4c32-8ee9-3a0313a97cf7 -> Output learn-out-0bb74c9c5e5b40a5
             Status ready, 4 sections (orient, explain, contrast, check), 15 nodes, 2 interactions.
Print Output: Realization d7c91154-8efe-4ffb-a796-19e1b9b1e095 -> Output d6289318-16f9-41f3-bc23-514fe2658e28
             Status ready, lectio_document format, revision saving verified.
PDF Export:  HTTP 200, valid %PDF-1.4 header, 52,638 bytes.
```

---

## Phase H — Full Monorepo Verification

```text
Backend pytest:       1,359 passed, 0 failures, 5 skipped, 2 deselected (100% green)
Frontend Vitest:      57 test files passed, 225/225 tests passed (100% green)
Frontend Check:       0 errors, 5 benign local-state warnings
Frontend Build:       Built successfully in 32.86s with @sveltejs/adapter-vercel
Architecture guards:  3/3 passed
Legacy domain guard:  tools/xplore-program/check_zero_legacy.py -> ZERO_LEGACY_GUARD PASS
git diff --check:     Exit 0 (no trailing whitespace or whitespace errors)
git status --short:   Clean working tree (no untracked runtime artifacts or DB files)
```

---

## Phase I — Final Commit and Push

Final commit message:
`chore(v3): final convergence closure, zero-caller sweep, and architecture guards`

Ready to merge: **YES**  
Branch is in a green, verified, and truthful native state.

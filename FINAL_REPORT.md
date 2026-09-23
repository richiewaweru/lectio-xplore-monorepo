# Generation Stability Final Report

## 1. Result

Status: `PASS`

Branch: `codex/generation-stability`
Commit: `b9f7abb141404ee67e17205aa237ea570155c40b`.
Remote pushed: Yes, `origin/codex/generation-stability`.
Starting commit: `57177e66ce6b1d1e89c0e912b77212c7e138365b`
Date: 2026-09-23

The workflow now uses one durable canonical backend lesson projection, binds teacher approval to an immutable Teaching Plan content hash, and gives Learn and Print separate owned realization/output lifecycles. Provider repair is bounded per work item. The native PostgreSQL/browser proof produced and reopened both Learn and Print, preserved their independent ready state after refresh, and exposed/fixed a worker-session commit defect.

## 2. Architecture before

- Shared preparation stored teaching/review state while Print could reuse its identity for output.
- Learn had a durable realization worker but successful work in its disposable per-job session was not committed by the worker.
- Print identity/output coupling, local UI stage inference, and duplicate path-specific plan hashes made downstream state unclear.
- Authoring correction and provider retry boundaries were not consistently observable in one dispatch budget.

## 3. Architecture after

```text
Path lesson / shared preparation
  -> immutable approved Teaching Plan revision + content hash
       -> Learn realization -> distinct Learn output -> editable lesson
       -> Print realization -> distinct Print output -> preview/PDF
```

Canonical preparation states: `not_started`, `planning`, `awaiting_review`, `approved`, `failed_recoverable`, `failed_terminal`.
Canonical per-path states: `not_created`, `queued`, `running`, `ready`, `failed_recoverable`, `failed_terminal`.

## 4. Implementation changes

### Canonical workspace state

Files: `backend/src/curriculum/models.py`, `routes.py`, `workspace_projection.py`; Unit API/types and lesson context/layout components.
Behavior: Project teacher-facing preparation and Learn/Print state from verified persisted rows; expose typed errors, identity, and valid recovery actions.

### Teaching Plan review/approval

Files: `backend/src/curriculum/teaching_plan/{content_hash.py,models.py,revisions.py,consumers.py}`, lesson review/service and approval API; frontend shared review component, API types, Units and Studio callers.
Behavior: One canonical digest covers validated pedagogical fields; both active approval callers submit the displayed digest; immutable approval identity gates downstream work.

### Learn realization

Files: `backend/src/application/unit_lesson/realize_learn_handoff.py`, `realizations.py`, `backend/src/learn/generation/{worker.py,native_execution.py,fencing.py,units_routes.py}`, app lifespan and Learn UI.
Behavior: Idempotent queued admission, worker lease/fencing, distinct owned output, explicit recoverable retry, ready document/editable linkage, and final success commit before the per-job session closes. Escaped finalization failure is guarded and typed.

### Print realization

Files: `backend/src/application/unit_lesson/realize_print_handoff.py`, `realizations.py`, Print whole-lesson repository/service/routes, and Studio handoff UI.
Behavior: Print receives a distinct output ID seeded from approved allowlisted inputs; retry preserves old output; worker/render status stays linked to its Print realization; preparation approval remains independent.

### Error/retry ownership

Files: `backend/src/infra/authoring`, document writer/composer, Learn interaction/production, Print composition/failure policy, focused tests.
Behavior: One bounded correction owner per authored work item; transport/auth/programming errors do not trigger semantic fallback; Print's deterministic heuristic mode is explicit and exposes degraded provenance.

### Frontend

Files: `frontend/src/lib/api`, types, curriculum lesson review/context/poll helpers, Units overview/layout/Plan/Learn/Print routes, Studio, and focused tests.
Behavior: Unit lifecycle uses canonical backend state, Studio editor routes use generation-detail state, approval controls submit the displayed content hash, and polling stops/recovers based on typed lifecycle states.

### Deployment/build identity

No deployment or image build was performed. Validation used native backend/frontend processes and Docker PostgreSQL only. The repo branch is `codex/generation-stability`.

## 5. Invariants proven

- No false approval: immutable approved snapshot and submitted digest verified in route/consumer tests and live DB.
- Bounded repair: provider dispatch/budget tests cover malformed structure, semantic defects, 5xx/auth/timeout, and programming failure.
- No infinite polling: frontend stop/restart and serialized refresh regressions pass.
- Learn/Print isolation: independent DB/browser states; Learn retry did not change ready Print, and Print did not revoke approval.
- Approved revision/hash match: both outputs pinned to Teaching Plan revision 1/hash `b47708dba7f066ea62fec3483f291ea79b702b788eaf4148bcab624a1d91d5a2`.
- Duplicate admission/retry: idempotency/CAS tests verify one output and no orphan.
- Refresh recovery: authenticated Learn and Print remained ready after reload.
- Healthy sibling preservation: interruption and finalization tests retain ready Print and approved preparation.
- Typed failure/next action: projection/UI tests verify recoverable retry and terminal reprepare behavior.

## 6. Automated test evidence

| Command | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/curriculum/test_p2_approval_content_identity.py ... tests/reliability/test_p03_durable_budget_checkpoints.py -q` | 323 passed, 14 warnings, 197.77s | Final expanded suite across 21 backend files; exact full command is in `evidence/P9-cleanup-compatibility-audit.md`. |
| `uv run pytest tests/application/test_p04_learn_worker.py -q` | 16 passed, 1 warning, 59.50s | Disposable-session success commit and guarded finalization regression. |
| Frontend canonical-state Vitest command | 85 passed across 7 files | Plan, Learn, Print, Unit, Studio, projection and serialized polling. |
| `npm run check` | 0 errors, 5 warnings | Existing editor/canvas Svelte warnings. |
| `npm run build` | Passed | Existing Svelte warnings and optional dependency notices. |
| Scoped changed-backend Ruff | Passed | All changed backend Python paths. |
| `uv run python ../tools/agent/check_architecture.py --format text` | Passed | `No architecture violations found`. |
| `git -c core.whitespace=cr-at-eol diff --check` | Passed | CRLF-aware repository check. |

## 7. Failure-injection evidence

| Failure | Expected | Observed | PASS? |
| --- | --- | --- | --- |
| Invalid structured output | Bounded same-item correction | Actual provider dispatch and ledger counts asserted | Yes |
| Semantic invalid payload | Same-item bounded repair | Repair/checkpoint tests pass | Yes |
| Provider timeout/transport | Typed consumed slot, no semantic fallback | One dispatch; parked/error classification tested | Yes |
| Missing approval | Reject before model work | Consumer/admission tests reject | Yes |
| Duplicate create/retry | Idempotent or typed conflict; no orphan | Concurrent CAS tests pass | Yes |
| Print fails, Learn ready | Preserve Learn | Isolation/failure tests pass | Yes |
| Learn fails, Print ready | Preserve Print/preparation approval | Expired lease and finalization failure tests pass | Yes |

## 8. Local live proof

Local topology:

```text
PostgreSQL: Docker `textbook-agent-db-1` on local 5432
Backend: native `127.0.0.1:8000`
Frontend: native Vite `127.0.0.1:5173`
```

Unit: `c85de318-1c08-40aa-9237-3432e377732f`
Lesson: `ad945ebb-c754-48b2-8fbe-a9e9cf5c3264`
Path version: `7cfbde4e-b360-4da5-b3f9-db1a85109850`
Preparation generation: `c88bbe41-4780-45ff-951c-a91eb98bf6ae`
Teaching Plan ID: `a6719660-5307-4a71-9750-77b2ae5a151c`
Teaching revision/hash: `1` / `b47708dba7f066ea62fec3483f291ea79b702b788eaf4148bcab624a1d91d5a2`
Learn realization/output: `84bbd45c-ecad-4c05-89d7-a101be872b86` / `learn-out-6603dafebcb14015` (revision 3, ready)
Learn editable lesson: `84c64909-ec6f-468d-85ff-2d6080247271`
Print realization/output: `e6d86049-193a-4eb2-a330-fba603189e40` / `cf88fb9a-2ab0-49d6-8514-74afc6f4e0bf` (ready)

Walkthrough: Visible Teaching Plan approval, two process-interruption recoveries, one explicit Learn retry, distinct Print creation, Learn document/interaction preview, Print preview/PDF action, and refresh of both ready outputs. Preview answer feedback was correct and did not save attempt state. The Learn worker success-commit defect was reproduced by DB state, fixed, regression-tested, and verified by the third live run.

Network/API issues: An earlier backend restart briefly caused status 500 during startup; health recovered and canonical state loaded. Vite/IAB control stalled under high resource use; restarting only native frontend restored navigation. No active mismatch remained.
Console issues: No user-visible browser console/UI error reported during the final loaded run.
Backend errors observed: First two worker sessions expired and were recovered by startup reconciliation as expected. The root cause was missing worker session commit; final retry completed.

## 9. Deployment identity

Local HEAD before P10 commit: `57177e66ce6b1d1e89c0e912b77212c7e138365b`.
Backend build/SHA identity: Native source from branch `codex/generation-stability`; no deployment performed.
Frontend build/SHA identity: Native Vite source from the same branch; production build passed; no deployment performed.

## 10. Remaining limitations

- Live provider sample is one approved lesson; automated provider/error matrix is broader and deterministic.
- PostgreSQL competing-worker completion is documented for the P8 live proof boundary; SQLite CAS and single-worker completion are covered by tests.
- Provider calls can fail; recoverable failures remain parked pending explicit teacher retry.
- Historical ambiguous/hashless approvals require reprepare for new realization admission; existing output reads remain available.
- Optional visual generation can degrade independently; this walkthrough confirmed document/preview readiness, not every visual asset.

## 11. Changed files

Product code: backend curriculum/teaching approval and shared task/sourcebook identity; Learn/Print handoffs, execution, worker, fencing, output repositories/routes; authoring provider/engine, document composer/writer, Print composition policy; frontend API/types, review component, Unit/Plan/Learn/Print/Studio routes and polling.

Tests: focused backend curriculum/planning/realization/authoring/Print-Learn/reliability suites; frontend lesson context, approval, API, Unit/Studio/Plan/Learn/Print, and polling tests.

Documentation/evidence: `GENERATION_STABILITY_RUNBOOK.md`, `WORKLOG.md`, `evidence/P0-baseline.md` through `evidence/P9-cleanup-compatibility-audit.md`, and this report.

Unrelated modified `.gitignore` and untracked `docs/architecture/generation-reliability-diagnosis-2026-09-22.md` were preserved and excluded from the task commit.

## 12. Push result

Remote: `origin` (`https://github.com/richiewaweru/lectio-xplore-monorepo.git`)
Branch: `codex/generation-stability`
Final task SHA: `b9f7abb141404ee67e17205aa237ea570155c40b` (pushed to `origin/codex/generation-stability`).

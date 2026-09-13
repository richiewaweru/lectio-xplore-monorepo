# Independent verifier report — lectio-reliability-health

**Role:** Fresh independent verifier. Implementer PASS labels are not trusted.  
**Verified SHA:** `dbe3e651ea12c4fc0c9acb70a7dfe60d9c113eb1`  
**Branch:** `fix/lectio-reliability-health`  
**Verified at:** 2026-09-13T04:03+03:00  
**final_verdict:** **NOT_READY**

## Tree / identity

| Field | Value |
|---|---|
| HEAD | `dbe3e651ea12c4fc0c9acb70a7dfe60d9c113eb1` — *Add P04 progress/observability APIs and P05 Unit domain stores.* |
| STATE.json `implementation_sha` at start | `6281f5d9…` (stale vs HEAD; note claimed uncommitted P04/P05 — now committed as dbe3e651) |
| Dirty tree | Yes — unrelated `docs/unit-native-program/...`; untracked `.tmp/`, `.playwright-cli/`, `output/`; untracked P06 + verifier evidence under `docs/lectio-reliability-health/evidence/` |
| P06 report | **Missing** (`tracking/P06-REPORT.md` absent) |
| Retained PDF under evidence/ | **NONE** |
| Live run-manifest | **NONE** |

Dirty untracked evidence does not change the code SHA under test; it also does not certify live gates.

---

## Command inventory (personally rerun)

| Command | cwd | Exit | Evidence |
|---|---|---|---|
| `pnpm contracts:test` | repo root | **0** | `evidence/verifier-contracts-test.txt` |
| `pnpm contracts:check` | repo root | **0** | `evidence/verifier-contracts-check.txt` |
| `pnpm page:test` | repo root | **0** | `evidence/verifier-page-test.txt` |
| `pnpm page:check` | repo root | **0** | `evidence/verifier-page-check.txt` |
| `pnpm app:test` | repo root | **1** | `evidence/verifier-app-test.txt` — fail `units/[id]/page.test.ts` (missing `Select a type` display value) |
| `pnpm app:check` | repo root | **0** | `evidence/verifier-app-check.txt` (0 errors, 4 a11y/state warnings) |
| `pnpm program:domain-guards` | repo root | **0** | `evidence/verifier-domain-guards.txt` |
| `python tools/agent/validate_repo.py --scope backend` | `apps/textbook-agent` | **FAIL** | `evidence/verifier-validate-backend.txt` — `[backend-ruff] FAIL`, Found **8** errors; pytest started then log truncated by prior interrupt. Ruff alone fails the gate. |
| `uv run ruff check src/ tests/` | `apps/textbook-agent/backend` | **1** | `evidence/verifier-ruff-stats.txt` — 8 errors: `app.py` I001; `infra/authoring/engine.py` BLE001; `infra/execution/progress.py` PLR1730; `print/.../states.py` F401×3; `test_p03_*.py` / `test_p04_*.py` I001 |
| `uv run python ../tools/agent/check_architecture.py --format text` | backend | **0** | `evidence/verifier-architecture.txt` |
| `uv run pytest tests/reliability/ tests/application/test_p02_admission_stages.py` | backend | **0** | `evidence/verifier-focused-pytest.txt` — **21 passed** |

Summary file: `evidence/verifier-command-summary.txt`.

P06 implementer inventory (`evidence/p06-commands-inventory.txt`) independently confirms `app:test=1` and incomplete `validate-repo-backend` stamp — agrees with verifier.

---

## Code inspection (harsh)

### Call-budget multiplication
- `LLMAuthoringProvider.invoke` sets `repair_attempts=0` and `retries={"output": 0}` — nested SDK retries do **not** multiply engine budget when this provider is used.
- `AuthoringEngine` reserves `CallBudget` before each dispatch; `max_transport_attempts=1`, `max_repair_attempts=2`, default `max_provider_calls=3`.
- **Gap:** `CallBudget` / `CallBudgetLedger` / `CheckpointStore` / `progress_store` appear only under `infra/` (+ optional engine hooks). **No references under `learn/` production modules.** Learn/Print production paths do not default-wire the durable ledger. Focused tests prove scaffolding, not end-to-end Learn accounting.

### Admit-before-provider (Learn)
- `native_execution.py` calls `admit_realization(...)` **before** `produce_learn_document_from_teaching_async` — ordering holds.
- Idempotency key threaded from `units_routes.py`.

### Fencing
- `claim_learn_execution` + `assert_learn_commit_allowed` wired in `native_execution.py` after admit / before publish.
- Competing-worker unit tests exist under `tests/reliability/`.

### ProgressStore auth / redaction
- `progress_routes.py`: owner check via unit `owner_id`; non-owner → 404; requires auth user.
- `redact_secrets` applied to event payloads; exporter failures soft (tests).
- **Gap:** `ProgressStore` is **process-local** (P04 report admits). Not durable across worker restart — fails “durable status/events” literal reading of G16.

### Unit shared-busy / FE store boundaries
- `createUnitWorkspace` uses per-lane `OperationBusyMap` / `setLane` — shared single busy flag removed for Print/Learn jobs.
- `program:domain-guards` includes FE store boundary check — **0** violations on this SHA.
- Route `units/[id]/+page.svelte` composes `createUnitWorkspace`.

### Live evidence (P06 partial)
Present: auth JSON, service health, screenshots (`p06-units-authenticated.png`, unit readback, studio structural, path locked).  
**Absent:** Learn generation provenance, Builder save/publish/attempt IDs, Print edit marker, **PDF binary/text/hash**, run-manifest, controlled interrupt/reconnect recovery proof, competing 409 live tabs.

→ G22/G23 **cannot** be PASS.

---

## Gate matrix G01–G24

| Gate | Verdict | Evidence / reason |
|---|---|---|
| G01 | **PASS** | `p06-auth.json` auth_me=200; `p06-units-authenticated.png`; session `reliability` / profile `.tmp/reliability-chrome-profile`; SHA stamped `dbe3e651`. No secrets exported. |
| G02 | **PASS** | Baseline inventory at `a6b75e33` retained (`P00-REPORT`, ruff/validate logs). Caller/health baseline documented. |
| G03 | **FAIL** | Full backend validator not green on `dbe3e651`: ruff **8** errors (`verifier-ruff-stats.txt` / `verifier-validate-backend.txt`). Historical P01 VALIDATE=0 does **not** certify current SHA. |
| G04 | **FAIL** | `pnpm app:test` **exit 1**; ruff regressions in reliability/progress tests/src. Architecture guards **PASS**. Focused reliability tests PASS but do not replace failing inventory. |
| G05 | **PASS** | Stage registry + unknown/illegal/approval-wait coverage in `test_p02_admission_stages.py` (included in 21 focused passes). |
| G06 | **PASS** | Additive admission migration + existing-doc admit identity covered in P02 tests; no evidence of breaking load of NULL-key rows. |
| G07 | **PASS** | Admission request-key replay / payload conflict / concurrent one-row assertions in focused suite. Code path admits before provider. |
| G08 | **PASS** | Effect-key replay/conflict + builder `expected_updated_at` coverage in P02 tests. |
| G09 | **FAIL** | Checkpoint reuse proven only against isolated `CheckpointStore` unit tests. **Not wired** into Learn production (`learn/` has zero CheckpointStore usage). Worker-death survival of real Learn composition unproved. |
| G10 | **FAIL** | `selective_recovery_keys` helper tested; P03 report admits media/assembly/export not proven in product path; no production invocation counts from live/real executor. |
| G11 | **FAIL** | Engine+fake-provider tests show ≤3 when budget attached. Production Learn path does **not** attach `CallBudgetLedger` / persist budget across workers. Cannot certify cap “across restarts and manual resume” on real Learn. |
| G12 | **PASS** | `error_policy` / Retry-After / permanent vs retryable / stream-after-200 covered in `test_p03_durable_budget_checkpoints.py`. |
| G13 | **PASS** | Learn fencing modules + `native_execution` claim/commit fence + competing-worker tests green. |
| G14 | **FAIL** | ResourceLimits / cost reservation exist as scaffolding tests only; not shown persisted/enforced on live Learn/Print admission path. |
| G15 | **PASS** | Incompatible checkpoint schema + declared/budgeted heuristic fallback covered in focused P03 tests; native_execution threads `allow_heuristic_composition_fallback`. |
| G16 | **FAIL** | Progress APIs exist and unit tests pass, but store is **process-local** — not durable across disconnect/worker restart as required. Status DB overlay ≠ durable event ledger. |
| G17 | **FAIL** | Trace sample is test-generated (`p04-trace-sample.json`). AuthoringEngine records traces only if `progress_store` set — **not default-on** in Learn/Print production. |
| G18 | **PASS** | Unauthorized → 401/403; non-owner → 404; redaction; soft exporter outage tests in `test_p04_progress_observability.py`. |
| G19 | **PASS** | Thin Unit route + domain stores; FE store boundary guard green; `program:domain-guards` exit 0. |
| G20 | **FAIL** | Vitest proves dual-lane busy + subscription dispose. **No** live browser reconnect/SSE proof against running worker (P05 admits; P06 evidence has none). Gate requires browser reconnect proof. |
| G21 | **FAIL** | Vitest dirty/409 helpers pass. **No** two-editor/live browser 409 proof; no independent sibling hash live evidence. |
| G22 | **FAIL** | Live journey incomplete. Screenshots/auth only. **No retained PDF**, no Learn response persistence chain, no Print marker→PDF extract. Auth available ⇒ not BLOCKED — required artifacts missing ⇒ **FAIL**. |
| G23 | **FAIL** | No controlled interrupt/reconnect/repeated-admission live recovery pack. Mock/unit recovery ≠ live. No run-manifest linking recovery. |
| G24 | **FAIL** | Mandatory commands not all green (`app:test`, ruff/validate). Gates G03–G04, G09–G11, G14, G16–G17, G20–G23 failed. Artifacts incomplete. |

---

## Contradictions (implementer vs verifier)

1. **STATE / phase reports** mark G03–G21 PASS and phases P01–P05 PASS, but **current SHA** fails ruff + `app:test` → G03/G04/G24 cannot be PASS.
2. **P03/P04** label G09–G18 “PASS (scaffolding)” while admitting unwired production paths / process-local stores — verifier treats durability/product-wiring requirements as **FAIL**, not PASS.
3. **P05** claimed G20/G21 PASS without live browser proofs required by strict gates.
4. **STATE `implementation_sha`** lagged HEAD (`6281f5d9` vs `dbe3e651`); historical green logs at older SHAs do not certify HEAD.
5. **P05** claimed `program:domain-guards` red; on `dbe3e651` verifier rerun is **green** — prior note stale (positive correction only).
6. **P06** evidence in progress without `P06-REPORT.md`, PDF, or run-manifest — cannot flip G22/G23.

---

## Final decision

**NOT_READY** on `dbe3e651ea12c4fc0c9acb70a7dfe60d9c113eb1`.

READY requires all G01–G24 PASS on one implementation SHA with retained live PDF/provenance and green full command inventory. None of those hold simultaneously.

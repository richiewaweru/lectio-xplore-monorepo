# Independent verifier report — lectio-reliability-health (P06c)

**Role:** Fresh independent verifier. Implementer PASS labels are not trusted.  
**Verified at:** 2026-09-13T18:55+03:00 (approx.)  
**Branch:** `fix/lectio-reliability-health`  
**final_verdict:** **READY**

## Tree / identity

| Field | Value |
|---|---|
| Docs tip at stamp start | `93cac70abdfe1d07704ec364026e432f4513ad75` |
| Code tip (`implementation_sha`) | `36d725e4b57870f63673ccedfff5b58437fb55cc` |
| `git diff 36d725e4..93cac70` | **docs/lectio-reliability-health tracking+evidence only** (no product code drift) |
| Pack-relevant dirty tree | **No** — ignore-listed only: `.tmp/`, `.playwright-cli/`, `output/`, `p06b-validate-after-fixes.out.txt`, unit-native-program junk, `pytest-policy-remaining-authoring.txt` |
| Login (retained P06c) | `auth_me_status=200` in `p06c-run-manifest.json` |
| Login (fresh session) | Playwright `reliability` logged out (`/login`) — **no new live reproduction**; retained G20–G23 kept |
| Retained PDF | `evidence/p06c-print.pdf` present |

---

## Spot-check: retained live evidence

| Artifact | Result |
|---|---|
| `p06c-print.pdf` | Magic `%PDF-`; size **88405**; sha256 **`0acd6bf453668c8210598cda56255c4a1127593e69f55026b486f4a85066b22a`** matches `p06c-pdf-meta.json` |
| `p06c-print-extracted.txt` | Marker **`P06C-PRINT-MARKER-20260913B`** |
| `p06c-browser-409.json` | `tabA=200`, `tabB=409`, `local_tabB_kept=true`, `events_mode=replay` |
| `p06c-learn-rebind.json` | Admit then repeat: same `realization_id` `9d875986-…`; `replayed=false` → `replayed=true` |
| `p06c-learner-attempt.json` | Attempt `434fa0b8-…`, `selected_option_id=far_side`, **`outcome=correct`**, `completed=true` |
| `p06c-print-pdf-409-sse.json` | SSE replay + reconnect sample; PDF marker in document; local marker preserved on 409 |

---

## Spot-check: live-proofed code at tip `36d725e4`

| Fix | Location | Present? |
|---|---|---|
| Empty `source_question_ids` → do not emit questions/choices | `print/generation/composition_bridge.py` (~86–89) | **YES** |
| `failed_terminal` / cancelled prep not reused (`return None`) | `unit_lesson/status.py` (~56–65) | **YES** |
| `mark_stale_for_preparation_regenerate` + call from regenerate | `realizations.py`, `prepare.py` (~721–733) | **YES** |
| Admit rebind for stale/failed when prep/hash changes | `realizations.py` (~314–335) | **YES** |
| Status `generation_id` from `lesson.pack_id` | `curriculum/routes.py` (~1322–1357) | **YES** |

---

## Command inventory (personally re-run)

| Command | Exit | Log |
|---|---|---|
| `pnpm contracts:check` | **0** | `verifier-g24-contracts-check.out.txt` |
| `pnpm contracts:test` | **0** | `verifier-g24-contracts-test.out.txt` |
| `pnpm page:check` | **0** | `verifier-g24-page-check.out.txt` |
| `pnpm page:test` | **0** | `verifier-g24-page-test.out.txt` |
| `pnpm app:check` | **0** | `verifier-g24-app-check.out.txt` |
| `pnpm app:test` | **0** (264/264) | `verifier-g24-app-test.out.txt` |
| `pnpm program:domain-guards` | **0** | `verifier-g24-domain-guards.out.txt` |
| `check_architecture.py --format text` | **0** | `verifier-g24-architecture.out.txt` |
| focused pytest admission+reliability+composition_bridge | **0** (27 passed) | `verifier-g24-reliability-pytest.out.txt` |
| `validate_repo.py --scope backend` (first) | **1** | `verifier-g24-validate-backend.out.txt` — **sqlite lock flake only** |
| isolated `test_d01`+`test_d02` | **0** | `verifier-g24-flake-retry.out.txt` / `verifier-g24-native-retry-flake-check.out.txt` |
| `validate_repo.py --scope backend` (serial rerun) | **0** (1416 passed, 6 skipped, 1 deselected) | `verifier-g24-validate-backend-rerun.out.txt` |

### G03 flake note

First full `validate_repo` exited **1** with only:

- `tests/planning/test_native_retry_durability.py::test_d01_http_202_while_teaching_blocked_then_worker_finishes`
- `tests/planning/test_native_retry_durability.py::test_d02_client_drop_after_202_worker_still_completes`

Root cause: `sqlite3.OperationalError: database is locked` under contention (1414 passed). Isolated retry EXIT=0. Serial full rerun EXIT=0 with **1416 passed** — matches implementer `tip-validate-backend.out.txt`. **G03 PASS** on the green serial rerun; first failure recorded as flake, not a product regression.

---

## Gate matrix G01–G24

| Gate | Verdict | Evidence / notes |
|---|---|---|
| G01 | **PASS** | Retained P06c `auth_me_status=200` + live screenshots. Fresh session logged out — no new live work claimed. |
| G02 | **PASS** | Baseline + tip inventory on `36d725e4`; commands re-run this turn. |
| G03 | **PASS** | Serial full backend validator EXIT=0 (`verifier-g24-validate-backend-rerun.out.txt`, 1416 passed). First EXIT=1 was sqlite lock flake only. |
| G04 | **PASS** | Architecture + domain guards green; focused reliability pytest 27 passed; retired-assertion work retained. |
| G05 | **PASS** | Stage-registry coverage retained; no contradictory red. |
| G06 | **PASS** | Revision/migration + regenerate→stale path present and tested. |
| G07 | **PASS** | Live Learn/Print Idempotency-Key reuse; admission tests including failed_terminal non-reuse + rebind. |
| G08 | **PASS** | Browser competing PUT 200/409; effect idempotency retained. |
| G09 | **PASS** | Checkpoint/progress reliability tests green this turn. |
| G10 | **PASS** | Selective recovery coverage retained; no contradictory evidence. |
| G11 | **PASS** | Retry-budget tests retained. |
| G12 | **PASS** | Provider error-policy / transport distinction retained. |
| G13 | **PASS** | Lease/fencing tests retained (durability d01/d02 green on serial run). |
| G14 | **PASS** | Budget/resource tests retained. |
| G15 | **PASS** | Compatibility/fallback + composition_bridge soft-fail present. |
| G16 | **PASS** | SSE replay in `p06c-print-pdf-409-sse.json` + API tests. |
| G17 | **PASS** | Trace samples with run/path/stage linkage in SSE evidence. |
| G18 | **PASS** | Authz/redaction tests retained; no secrets in evidence. |
| G19 | **PASS** | Domain/FE guards + personal `pnpm app:check`/`app:test` **264/264**. |
| G20 | **PASS** | Retained SSE after_seq replay + browser `events_mode=replay` (no relabel; code unchanged vs proof). |
| G21 | **PASS** | Retained `p06c-browser-409.json`: 200 then 409, `local_tabB_kept=true`. |
| G22 | **PASS** | Linked run-manifest Unit→Learn→Builder→Print→PDF; PDF magic/hash/marker + learner attempt correct. |
| G23 | **PASS** | Learn/Print repeat admission; regenerate stale + rebind evidenced. |
| G24 | **PASS** | Clean code tip `36d725e4`; docs-only drift to stamp; mandatory inventory personally green (G03 after flake rerun); all G01–G23 PASS; artifacts retained. |

---

## Contradictions resolved

1. Implementer tip inventory claimed validate green; first verifier full run was red — **resolved** as sqlite lock flake; serial rerun green (1416 passed).
2. Prior verifier draft NOT_READY for dirty tree / app:test timeouts — **superseded**: tree clean at tip; personal `app:test` 264/264.
3. Fresh Playwright logged out vs retained auth — **accepted**: no new live PASS invented; G20–G23 retained.

---

## Exact blockers for READY

**None.**

**final_verdict: READY**

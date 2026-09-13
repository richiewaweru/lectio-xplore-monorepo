# Independent verifier report — lectio-reliability-health (P06c)

**Role:** Fresh independent verifier. Implementer PASS labels are not trusted.  
**Verified at:** 2026-09-13T16:50+03:00 (approx.)  
**Branch:** `fix/lectio-reliability-health`  
**final_verdict:** **NOT_READY**

## Tree / identity

| Field | Value |
|---|---|
| HEAD (committed tip) | `6d84d30691b35f3fc8dd0d4540be81598cc8d95f` |
| STATE.json `implementation_sha` | `6d84d30691b35f3fc8dd0d4540be81598cc8d95f` (matches HEAD) |
| Dirty tree | **YES** — large uncommitted set including composition_bridge / realizations stale-rebind / status pack_id / authoring+progress wiring / FE tests + untracked `p06c-*` evidence |
| Code under live proof | **Dirty working tree atop `6d84d306`** (manifest + STATE explicitly say live G20–G23 ran against uncommitted fixes) |
| Login (retained P06c) | `auth_me_status=200` in `p06c-run-manifest.json` |
| Login (fresh optional) | Playwright session `reliability` → `/units` then **redirect `/login`** (session not currently authenticated) |
| Retained PDF | `evidence/p06c-print.pdf` present |

**Certification blocker:** Dirty tree means there is no single clean certified tip SHA that includes the live-proofed code. G24 cannot PASS.

---

## Spot-check: retained live evidence (invent nothing)

| Artifact | Result |
|---|---|
| `p06c-print.pdf` | Exists; magic `%PDF-`; size **88405**; sha256 **`0acd6bf453668c8210598cda56255c4a1127593e69f55026b486f4a85066b22a`** matches `p06c-pdf-meta.json` |
| `p06c-print-extracted.txt` | Contains marker **`P06C-PRINT-MARKER-20260913B`** |
| `p06c-browser-409.json` | `tabA=200`, `tabB=409`, `local_tabB_kept=true`, `events_mode=replay` |
| `p06c-learn-rebind.json` | Admit then repeat: same `realization_id` `9d875986-…`; `replayed=false` then `replayed=true` |
| `p06c-builder-print.json` | Builder marker `P06C-BUILDER-EDIT-20260913B`; print admit → output `7206057e-…`; `print_repeat.same_rid=true` |
| `p06c-learner-attempt.json` | Attempt `434fa0b8-…`, `selected_option_id=far_side`, **`outcome=correct`**, `completed=true` |
| `p06c-print-pdf-409-sse.json` | Replay `after_seq=2` HTTP 200; stream sample; reconnect sample after `Last-Event-ID=3` includes seq 4; also records **`sse_stream_reconnect_error: "timed out"`** (partial stream reconnect) |
| Screenshots | `p06c-print-studio.png` / reloaded / after-409 retained (studio shows logged-in UI + rev) |

**Intermediate noise (not treated as final journey proof):** `p06c-builder-print-admit.json` shows earlier 422 learner body + print admit still on superseded pack `8a890460-…` — superseded by successful `p06c-builder-print.json`.

---

## Spot-check: code fixes on disk (dirty tree)

| Fix | Location | Present? |
|---|---|---|
| Empty `source_question_ids` → do not emit questions/choices; fall back to document | `print/generation/composition_bridge.py` (~86–89) | **YES** |
| `mark_stale_for_preparation_regenerate` + call from regenerate | `unit_lesson/realizations.py`, `prepare.py` | **YES** |
| Admit rebind for stale/failed when prep/hash changes | `realizations.py` (~314–335) | **YES** |
| `failed_terminal` / cancelled prep not reused | `unit_lesson/status.py` (~56–65 returns `None`) | **YES** |
| Lesson status `generation_id` from prep / `lesson.pack_id` | `curriculum/routes.py` (~1350–1356) | **YES** |

---

## Command inventory (this turn)

See `evidence/verifier-p06c-commands-inventory.txt`.

| Command | Exit | Log |
|---|---|---|
| `pnpm program:domain-guards` | **0** | `verifier-p06c-domain-guards.out.txt` |
| `check_architecture.py --format text` | **0** | `verifier-p06c-architecture.out.txt` |
| focused pytest `tests/reliability/` + print_learn p05/p08 | **0** (30 passed) | `verifier-p06c-reliability-pytest.out.txt` |
| `pnpm contracts:check` | **0** | `verifier-p06c-contracts-check.out.txt` |
| `pnpm contracts:test` | **0** | `verifier-p06c-contracts-test.out.txt` |
| `pnpm page:check` | **0** | `verifier-p06c-page-check.out.txt` |
| `pnpm page:test` | **0** | `verifier-p06c-page-test.out.txt` |
| `pnpm app:check` | **0** | `verifier-p06c-app-check.out.txt` |
| `pnpm app:test` | **1** — **7 failed** (timeouts), 257 passed / 264 | `verifier-p06c-app-test.out.txt` |
| `validate_repo.py --scope backend` | **NOT_RUN this turn** | retained `p06b-validate-final.out.txt` exit=0, 1413 passed (earlier dirty stamp) |

`app:test` failures (all `Test timed out in 5000ms`): onboarding recovery, V3BookletIssuesPanel, 4× V3InputSurface, compositionId page load.

---

## Gate matrix G01–G24

| Gate | Verdict | Evidence / notes |
|---|---|---|
| G01 | **PASS** | Retained P06c `auth_me_status=200` + live screenshots. Fresh optional `/units` now redirects to `/login` — new live work blocked; does not erase retained auth proof. |
| G02 | **PASS** | Baseline SHA / inventory retained from earlier phases; commands inventoried. |
| G03 | **PASS** | Retained full backend validator green (`p06b-validate-final.out.txt` exit=0). Not re-executed this turn on tip. |
| G04 | **PASS** | Architecture/domain guards green this turn; focused reliability pytest green; prior retired-assertion work retained. |
| G05 | **PASS** | Prior stage-registry coverage retained; no contradictory red this turn. |
| G06 | **PASS** | Prior revision/migration tests retained; regenerate→stale path present in code. |
| G07 | **PASS** | Live Learn/Print Idempotency-Key reuse evidenced; DB-backed tests retained from earlier phases. |
| G08 | **PASS** | Browser competing PUT 200/409; effect idempotency tests retained. |
| G09 | **PASS** | Checkpoint/progress wiring + reliability tests (18+ focused) retained/green. |
| G10 | **PASS** | Selective recovery tests retained; no contradictory evidence. |
| G11 | **PASS** | Retry-budget tests retained. |
| G12 | **PASS** | Provider error-policy / transport distinction retained. |
| G13 | **PASS** | Lease/fencing tests retained. |
| G14 | **PASS** | Budget/resource tests retained. |
| G15 | **PASS** | Compatibility/fallback coverage retained; composition_bridge soft-fail present. |
| G16 | **PASS** | SSE replay evidence in `p06c-print-pdf-409-sse.json` + prior API tests. |
| G17 | **PASS** | Trace samples with run/path/stage/item/attempt/prompt_hash in SSE evidence. |
| G18 | **PASS** | Authz/redaction tests retained; no secrets in retained evidence. |
| G19 | **FAIL** | Domain/FE boundary guards + `app:check` pass, but mandatory **`pnpm app:test` exit=1** on this dirty tree (7 timeouts). |
| G20 | **PASS** | SSE after_seq replay + browser `events_mode=replay`; stream reconnect partially proved (sample after Last-Event-ID) despite timeout flag. |
| G21 | **PASS** | `p06c-browser-409.json`: 200 then 409, `local_tabB_kept=true`. |
| G22 | **PASS** | Linked run-manifest Unit→Learn→Builder→Print→PDF; PDF magic/hash/marker + learner attempt correct. |
| G23 | **PASS** | Learn/Print repeat admission; regenerate stale + rebind evidenced; SSE reconnect samples. |
| G24 | **FAIL** | **(1)** Dirty tree — live proofs/code not on a clean certified tip. **(2)** `pnpm app:test` exit=1. **(3)** Full `validate_repo --scope backend` not personally re-run on current tip this turn. |

---

## Contradictions

1. Implementer labels G20–G23 PASS and implies closeout, while STATE/`p06c-run-manifest` admit proofs ran on **dirty** code — cannot claim G24 READY.
2. `sse_stream_reconnect_error: "timed out"` vs implementer unqualified SSE reconnect PASS — still enough partial evidence for G20/G23 PASS, but not clean.
3. Prior P06b verifier: auth blocked + no PDF; P06c retained evidence shows auth+PDF recovery — accepted after spot-check.
4. Earlier `p06b` inventory had `app:test` green; **this verifier re-run is red** (timeouts) — mandatory inventory not green on current dirty tip.
5. Fresh Playwright `reliability` session is **logged out** (`/login`) while STATE still says `AUTHENTICATED`.

---

## Exact blockers for READY

1. Commit all reliability fixes + evidence into one tip SHA; re-run mandatory inventory on that clean tip.
2. Fix or re-prove `pnpm app:test` (currently exit 1 / 7 timeouts).
3. Personally re-run `validate_repo.py --scope backend` on the certified tip and retain the log.
4. Re-establish authenticated browser session before any new live reproduction.

**final_verdict: NOT_READY**

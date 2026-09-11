# Independent Verifier Report — Treasure Joe Final Cleanup

**Role:** Independent verifier (not implementer)  
**Date:** 2026-09-11  
**Branch:** `fix/treasure-joe-final-cleanup` (tracks `origin/fix/treasure-joe-final-cleanup`)  
**Do not merge.** Implementer PASS labels treated as untrusted.

## Commit SHAs

| Role | SHA | Notes |
|------|-----|--------|
| Baseline | `6f782e94769d0dfce34b2dd80d1d462a9c38bd04` | Program start |
| Implementation (A–E product) | `5bebfbad40e2c4f510e54a5c01670cdd5d952b5e` | “Close Treasure Joe cleanup…” |
| Tracking stamp | `d6fa1d8f8eea32e9a8d0358c2d50df1b0d68af5a` | Stamp commit |
| Correct tracking SHA record | `e0ea977da76d609b4292bf198b8e1b9cf0456d37` | Had `final_tracking_sha: d6fa1d8f…` |
| **Origin tip (verified)** | `7123f0db291c0f6793d878476ce0b909862ba02b` | Normalize tracking / Phase F evidence |

Working tree at verification time also had an **uncommitted** edit to `docs/treasure-joe-final-cleanup/tracking/STATE.json` (renames field / replaces tip placeholder). Tip on origin is what counts.

---

## Phase verdicts (A–F)

| Phase | Verifier verdict | vs implementer |
|-------|------------------|----------------|
| **A** | **PASS** | Agree |
| **B** | **PASS** | Agree |
| **C** | **PASS** | Agree |
| **D** | **PASS** (with provenance caveats) | Agree on outcome; dispute completeness of stamped chain |
| **E** | **PASS** (with artifact packaging caveats) | Agree on outcome; PDF binary not retained |
| **F** | **FAIL** | Agree FAIL; add automatic FAIL for `pending-this-commit` on tip |

---

## Automatic FAIL conditions — findings

### A — unknown learner action can survive approval and disappear downstream

**Not triggered.**

- Vocabulary is YAML-backed (`resources/policies/learner-actions.yaml`).
- Approval/generation path calls `_unknown_learner_action_errors` and fails closed (`TEACHING_UNKNOWN_LEARNER_ACTION`).
- `describe-in-own-words` is intentionally **unknown** (not aliased); repair hint points to `enter-text` / MC-compatible actions.
- Alias `reconstruct-order` → `order-items` resolves; every canonical non-passive action has Learn + Print map (unit tests).
- Note: `resolve_learner_action()` returns the raw string for unknowns (does not return `None`), but Learn/Print maps return `None` and the teaching ownership gate rejects unknowns before approval — so the automatic FAIL path is blocked.

### B — hash-only prompt / unnecessary LLM / illegal escape

**Not triggered.**

- `_select_interaction_for_block`: single candidate → `deterministic_single`, no LLM; multi → `llm_multi_candidate` via `effective_prompt_text("interaction-selection")` + legal-set validation.
- Tests assert no prompt load / no LLM for one candidate; illegal multi pick raises.

### C — executable v1 ordinary Learn generation/salvage remains

**Not triggered.**

- `apps/textbook-agent/backend/src` has **0** hits for: `build_closed_learn_production`, `_async`, `host_interaction_blocks_for_builder`, `closed_learn_selection`, `assemble_ordered_learn_document`.
- `ordered_assemble.py` absent; `test_zero_v1_learn_salvage.py` green inside `tests/learn`.
- Remaining `explanation-block` / `LessonDocument v1` hits are docs, retired-runtime messaging, or historical tests — not active v1 salvage production.

### D — seed script / injected action / Builder manual / attempt not persisted

**Not triggered as automatic FAIL**, with caveats.

- Script used is Unit HTTP path (`live_treasure_joe_d_unit_learn.py` → `realizations:generate-learn`), not seed-to-Builder.
- Final stamp `phase-d-PASS.json` / `phase-d-20260911T151048.json`:
  - `unit_id` `f8b9a4eb-346e-45b1-af35-e2248a10788a`
  - `generation_id` / pack `5d43ce47-6036-4fc2-ac12-31ba68e5f9e9`
  - LearnDocument v2, `composition_mode=llm`, Builder `open_href` `/builder/2c7f23aa-…`
  - Attempt `66d4cfd8-…` outcome `correct`, `reloaded_attempt_count: 1`
  - Teaching actions: `enter-text`, `select-one`, `select-one`; `unknown_actions: []`
- **Caveat:** Final PASS stamp is a **resume** (path_note: generate-learn earlier; this stamp = publish→attempt→reload). No single JSON in evidence records the full create→generate-learn HTTP steps for `f8b9a4eb`.
- **Discrepancy:** `phase-d-20260911T150923.json` is labeled `status: PASS` with `attempt.id/outcome: null` and no `composition_mode` — does not meet the script’s own PASS criteria. Do not treat that intermediate as proof.

### E — UI-only PDF / marker absent / no stale protection / Learn sibling changed

**Not triggered as automatic FAIL**, with packaging caveats.

- `phase-e-PASS.json` records: save 200 (rev 4→5), stale PUT **409** `stale document revision`, export PDF 200 `application/pdf` ~98286 bytes, `reload_has_marker: true`, `learn_sibling_unchanged: true` (same `updated_at`).
- Marker `TJ-E-MARKER-2EE22CCB16` present in `phase-e-20260911T224742-pdf-text.txt` as split lines `TJ-E-MARKER-` + `2EE22CCB16`; whitespace-compacted text contains the full marker.
- **Caveat:** Claimed PDF path is **not on disk and not in git** (0 `*.pdf` under evidence). Verification used the committed text extract + JSON, not a re-parsed PDF binary. Evidence does not look forged, but packaging is incomplete.

### F — contracts skipped / pending-commit / matrix unproven

**Triggered.**

1. **`pending-this-commit` remains on origin tip**  
   `7123f0db` `STATE.json` has `"final_tracking_sha": "pending-this-commit"`.  
   Prior commit `e0ea977d` had already recorded the real stamp SHA; tip **regressed** the placeholder. Automatic FAIL: *pending-commit remains*.
2. **`validate_repo --scope backend` red** (implementer-documented; also visible in `phase-f-commands.txt`: ruff + planning/other pytest failures). Pack-required focused gates are not a substitute for the COMMANDS.md validate_repo requirement when the matrix still tracks it.
3. Matrix honestly leaves independent verifier / validate_repo unchecked and overall **NOT READY** — consistent with FAIL, but tip tracking placeholder still violates the search/tracking gate.

`independent_verifier: pending-launch` in tip `phase-f-PASS-FAIL.json` is expected pre-verifier and is updated by this report.

---

## Commands personally run

Timestamps local (UTC+3) unless noted.

| Command | Exit | Result | When |
|---------|------|--------|------|
| `uv run pytest tests/core/policies/test_action_maps.py tests/print_learn/test_learner_action_policy.py tests/application/test_p03_realization_gates.py -q` | **0** | **21 passed** | 2026-09-11T23:42:35+03 |
| `uv run pytest tests/learn -q` | **0** | **27 passed** | 2026-09-11T23:42:36+03 |
| `uv run pytest tests/print_learn -q` | **0** | **77 passed** | 2026-09-11T23:45:06+03 |
| `pnpm program:domain-guards` | **0** | Domain + backend boundaries PASS; ZERO_LEGACY_GUARD PASS; 6 pytest passed | 2026-09-11T23:45:07+03 |
| `uv run python ../tools/agent/check_architecture.py --format text` | **0** | No architecture violations found | 2026-09-11T23:47:21+03 |
| `pnpm contracts:check` | **0** | tsc `--noEmit` OK | 2026-09-11T23:47:22+03 |
| Search gates on `backend/src` for v1 salvage needles | n/a | **0** matches each | during verification |
| PDF text extract marker check | n/a | Compact marker **present**; PDF binary **missing** | during verification |

**Not re-run (expensive / already evidenced red):** full live LLM Unit generate-learn; full `pnpm app:test` / `page:test` / `contracts:test` / `validate_repo` (implementer log shows validate_repo exit 1; app_test later green at 257 in `phase-f-app_test.txt` after earlier failures in the command log).

---

## Live IDs / artifacts checked

### Phase D
- Evidence: `phase-d-PASS.json`, `phase-d-20260911T151048.json`, `phase-d-20260911T150923.json`, `phase-d-resume-path.json`, script `live_treasure_joe_d_unit_learn.py`
- IDs: unit `f8b9a4eb-…`, generation/pack `5d43ce47-…`, editable/builder `2c7f23aa-…`, output `learn-out-c39225773acd`, release `5b1ed79a-…`, instance `92a16141-…`, attempt `66d4cfd8-…` / interaction `ix-b85328663c1b`

### Phase E
- Evidence: `phase-e-PASS.json`, `phase-e-20260911T224742.json`, `phase-e-20260911T224742-pdf-text.txt` (PDF file absent)
- Marker `TJ-E-MARKER-2EE22CCB16`; prep/doc `b17572f5-…`; Learn sibling `6b7f1426-…` / `learn-out-ccd04ae62c17`

### Phase F
- `phase-f-PASS-FAIL.json`, `phase-f-commands.txt`, `phase-f-search-gates.txt`, `phase-f-app_test.txt`, `STRICT_GATE_MATRIX.md`, tip `STATE.json`

---

## Discrepancies vs implementer claims

1. **Tip `STATE.json` still has `final_tracking_sha: pending-this-commit`** despite stamp/follow-up commits and matrix note that tracking uses actual SHA. Working-tree-only fix is not on origin tip.
2. **`7123f0db` regresses** the real SHA recorded in `e0ea977d`.
3. **Phase D intermediate `150923` marked PASS** without a successful attempt / composition_mode — overclaim.
4. **Phase D final proof is resume-closed**; full generate-learn HTTP stamp for the winning unit is narrative, not a single artifact.
5. **Phase E PDF binary** referenced in PASS JSON is not retained in the repo/evidence tree.
6. **Phase F `app:test`:** command log shows early exit=1 (3 failed); later `phase-f-app_test.txt` shows 257 passed — claim is eventually true, but the aggregate command log is messy.
7. Implementer already marks **F FAIL** / matrix **NOT READY** — that part is consistent; independent verifier does **not** upgrade to merge-ready.

---

## Final recommendation

```text
NO — NOT READY
```

Primary blockers: origin tip still contains `pending-this-commit` in tracking (Phase F automatic FAIL), and `validate_repo --scope backend` remains red. Product phases A–C look solid under independent code/test/search review; D/E live outcomes look credible with packaging/provenance caveats that do not by themselves force merge readiness while F is red.

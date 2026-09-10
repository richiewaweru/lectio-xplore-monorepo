# Policy cleanup v4 — FINAL REPORT

```text
Implementation branch: feat/unit-print-learn
Baseline commit: c3563abbb141443bc0131917d09de81a8e4c118a
Tested code commit: 80cbc1685f4830a55379912adfaea06302cec0c3
Working-tree state during tests: clean for implementation files; unrelated .tmp/ and P09 artifacts preserved
Evidence/report commit: (this docs commit)
```

## Changes by phase

### P0
- Documented baseline (exact match to reviewed SHA), caller map, superseded remaining-fixes clauses, G01–G24 ledger.

### P1
- Package `knowledge` / `assessment` on Learn and Print writer views; regenerated exports.
- Shared `infra.authoring.policy_resolver` with `POLICY_CONFLICT`, decision snapshot, legacy-absent-v1.
- Extended `AuthoringProvenance.policy` and prompt knowledge blocks.

### P2
- Removed objective/title/arc → facts substitution and id-as-statement.
- Mode-aware input validation (`supplied_preferred` allows empty facts; `supplied_only` fails).
- Print executor threads packet statements into `allowed_facts`.
- Removed brief/`Offline fixture fact.` invention in interaction writer.

### P3
- `_convert_short_response` uses explicit assessment resolution + authorized fallback.
- Builder PUT validates interaction contracts.
- Runtime G18 proves automatic correct/incorrect and teacher-review pending-review.

### P4
- Persistence/publish/Builder gates; G22 isolated mutation red tests; retained suite rerun.

## G01–G24

All **PASS**. See [GATES.md](GATES.md). Evidence under [evidence/](evidence/).

## Old-behavior detection (G22)

Isolated worktree at `.tmp/policy-g22-mutation` (base `80cbc168`):

1. Restored objective-as-fact substitution → `test_g09_objective_never_becomes_fact` failed with `assert ['Explain evaporation'] == []`.
2. Bypassed assessment permission to force teacher-review on missing answers → `test_g14_automatic_required_missing_answer_fails` failed with `DID NOT RAISE Exception`.

Log: `evidence/g22-mutation-failures.txt`. Deliverable branch untouched.

Positive authorized fallback: `test_g16_automatic_preferred_fallback_records_reason`.

## Existing gate regressions and skip accounting

| Suite | Result |
| --- | --- |
| `tests/policy_cleanup/` | 22 passed |
| `tests/remaining_fixes/` + `tests/authoring_correction/` | 124 passed, 3 skipped |
| P06/P07/P08 | 30 passed |
| `interaction-shells.r04.test.ts` | 9 passed |

Superseded clauses with equivalent coverage:

- Empty-facts generate ban → G06/G07/G10 + remapped `test_r02_g05_*`
- Silent missing-answer teacher-review → G14/G15/G16 + remapped R01/A04 convert cases

## Environment blockers

None for offline mandatory gates.

## Remaining defects

- Student UI still does not mount short-response server attempts (live deferred).
- No teacher grading dashboard (out of scope).
- Print knowledge instructions updated for prose; other Print form instruction files still generic (resolver/prompt block covers semantics).

## Live acceptance: DEFERRED

Not established by offline mocks. Pending: real-model objective-development inspection; supplied-only adherence; browser Builder/publish/reload; learner automatic and teacher-review journeys; Print PDF inspection.

## Overall: OFFLINE ACCEPTED

Every G01–G24 passed against tested code commit `80cbc168`. Offline acceptance does not mean live acceptance.

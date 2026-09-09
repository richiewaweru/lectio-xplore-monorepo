# R00 Plan — Reopen gates and reproduce

## Scope

Documentation, v2 gate reopen notes, and failing regression tests only. No product fixes, no xfail markers, no weakening of assertions.

## Phase steps

1. Confirm branch and baseline identity at `db157f00731602c35ec1ec1e71fd5cc5d21e655b`; preserve pre-existing dirty work (P05 image evidence, `.tmp`, backend logs/data, P09 scripts).
2. Read `SPECIFICATION.md`, `acceptance/REGRESSION_SCENARIOS.md`, `phases/R00.md`, v2 pack tracking, and `docs/unit-native-program/COMMAND_MAP.md`.
3. Write `tracking/R00-BASELINE.md` and `tracking/R00-CALLER_MAP.md` with exact function paths for prepare → selection → work orders → engine → assembly → persist on Print and Learn.
4. Reopen unsupported A02/A04/A05/A06 PASS claims in v2 tracking; keep historical evidence paths labelled historical.
5. Add five focused regressions under `apps/textbook-agent/backend/tests/remaining_fixes/` mapped to R1–R4 defects:
   - `test_r00_incomplete_activity.py` — numeric generate uses brief as prompt and generic feedback (scenario 1 partial).
   - `test_r00_approved_source_leak.py` — no-ref binds `approved_items[0]`; explicit q2 leaks q1 sentinel (scenarios 2–3 partial).
   - `test_r00_empty_teaching_context.py` — `build_closed_learn_production` hardcodes empty facts (scenario 5 partial).
   - `test_r00_keyword_selection.py` — ambiguous shortlist uses keyword `ranked[0]`, not model selector (scenario 6 partial).
6. Run focused pytest; capture failure logs under `evidence/r00/`.
7. Update `tracking/GATES.csv` (R00-G01..G03 PASS) and `tracking/STATE.json` (R00=PASS).
8. Write `tracking/R00-REPORT.md` and commit with message `test(remaining): reopen unsupported gates and add R00 regressions`.

## Done criteria

- Baseline and caller map identify head, dirty work, and normal production paths.
- Five regressions fail on current HEAD for the intended defect reasons.
- A02/A04/A05/A06 gates marked REOPENED without deleting historical reports or evidence.
- Gate tracking and evidence paths recorded at tested commit.

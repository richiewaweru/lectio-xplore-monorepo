# R03 Plan — Model selector for ambiguous shortlists

## Scope

Implement R4 from `SPECIFICATION.md`: production Learn and Print closed selection must invoke a configured model selector for ambiguous shortlists (len>1). Keyword overlap ranking must not pick production winners. Sole candidates (len==1) stay automatic with no selector call.

## Phase steps

1. **Shared selector (`infra/authoring/capability_selector.py`)**
   - `CapabilitySelection`, `CapabilitySelectionError` with typed codes.
   - `select_capability_from_shortlist`: sole-candidate auto; ambiguous → `choose` with bounded repair on same shortlist; exhaustion → typed failure, no keyword fallback.
   - Payload: eligible IDs, choose_when/reject_when, block brief/intent/action, optional teaching constraints.
   - Default `choose` → `run_capability_selector` (curriculum agents + `native_capability_selector` slot).
   - Thin domain adapters in Learn/Print that build payload from selection views.

2. **Learn (`learn/generation/native_selection.py`, `native_production.py`)**
   - `select_learn_with_model_async` / `build_learn_selection_snapshot_async`: async selection for content and interaction when len>1.
   - Remove production use of `select_learn_deterministically`; keep `rank_*` as explicitly named test utilities.
   - `build_closed_learn_production_async` awaits async snapshot builder.
   - Sync `build_learn_selection_snapshot` delegates to async only when no running loop (tests may pass `choose`).

3. **Print (`print/generation/selection_snapshot.py`, `native_production.py`, `executor.py`)**
   - `select_print_with_model_async` / `build_print_selection_snapshot_async`.
   - `build_closed_print_production_plan_async`; executor awaits it.
   - Remove production `select_print_deterministically` and `prefer_figure_for_visual_slots` hardcoded overrides; pass visual-slot constraints into selector context.
   - Sealed `FormPlan` path: consume without reselecting.

4. **Print source resolver (R02 defer)**
   - `print/generation/source_resolver.py`: resolve `source_refs` only; wire `run_print_authoring`.

5. **Tests (`tests/remaining_fixes/test_r03_*.py`)**
   - R03-G01: Learn content+interaction selector through `build_closed_learn_production_async`.
   - R03-G02: Print selector or sealed plan without second select.
   - R03-G03: Mock nonfirst lexically-disfavored ID honored; sole candidate no call.
   - R03-G04: Invalid ID → repair; exhaustion → typed error; no keyword fallback.
   - R03-G05: Candidate order permutation; no production keyword bonuses.
   - Update `test_r00_keyword_selection` to patch configured selector (no weakening).

6. **Evidence and tracking**
   - Run focused pytest; save `evidence/r03/pytest-r03-all.txt`.
   - Update `GATES.csv`, `STATE.json`, `R03-REPORT.md`.

7. **Commit** — `fix(selection): model selector for ambiguous shortlists`

## Done criteria

- R03-G01..G05 PASS with honest provider-call assertions.
- R00 keyword-selection regression PASS without assertion weakening.
- No production path calls `rank_learn_*` or `rank_print_form_candidates`.

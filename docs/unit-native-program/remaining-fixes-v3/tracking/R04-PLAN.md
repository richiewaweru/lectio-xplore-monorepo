# R04 Plan — Real offline integration and rendering

## Scope

Implement R5 from `SPECIFICATION.md`: gate evidence must use real persistence/API/component boundaries with mocked provider boundaries only. Supersede overstated A06 integrated claims.

## Quality bar (non-negotiable)

**Forbidden as gate evidence:** deepcopy reload, hash-only publish, single Print block via `dispatch_writer_async`, Python `evaluate_interaction` alone, injected `authored_results` maps or direct DB document edits as product journey proof.

**Required:** fresh SQLAlchemy session after close; real publish and runtime APIs; real `@lectio/learn` component mounts; mock only provider/external boundary (labelled MOCK); labelled fixture seeding OK.

## Phase steps

1. **Shared fixtures (`tests/remaining_fixes/r04_fixtures.py`)**
   - Envelope mock provider (MOCK) for eight core interactions.
   - `build_envelope_learn_document()` via `run_learn_work_order_authoring` + `assemble_ordered_learn_document` / `build_closed_learn_production`.
   - API client overrides (reuse P07 pattern): seed user, httpx client, publish helper.

2. **R04-G01 (`test_r04_g01_dual_path_persistence.py`)**
   - Reuse P08 Unit→approve→Print (`execute_after_teaching_approval`) + Learn (`produce_learn_from_approved_teaching`).
   - Persist, close session, **fresh** `async_session_factory` reload.
   - Assert same teaching revision/hash, handoff identity, meaningful content in both outputs.

3. **R04-G02 (`test_r04_g02_publish_builder.py`)**
   - Document from envelope production (not hand-built minimal lesson).
   - POST publish v1 → PUT Builder edit → publish v2 → fresh DB/API reads: v1 immutable, v2 reflects edit.
   - Malformed Builder edit rejected (422) where supported.

4. **R04-G03 (`test_r04_g03_runtime_attempts.py`)**
   - Envelope-produced sequence lesson; publish via API; correct + incorrect attempts via runtime API.
   - Forged client score rejected; fresh DB authoritative.

5. **R04-G04 (`test_r04_g04_writer_failure_retry.py`)**
   - P08 print writer failure injection (`configure_failure_injection`); requeue/retry production path.
   - Learn sibling realization intact; no duplicate logical print blocks after recovery.

6. **R04-G05 (`packages/lectio-learn/.../interaction-shells.r04.test.ts`)**
   - Mount all eight core interaction shells with envelope-shaped contract props; keyboard/submit; offline rendering label.
   - Not evaluator-only.

7. **R04-G06 (`test_r04_g06_instruction_regeneration.py`)**
   - Mutate package instruction → `build_learn_writer_request` / production capture shows new instruction + hash change.
   - Published v1 release snapshot unchanged in fresh DB read after regeneration.

8. **A06 cleanup**
   - Remove or rewrite false-pass tests in `test_a06_integrated_offline.py`; point to R04 gates.
   - Update v2 `A06-REPORT.md` notes.

9. **Evidence and tracking**
   - `evidence/r04/pytest-r04-all.txt`, `evidence/r04/vitest-r04-g05.txt`
   - Update `GATES.csv`, `STATE.json`, `R04-REPORT.md`
   - Commit: `test(remaining): real persist publish attempt and component gates`

## Done criteria

- R04-G01..G06 PASS with honest assertions per POLICY.md.
- A06 no longer claims PASS for superseded behaviors.
- No gate waiver or lowered assertions.

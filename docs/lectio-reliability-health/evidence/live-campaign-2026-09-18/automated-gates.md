# Automated reliability gates

## Passed

- Frontend unit suite: `61` files, `275` tests passed.
- Frontend type/a11y check: `0` errors, `5` pre-existing warnings.
- Backend focused reliability suite: `51` passed, `2` warnings.
- Backend path and realization regression suite: `21` passed, `1` warning.
- Full backend suite: `1462` passed, `6` skipped, `2` deselected, `25` warnings.
- Contracts: `pnpm contracts:test` passed (`20` tests); `pnpm contracts:check` passed.
- Page gates: `pnpm page:test` passed (`64` tests); `pnpm page:check` passed with `0` errors and `0` warnings.
- Architecture gate: no violations.
- Program/domain guards: passed with `0` violations; backend/frontend store boundary and legacy guard passed.

## Reliability repairs covered by tests

- Plan status preserves structured failure metadata and renders recoverable versus terminal states.
- Plan polling stops for approval, ready, completed, cancellation, and failure states; known failures cannot fall through to `working`.
- Native retry test injection is placed at the intended writer boundary.
- Selected-learner route tests use the application’s current dependency override contract without weakening authorization semantics.
- Print retry without an override preserves the preparation output identity and re-admits Print from the shared preparation checkpoint.
- Learn and Print editor navigation uses the dedicated editor routes, avoiding the unreliable in-place tab branch observed during live browser verification.
- Formative shared-response projection admits the exact mapped Print treatment when the historical intent shortlist omits that path-neutral form.
- Plan realization cards distinguish queued/running/preparing from ready even
  when an output ID exists; the queued-Print regression test passed.

## Known warnings

The frontend check reports five existing Svelte warnings in `InteractionEditor`, `DocumentCanvas`, `DocumentEditor`, and `PrintDocumentEditor`. They are non-fatal and were not expanded into this campaign because the check remains error-free.

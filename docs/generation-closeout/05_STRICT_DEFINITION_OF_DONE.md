# Strict Definition of Done

Prior agent passes sometimes implemented a small fraction of a requirement and reported completion. This file prevents that.

## NOT done when

- a file exists but no live caller uses it;
- a fixture passes but Unit flow bypasses the code;
- a prompt exists but production still uses hardcoded instructions;
- an endpoint exists but UI does not call it;
- a renderer exists but live generated data cannot reach it;
- a feature works only after manual DB JSON edits;
- a fallback silently masks the intended stage;
- a report says PASS without required browser/runtime proof;
- TODO/stub/deferred logic remains on canonical path;
- one example passes while Print/Learn semantics still diverge.

## Required evidence for every phase

1. **Call graph** — entrypoint → changed layer → artifact.
2. **Code** — exact changed/deleted files and no competing canonical path.
3. **Automated** — focused tests + affected broader suites + static/type checks.
4. **Production path** — real Unit/Teaching Plan or real saved artifact; real provider for LLM stages; browser route for UI stages.
5. **Negative proof** — old/wrong path cannot still be selected; prompt edits alter effective prompt hash; missing action does not silently become unrelated task.

## Gate status

Only `PASS`, `FAIL`, or `BLOCKED`.

## The 90% rule

A phase may be split if too large. The parent phase is not complete until:
- canonical happy path works end to end;
- error/retry behavior works;
- persistence/reload works where relevant;
- UI is connected where relevant;
- remaining work is cosmetic rather than architectural/behavioral.

Otherwise the phase remains incomplete.

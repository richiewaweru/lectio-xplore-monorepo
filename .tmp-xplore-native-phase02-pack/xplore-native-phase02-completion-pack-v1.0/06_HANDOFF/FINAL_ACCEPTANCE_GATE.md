# Final Acceptance Gate

Phase 02 is accepted only when:

```text
approve returns
worker claims
form persists
writers checkpoint
failure is isolated
restart occurs
worker reclaims
ready blocks skip
failed block retries
assembly reloads DB
document persists
fresh session reloads
teacher PDF passes
student PDF passes
```

## Required evidence

- filled checklist;
- failure/restart log;
- DB verification;
- before/after block report;
- native document and reloaded copy;
- PDF assertions and both PDFs;
- four run manifests;
- final report.

## Automatic rejection

- approval still runs writers inline;
- FastAPI background task is the sole durability mechanism;
- ready blocks regenerate;
- one failure cancels siblings;
- assembly requires local writer results;
- status/stage drift;
- PDF exports with required visuals pending;
- student PDF exposes answers;
- fixture or `resume_stage2` appears in official runs;
- browser automation is claimed as the only proof.

## After acceptance

Begin the quality phase: evaluate prompts, improve slot guidance, expand factual item budgets, tune models, and measure cost/latency. Do not mix those changes into the four baseline runs.

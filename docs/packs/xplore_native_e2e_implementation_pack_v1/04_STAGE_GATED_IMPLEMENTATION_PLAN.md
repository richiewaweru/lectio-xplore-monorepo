# Stage-Gated Implementation Plan

Grok must not advance until the current gate is green.

## Gate 0 — Baseline and evidence directory

Actions:

- confirm branch and clean working tree;
- record current commit;
- run current targeted native tests;
- create `docs/evidence/native-e2e-v1/`;
- capture existing failure behavior for the known run shape.

Pass:

- baseline report exists;
- failures are documented, not silently ignored.

## Gate 1 — Native-only routing

Actions:

- identify all entry points for create, continue, approve, retry, render, and PDF;
- ensure new requests use native v2 only;
- disable legacy entry points in production routing;
- keep historical read compatibility only where required.

Tests:

- route spy proves no legacy builder/stage2/conversion call;
- native generation enters native state machine;
- disabled legacy endpoint returns explicit response.

Pass:

- one request reaches native planning without touching legacy execution.

## Gate 2 — Typed all-form writer registry

Actions:

- define strict models for 8 generated forms;
- add registry;
- reject unsupported objects;
- ensure extra fields fail;
- add aside and choices.

Tests:

- valid/invalid fixtures for each form;
- unknown form test;
- writer cannot change object/intent/ID.

Pass:

- all 8 forms pass valid fixtures and reject broken variants.

## Gate 3 — Questions, choices, and answer key

Actions:

- remove MCQ metadata from questions;
- create choices output;
- create AssessmentBundle;
- stable IDs;
- document-level answer key;
- cross-reference validation.

Tests:

- open response;
- MCQ;
- mixed assessment;
- orphan answer;
- missing answer;
- duplicate ID;
- invalid MCQ letter.

Pass:

- valid bundle assembles; every broken reference fails deterministically.

## Gate 4 — Immediate validation and informed repair

Actions:

- validate writer content before persistence;
- introduce mock provider;
- one repair attempt with prior output and errors;
- separate transport retry from schema repair.

Tests:

- invalid JSON then valid;
- wrong schema then valid;
- extra fields then valid;
- wrong object then valid;
- permanently invalid;
- timeout then valid.

Pass:

- invalid content is never stored as ready;
- permanent invalidity is a recoverable structured error.

## Gate 5 — Pending figure path

Actions:

- deterministic stable request IDs;
- pending asset;
- placeholder renderer;
- no live visual dependency.

Tests:

- pending figure validates;
- missing alt text fails;
- placeholder appears;
- PDF completes with pending visual.

Pass:

- document can become ready with pending figures.

## Gate 6 — Parallel section execution

Actions:

- create one job per section;
- semaphore limit 4;
- persist section/block progress;
- canonical ordering;
- dependency-aware local execution;
- resume skips completed work.

Tests:

- finish order 3,1,4,2;
- one slow section;
- one repair section;
- one failed section;
- resume after two complete;
- concurrency never exceeds 4.

Pass:

- output order remains 1,2,3,4 and completed work is not regenerated.

## Gate 7 — Mechanical assembly and persistence

Actions:

- no generation during assembly;
- exact expected-key reconciliation;
- answer merge;
- document validation;
- persistence;
- reload and validation.

Tests:

- all-forms expected document;
- duplicate block;
- missing block;
- invalid order metadata;
- invalid answer reference;
- round trip equality/canonical hash.

Pass:

- valid document persists and reloads; invalid assembly gives exact cause.

## Gate 8 — Native status and frontend behavior

Actions:

- native status projection;
- non-null structured errors;
- polling termination;
- recoverable retry UI;
- teacher/student render differences.

Tests:

- status at each stage;
- recoverable failure;
- terminal programming failure;
- ready document;
- frontend polling stops;
- answer key visibility rules.

Pass:

- no null terminal error and no infinite polling.

## Gate 9 — Mocked full end-to-end run

Use the supplied all-forms fixture.

Required outputs:

- generated document JSON;
- persisted and reloaded JSON;
- student render;
- teacher render;
- student PDF;
- teacher PDF;
- status timeline;
- test report.

Pass:

- complete mocked flow produces all outputs and all mock scenario tests pass.

## Gate 10 — Real LLM smoke run

Actions:

- run one small lesson through the same production path;
- no bypasses;
- capture raw provider outputs safely;
- capture repair evidence if needed.

Pass A:

- valid document, renders, PDFs.

Pass B, controlled provider issue:

- exact invalid provider output classification;
- repair attempted;
- recoverable failure surfaced;
- no unexplained application failure.

Any application crash, null error, stuck state, invalid persistence, or legacy routing is a failed gate.

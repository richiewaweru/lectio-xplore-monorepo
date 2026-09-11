# Phase Sequence

```text
A  Externalize generation specs/policies
│
B  Fix learner-action planning + validation
│
C  Twin Learn/Print task realization
│
D  Complete Print shared-writer cutover
│
E  Add symmetric realize-print handoff
│
F  Fix figure serving + preserve section structure
│
G  Natural live Learn interactions + tabs/navigation
│
H  Native Print artifact editor
│
I  Full acceptance + UI refinement
```

## Phase A — Externalize generation specs/policies

Tasks:
- register composer/writer in canonical prompt manifest;
- add learner-action, interaction-selection, interaction-writer, figure-authoring and Print-realization specs;
- add policy YAMLs;
- remove mutable LLM-facing guidance from Python where practical;
- preserve code-level schemas/invariants.

Gate:
- changing learner-action or figure-authoring behavior requires Markdown/YAML only;
- effective production prompt comes from canonical loader;
- prompt version/hash changes when default changes.

## Phase B — Learner-action planning

Tasks:
- feed learner-action policy into Teaching Plan generation;
- broaden actions beyond formal assessment;
- make evidence-bearing check/practice blocks intentionally reason about learner action;
- validate pathological missing-action outputs while preserving legitimate passive blocks.

Gate:
- at least two fresh real Teaching Plans;
- at least one naturally emits an action before/during instruction;
- at least one naturally emits a check/practice action;
- no native Learn/Print ids appear in Teaching Plan.

## Phase C — Twin task realization

Tasks:
- load Learn/Print action maps from policy;
- same learner action drives both path realizations;
- stop Print from inventing unrelated response surfaces from intent alone, except explicitly documented approved-item semantics.

Gate:
- `select-one` → Learn `choice` and Print `choices` from same plan;
- `classify-items` → Learn classification and paper-appropriate response;
- no action → no unexplained task divergence.

## Phase D — Print shared writer cutover

Tasks:
- live Print ordinary content calls shared `document.writer`;
- Print maps authored nodes to page objects;
- Print-only treatment/layout remains downstream;
- remove competing ordinary writing path.

Gate:
- live Unit Print trace proves shared writer calls;
- valid LectioDocument/PDF;
- no ordinary prose/table/callout content is re-authored by legacy page-object writers.

## Phase E — Symmetric realize-print

Tasks:
- add Print handoff matching Learn conceptually;
- Unit UI explicitly realizes Print from approved Teaching Plan;
- Studio opens/edits artifact after admission;
- retry/status remain realization-scoped.

Gate:
- Learn-only creates only Learn;
- Print-only creates only Print;
- sibling can be generated later from same plan;
- no re-approval/stale-revision workaround.

## Phase F — Assets + section structure

Tasks:
- one configured absolute image-store root;
- fix Learn figure URLs;
- preserve section id/order/title/transition in LearnDocument;
- support section-local targeting.

Gate:
- generated figure browser request returns 200;
- process CWD does not alter image serving;
- final LearnDocument can group nodes by section without reopening Teaching Plan.

## Phase G — Natural live Learn interactivity + tabs

Tasks:
- tab/navigation UI from realized section metadata;
- fresh Unit whose planner naturally emits learner actions;
- real interactions render, submit, evaluate and persist;
- edit/add/delete/reorder/save/reload remains working.

Gate:
- no hand-injected actions;
- at least two naturally generated interaction types across live Unit proofs;
- response/evaluation follows actual runtime/persistence path.

## Phase H — Native Print artifact editor

Tasks:
- edit LectioDocument v2, not LearnDocument;
- view/edit mode in native Print workspace;
- practical edits: prose, lists, table cells, callouts, figure metadata/asset, questions/options, response-space settings where supported;
- validate on save;
- optimistic revision control;
- rerender/reflow PDF.

Gate:
- edit live artifact;
- save/reload persists;
- PDF reflects edit;
- invalid edit rejected;
- stale edit returns 409;
- Learn sibling unchanged.

## Phase I — Final acceptance + UI refinement

Only after A–H pass:
- spacing/navigation/loading/error states;
- interaction visual polish;
- Learn tab polish;
- Print editing affordances;
- remove dead routes/helpers found in final call graph.

Gate: `verification/FINAL_ACCEPTANCE_MATRIX.md` has no failed critical item.

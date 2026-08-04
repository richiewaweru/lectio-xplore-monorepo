# G. Phasing Plan — Direct Page-Object Cutover

## Principle

Answer the highest-risk and cheapest question first: whether the new intent/object vocabulary preserves planning quality.

Each phase is one commit and independently verifiable.

The experimental branches are disposable. Production remains untouched until the comparative gate is passed.

## Progress meters

Track at every commit:

```text
intent catalogue count
object catalogue count
v2 selector count
v2 print rule count
legacy print-theme.css line count remaining in v2 path
number of v2 imports from legacy Lectio
number of section_field references in v2 path
number of component_id references in v2 path
planner rubric score
PDF page count for fixed fixtures
render defects
```

Targets:

- intents: 28–35 initially;
- objects: 10 unless evidence forces a change;
- legacy imports in v2: 0;
- `section_field` in v2: 0;
- `component_id` in v2 resource path: 0;
- boxes outside aside: 0;
- component-name labels printed: 0.

The new base stylesheet should remain small. The legacy stylesheet does not literally shrink because this is a fresh repository; instead track v2 rule count. If v2 rules grow to undo screen styling, stop.

## Phase 0 — Baseline capture

**Commit:** `chore: capture component-path comparison baseline`

Deliver:

- three fixed generation inputs;
- raw current plans;
- raw current generated JSON;
- student and teacher PDFs;
- page counts;
- defect inventory;
- current planner palette snapshot;
- current print stylesheet metrics.

Binary done:

- all baseline artifacts are reproducible;
- PDFs open;
- defects have page references;
- no production code changed.

## Phase 1 — Intent and object contract validation

**Commit:** `feat: define and validate v2 planning vocabulary`

Deliver:

- 10-object catalogue;
- 32-intent catalogue;
- compatibility matrix;
- hand-assembled v2 planner palette;
- comparison harness;
- three candidate planner runs;
- rubric report.

Binary done:

- schema loads;
- all intents have role, cognitive job, valid objects and guidance;
- planner score ≥16/20;
- no catastrophic output <12/20;
- candidate equals or beats control on cognitive progression;
- no renderer code exists yet.

Stop rule:

If the planner becomes bland, revise the catalogue before continuing.

## Phase 2 — Fresh Lectio v2 package scaffold

**Commit:** `chore: scaffold fresh print-native lectio package`

Deliver:

- package build;
- public exports;
- contract export script;
- JSON schemas;
- fixture route;
- zero legacy imports.

Binary done:

- package builds;
- package installs beside legacy Lectio;
- contract export hashes are deterministic;
- empty document validates;
- old documents still render through old package.

## Phase 3 — Geometry and base print proof

**Commit:** `feat: establish scholar-margin print geometry`

Deliver:

- root document shell;
- base print stylesheet;
- float margin implementation;
- language propagation;
- Playwright PDF test;
- pagination fixtures.

Binary done:

- float margin passes;
- grid implementation absent;
- table header repeats;
- figure and caption stay together;
- widows/orphans fixture passes;
- hanging numbers pass;
- no `!important`;
- no card styles.

## Phase 4 — First five objects

**Commit:** `feat: render core document objects`

Implement:

- heading;
- prose;
- list;
- figure;
- aside.

Binary done:

- heading binds to first following block;
- prose splits correctly;
- list items behave;
- full-span figure works;
- adjacent margin asides do not collide;
- no boxes outside aside.

## Phase 5 — Remaining five objects

**Commit:** `feat: render instructional and assessment objects`

Implement:

- table;
- worked-example;
- questions;
- choices;
- answer-key.

Binary done:

- table headers repeat;
- worked example splits between steps;
- answer remains with final step;
- questions never split internally;
- choices print letters only;
- answer key can be suppressed from student edition.

## Phase 6 — V2 planner and blueprint models

**Commit:** `feat: plan document moves instead of components`

Deliver:

- v2 planner palette loader;
- `PlannedDocumentMove`;
- skeletons expressed as pedagogical moves;
- object-intent validation;
- v2 blueprint output.

Binary done:

- one real topic plans;
- positions present;
- repeated object types present when appropriate;
- no component ID or section field in v2 blueprint;
- existing path, group, schedule and deviation tests remain green.

## Phase 7 — Writer contract and block events

**Commit:** `feat: emit ordered document blocks`

Deliver:

- writer work-order change;
- object schema resolver;
- block discriminated union;
- `block_ready` event;
- writer prompt update.

Binary done:

- one section produces valid blocks;
- intent and object remain separate;
- no styling in generated content;
- duplicate object types validate;
- event replay is idempotent.

## Phase 8 — Ordered document merge

**Commit:** `feat: preserve generated block order in v2 snapshots`

Deliver:

- v2 merge implementation;
- ordered section arrays;
- position-collision diagnostics;
- resume/replay test.

Binary done:

- `position` survives;
- two prose blocks survive;
- two figures survive;
- replay does not duplicate;
- resume preserves order;
- no assignment by section field exists.

## Phase 9 — Visual and question integration

**Commit:** `feat: resolve figures and answer keys inside v2 documents`

Deliver:

- figure placeholders;
- visual resolution by block ID;
- question blocks;
- document-level answer key.

Binary done:

- asynchronous visual result updates correct figure;
- failed image leaves an honest printable fallback;
- answer-key references validate;
- student edition omits answer key.

## Phase 10 — Direct frontend consumption

**Commit:** `feat: render v2 documents directly in studio and print`

Deliver:

- v2 API type;
- direct Lectio v2 renderer;
- review wrapper;
- v2 print route;
- version routing.

Binary done:

- no v2 import of `SectionContent`;
- no v2 pack adapter;
- no editor chrome in PDF;
- v1 still renders through legacy path;
- v2 renders through new package.

## Phase 11 — QC and comparative run

**Commit:** `test: compare page-object and component booklet paths`

Deliver:

- contract QC;
- instructional QC;
- document QC;
- render QC;
- before/after PDFs;
- rubric report;
- page-count report;
- defect report.

Binary done:

- same inputs processed by both paths;
- reviewers score blindly where possible;
- all critical print defects counted;
- new path shows no component labels or builder chrome;
- decision memo written.

## Phase 12 — Decision, not automatic rollout

**Commit:** `docs: record page-object experiment decision`

Possible decisions:

### Accept

Proceed to hardening and make v2 default for new documents.

### Revise

Change object taxonomy, intent catalogue, or composition rules and rerun selected phases.

### Reject

Archive the branch. Preserve findings. Do not force migration because work was invested.

## Acceptance target for the whole experiment

- planner quality maintained or improved;
- print readability clearly improved;
- page count reduced where old pages were structurally wasteful;
- no loss of teacher ordering;
- no loss of repeated blocks;
- no builder chrome in student PDF;
- no boxes outside aside;
- no legacy component dependency in v2;
- Chromium defects are isolated and understood;
- generation reliability remains acceptable.

## Estimated effort

- vocabulary validation: 2–4 days;
- Lectio package and renderer: 5–10 days;
- backend rewiring: 5–8 days;
- frontend and print integration: 3–5 days;
- comparative testing and revision: 4–8 days.

Realistic focused range: 3–5 weeks.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** A–F

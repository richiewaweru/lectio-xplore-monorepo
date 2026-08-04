# Architecture Authority

## 1. Mission

Repurpose `xplore` so the application natively produces page-oriented Lectio documents. The page-object contract is not a final rendering adapter. It is the application’s committed document representation for v2 generations.

The minimum successful product path is:

```text
approved objective and concept card
        ↓
resource + skeleton constraints
        ↓
ordered page-block planning
        ↓
object-specific writing
        ↓
LectioDocumentV2 persistence
        ↓
Lectio semantic and structural validation
        ↓
teacher/student rendering
        ↓
A4 PDF
```

## 2. Non-negotiable product invariants

### 2.1 The wall

Question content is generated from the approved concept card and item context only. Surrounding lesson prose, block briefs, object writers, visual descriptions, and neighbouring blocks must never become item-generation inputs.

A block planner may decide where questions appear and which pre-generated question IDs belong there. It may not draft question text.

### 2.2 One variable per variant

Differentiated variants may change exactly one declared axis. Page-object planning must not quietly introduce a second audience difference through object choice, content omission, question difficulty, or visual density.

### 2.3 No pedagogical count targets

No phase may add arbitrary caps such as “one worked example per lesson” or “two key ideas maximum” as quality rules. Counts are allowed only when they come from:

- a physical page capacity;
- a schema minimum required to make an object valid;
- an approved skeleton shape;
- an explicit teacher-selected depth contract.

### 2.4 Misconceptions are evidence, not quota

A lesson may have zero to three real misconceptions. No planner or writer may manufacture one to justify a `diagnose-misconception`, `warn`, `choices`, or question block.

### 2.5 Lesson-first

The first native resource is a lesson. Other resources are projections or companions of prepared lessons unless a later authority document deliberately changes this.

### 2.6 Lectio holds no audience policy

Lectio owns document shape, page-object contracts, compatibility, physical capacity, semantic validation, normalization, rendering, and print CSS.

Xplore owns resource identity, prior knowledge, lesson mode, educational sequencing, visibility, differentiation, and what the learner is expected to do.

### 2.7 Ordered arrays are authoritative

For v2, array order is document order. `position` must equal the block’s array index after normalization. No sidecar order, field-order constant, template ladder, or projection may independently reorder blocks.

### 2.8 No lossy wide record in the v2 path

The new path must not construct the old one-field-per-component `SectionContent` record and then translate it into page objects. A temporary test helper may map the same source content into both representations, but production v2 generation must build `LectioDocumentV2` directly.

## 3. Settled architecture decisions

1. **One section-level block-planning call for v1 of the integration.** It chooses ordered intent/object pairs together while exposing its evidence. Deterministic code validates every pair. The two-call intent/object barrier remains a later experiment.
2. **Resource identity is prompt context, not a `StanceSpec` domain model.** Build it from existing spec fields plus runtime lesson context.
3. **`PlannedBlock` is additive.** Legacy component fields remain while v1 documents still run.
4. **Headings:** document title is h1; `section.title` renders automatically as the section-level heading; generated planners do not emit heading blocks in the first slice. The `heading` object remains available later for nested structural subheadings and has no pedagogical intent.
5. **First-slice objects:** prose, list, table, worked-example, questions, figure. Aside, choices, nested heading, and answer-key rendering are follow-on work unless required to make the first fixture honest.
6. **First-slice scope:** lesson resource, core variant, first-exposure conceptual lesson. Do not generalize before this path prints.
7. **Canonical contract synchronization:** the page package remains the source of truth. The backend consumes committed generated snapshots produced by a reproducible sync script, not a fragile runtime relative path.
8. **v1/v2 coexistence:** old documents render through old Lectio; v2 documents render through `@lectio/page`. No bulk migration and no compatibility adapter as primary production logic.
9. **Figures own position before assets are ready.** A pending figure block is a complete document block with stable identity and placement.
10. **Writer cannot change plan.** Object writers fill the assigned content schema. They cannot switch object or intent.

## 4. First proof

The first proof must be created by the real Xplore preparation/generation path, persisted, reloaded, rendered in the application, and printed by Playwright.

A hand-authored library fixture is a contract smoke test, not proof of Xplore integration.

## 5. Explicitly prohibited shortcuts

- Reintroducing component slugs as hidden page-object identifiers.
- Mapping every legacy component to one new object and calling that native generation.
- Selecting object from its name rather than catalogue tests.
- Letting object writers receive the full list of alternative objects.
- Generating question text from block context.
- Reordering blocks inside the frontend.
- Adding a second renderer-owned ordering system.
- Deleting the legacy path before v2 has a green rollback gate.
- Renaming `generation/v3_studio` during the first vertical slice merely for cleanliness.
- Removing a failing test instead of recording and resolving its contract conflict.
- Letting Cursor invent a missing product decision during unattended execution.

## 6. Scope-change protocol

When implementation evidence contradicts this authority:

1. stop the affected run;
2. write `docs/implementation-runs/BLOCKER-<phase>-<slug>.md`;
3. include the exact file, symbols, current behavior, proposed alternatives, and consequences;
4. continue only with independent tasks that do not assume an answer;
5. do not silently reinterpret the architecture.

## 7. Success condition

The authority is fulfilled when an approved first-exposure conceptual lesson can complete this path without any legacy section-content construction:

```text
prepare → plan blocks → write blocks → assemble v2 → persist → reload → render → PDF
```

and the same deployment can still open an existing v1 document.

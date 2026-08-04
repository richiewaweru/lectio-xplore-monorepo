> HISTORICAL INPUT — NOT IMPLEMENTATION AUTHORITY

# Context Handoff — Page-Object Rewrite, Reasoning Trail

**For:** an agent asked to review this work and offer an independent view
**Date:** 2026-08-04
**Status:** design complete, first implementation phase queued for overnight autonomous work

---

## What you are being asked to do

Read the trail. Then tell us where it is wrong.

Not "here are some risks" — specific disagreements with specific decisions,
grounded in what the reasoning actually was rather than in general principles
about document models or prompt design.

The most useful thing you can do is find a decision that was made for a good
reason that no longer applies, or a piece of evidence that was over-read.

---

## 1. The product

A textbook generator for CBC-aligned lesson authoring, sold to Kenyan schools.
Solo founder, former middle-school teacher, now full-stack. Operating at
concierge scale, no funding raised.

The thesis: AI made explanations free, but explanations were never the
bottleneck. Unstructured content cannot be measured. The industry optimised for
engagement proxies — completion, streaks — because learning is slow to measure.

Two systems exist. A textbook generator (FastAPI / LangGraph / SvelteKit /
DeepSeek / Postgres) and a separate AI tutor. The active work is the `xplore`
branch of the generator.

**Named principles the founder holds and enforces.** These come up repeatedly
and several decisions below were reversed because they violated one:

- **The wall** — quiz items are generated from concept cards only, never from
  surrounding content. Enforced structurally.
- **One variable per variant** — differentiated renderings vary on exactly one
  declared axis. Makes the differentiation claim falsifiable.
- **Count targets are harmful inputs** — a count target caused the planner to
  silently drop prerequisites rather than be economical. Both count and
  duration targets were removed as planner inputs.
- **Misconceptions without quota** — zero to three real ones, never manufactured
  to reach a number.
- **Lesson-first** — resources are projections of prepared lessons, not primary
  outputs.
- **Lectio holds no audience policy** — the component library renders what it is
  handed; the consumer decides visibility.

---

## 2. The trigger

A review brief proposed replacing Lectio's component-first document model with a
page-object-first one. Ten physical objects, thirty-plus pedagogical intents.
The stated reason: *the printed booklet is the product, and the component-first
model has repeatedly failed to produce consistently strong printed documents.*

The brief asked for a review against the actual `xplore` code, with an explicit
instruction not to protect the proposal from criticism.

---

## 3. What the code review found

The `xplore` branch was cloned at `a1f0a62`, and `lectio@0.6.0` — the version the
frontend pins — was pulled from npm and unpacked.

### The headline finding

Block order is decided in three places, and the three disagree.

```
   PLANNER                 BUILDER                    PRINT / PDF
   position                BLOCK_FIELD_ORDER          {#if} ladder
   (int per block)         (33-entry const)           (source order)
        |                        |                          |
   section_builder          lectio/dist/teacher/       lectio/dist/templates/
   sorts by it ...          document.js:17             guided-concept-path/
        |                        |                     layout.svelte
   ... then discards it          |                          |
   into a sidecar                |                          |
   `_component_order`            |                          |
        |                        |                          |
   read by ONE                read by the               READ BY THE
   Svelte canvas              builder only              ACTUAL PRODUCT
   component
```

`layout.svelte` renders `callout` and `key_fact` **before** `explanation` and
`definition`. `BLOCK_FIELD_ORDER` does the reverse. The planner's `position`
agrees with neither and never reaches print.

The brief claimed `position` is discarded at the merge. It is discarded three
times, and print never had it. This is stronger evidence for the change than the
brief itself made.

### Other findings

- **The brief targeted the wrong planner.** Two structural planners exist. The
  brief's "planner palette builder" (`_planner_index_block`) belongs to a
  free-generation path. The product path selects components via
  `slot.allowed_components` in `skeletons.yaml` plus a `component_selector`
  agent.
- **Skeletons carry component IDs.** `preferred:` / `allowed:` lists per slot.
  The brief assumed skeletons were pedagogy-only.
- **Projections read hardcoded field names.** `planning/projections.py`
  `_revision_sections` iterates `("definition", "key_fact", "comparison_grid",
  "pitfall", "worked_example", ...)`. That is the product layer reaching into
  the storage representation. The brief listed projections as unchanged.
- **Visuals have no position.** `attaches_to` is a section id; placement is by
  mode. The brief listed the visual pipeline as unchanged. It cannot be.
- **Questions are conditionally dropped.** `PRACTICE_BUCKET_COMPONENTS =
  {"practice-stack"}` — generated questions become a warning unless that
  specific component was planned.
- **`document_version` is taken.** Already means a poll-cache hash.

### The reframing

Lectio already has two document models. `LessonDocument` (used by the builder)
is ordered blocks with positions. `SectionContent` (used by the renderer) is a
wide record with one field per component. The builder round-trips through the
wide record and back out.

So the honest framing is not *replace the component model with an object model*.
It is: **the wide record is a lossy layer between a planner with real intent and
two consumers that both need order, and one of Lectio's own models is already
the better one.**

**Verdict given:** PROCEED FROM XPLORE, with two corrections — the change
surface is ~40% larger than the brief estimated, and the renderer is not
downstream of the experiment, it *is* the experiment.

---

## 4. The new library

`lectio-pageobject` was built. Ten objects, thirty-two intents, an ordered
document contract with `{id, position, object, intent, content}`, and a fixture
render pipeline (`pnpm pdf:fixture` → Playwright → A4).

Initial catalogue shape:

```
INTENT                          OBJECT
teacher_label                   holds
pedagogical_role                content_schema
cognitive_job                   placement
valid_objects                   fragmentation
generation_guidance             emphasis
                                screen_layer
```

`isCompatible(object, intent)` gates on `valid_objects`. `heading` returns false
against everything — structural, `intent: undefined`.

---

## 5. The catalogue audit

Question asked: can an LLM actually reason over this?

**Finding: no, not as shipped.** Descriptions in isolation do not discriminate.
`pedagogical_role` tells you what an intent is; nothing tells you why it beats
its neighbour. `explain` / `explain-cause` / `trace-flow` / `show-structure` are
indistinguishable from their descriptions alone.

**A wrong estimate, corrected.** The first pass claimed nine clusters and ~9
intents needing disambiguation. The audit found **31 of 32** — the clusters
chain, because `prose` appears in 18 intents' `valid_objects` and `questions` in
14. Any two intents sharing an object can appear in the same candidate list.

**Fields added:**

| Field | On | Why |
|---|---|---|
| `choose_when` | intents | a testable condition, not a description |
| `not_when` | intents | keyed by cluster-mate: when the neighbour is better |
| `earns_its_place_when` | objects | prose is in 18 intents' valid_objects; without a positive test the selector defaults to prose every time |
| `reject_when` | objects | counter-test, makes the choice binary |
| `capacity` | objects | **a regression being fixed** — old component cards had `capacity`; the object catalogue dropped it |
| `selectable` | intents | `answer-key` is never chosen by the selector |

**On `capacity`:** without numbers, `aside` has no length bound, and an aside
that overflows the 56mm margin column breaks the float layout — the exact print
failure the rewrite exists to fix. The bound was derived, not guessed: 56mm at
~9.5pt/13pt ≈ 6 words per line, seven lines before it drags past its anchor,
≈ 40 words.

**A field rejected:** `evidence_signal` (verb lists per intent, mirroring
`verb_signals` in `skeletons.yaml`). Dropped — it duplicates `choose_when`, and a
verb list invites keyword-matching, which is the failure mode being designed
against.

**Shipped:** `catalogue_version 1.1.0`, 11 intents with `choose_when`/`not_when`,
8 objects with all three fields, `answer-key` marked non-selectable.

---

## 6. The reversal that matters most

A `density` field was proposed on nine intents — `emphasise: "at most one per
lesson"`, with planner-side resolution by re-selection and a QC assertion.

**The founder rejected it:**

> "if the reason for picking was valid then let us allow them instead of forcing
> it not to otherwise. we will deal with it once we see that is an issue but for
> now let us trust the prompts and lesson specs we will write will be truthful to
> always pick the best candidate for job."

**This was correct and the original proposal was wrong.** "Two key ideas is zero
key ideas" was asserted as fact. It is a claim about a reader, made without
having seen the output. And it was a count target dressed as a quality rule —
the exact mechanism the founder had already removed from the planner.

**What replaced it:** restraint moved into `choose_when` as a condition the model
evaluates rather than a number it obeys.

```
BEFORE
  choose_when: "The learner has not yet seen the method carried out
                end to end on a real instance."
  density: "At most one per lesson."

AFTER
  choose_when: "The learner has not yet seen the method carried out end to
                end on a real instance. If the learner has already seen it
                worked through in this lesson, this condition is no longer
                met."
```

The second `demonstrate` slot now self-excludes on evidence. Better design than
the cap, arrived at by being overruled.

**The one count that survived:** `aside.capacity.maxPerSection: 2`. Not pedagogy
— three floated asides in a 56mm column collide. It replaced a hardcoded
`asideCount > 2` in `validation.ts`.

---

## 7. Two-layer narrowing

The founder proposed that resource specs declare which vocabulary is in scope,
so the model never reasons over things outside the spec.

This was accepted and it is stronger than it first appears, because the two
filters are orthogonal.

```
RESOURCE SPEC                    SKELETON SLOT
per resource_type                per knowledge_type × lesson_mode
"what a worksheet IS"            "what this moment NEEDS"
       │                                  │
       └──────────────┬───────────────────┘
                      ▼
              INTERSECTION  →  2-5 intents
                      │
              empty = config error,
              caught at load time
```

**Three consequences:**

1. **Projections become a filter.** `_revision_sections`'s hardcoded field names
   become `filter(blocks, intent in spec.intents)`. `ROLE_FILTERS` dies. Days of
   work become an afternoon.
2. **Specs become a product surface.** `excluded` carries reasons, not just a
   list. A teacher can read what a worksheet is.
3. **The `not_when` set becomes computable.** Which pairs actually co-occur is
   determined by config, so it can be derived rather than estimated. A CI test
   was specified to do exactly that — and to overrule the earlier hand-picked
   list of 11.

**Strict scoping was chosen.** The model sees only the intersection. Never the
full 32, never a "do not use these" list. `not_when` clauses referencing
out-of-scope neighbours keep the clause text and drop the intent name — naming an
unpickable intent is noise and invites hallucination.

**Escape hatch:** if nothing fits, the model emits `slot_concern` rather than
picking the least-bad option. That signal is evidence a spec is too narrow,
raised by a real lesson rather than guessed in advance.

---

## 8. Another correction: the worked example

The proposal excluded the `worked-example` **object** from worksheets, citing
the existing spec rule *"worksheet must not re-explain the concept."*

Wrong object. The correction:

```
worked-example OBJECT  +  demonstrate INTENT       → re-teaching.  Excluded.
worked-example OBJECT  +  practise-guided INTENT   → scaffolding.  Allowed.
```

Same form on the page, different teaching job. Under the old component model
this would have needed two components. This is the first concrete evidence the
two-catalogue split earns its complexity.

A related call: v1 globally forbade `pitfall-alert` in worksheets — *"belongs in
the teaching resource, not practice."* Right about the component, wrong about
the job. `warn` + `prose` is "convert both to the same unit before you compare",
which is what a teacher says walking between desks. The worksheet excludes the
`aside` object, so `warn` resolves to prose. The box is gone; the reminder stays.

---

## 9. Decisions settled

| | |
|---|---|
| Monorepo | `apps/textbook` + `packages/lectio-page`, workspace-linked. Publish when the API stabilises. |
| Coexistence | v1 documents keep the old renderer. v2 generated directly. No adapter, no migration. Safe because the wide record is opaque JSON. |
| Base branch | `xplore`. Nothing patched first — the known beta gaps sit in the item path, untouched by this. |
| Catalogue split | intent = pedagogy, object = paper. Nothing owns both. |
| Narrowing | spec × skeleton intersection, strict, closed set. |
| Decision order | intent (objects hidden) → brief → object (brief visible) → planner assigns position. |
| Position | assigned by the planner — the only node that sees the whole section. |
| Headings | renderer-generated from `section.title`. Costs the h3 tier. Buys: title and heading cannot disagree, and the `break-inside: avoid` wrapper is applied once at a known position instead of hand-managed. Additive to turn on later. |
| `answer-key` | `selectable: false`, `produces_answer_key: true` on the spec. |
| Free-generation path | deleted. |
| `generation/v3_studio/` | **not** deleted — it is the shared runtime, imported by 13 files. Renamed to `runtime/`. |

---

## 10. The last gap found

The founder flagged that the specs declare vocabulary but never say what the
resource *is*:

> "a lesson is different from a worksheet and so it needs be in prompt to align
> the model with the resource it is producing."

**Two failures stacked.** The selector prompts never mentioned the resource at
all — slot purpose, candidates, objective, misconceptions, nothing saying "this
is a worksheet." And the existing `intent:` prose is written for a human; read as
a block-level decision rule it evaporates, because the exclusion list already
encodes "no teaching."

**Fix:** a `stance` block — four fields, each a test rather than a description.

```yaml
stance:
  student_arrives_with: ...      # what the reader already holds
  page_is_spent_on: ...          # what the page budget buys
  reader_is: reading|writing|checking|revising
  fails_by: ...                  # the characteristic failure of this type
```

`fails_by` outranks `choose_when` — a rejection test, not a warning.
`reader_is` does the quiet work: `reading` vs `writing` changes block length,
prose density, and whether a table is a reference or something to fill in,
across every intent without naming any.

Rendered at the **top** of both selector prompts, with `label` and `id` verbatim
so the model can name what it is producing.

One test exists specifically because of how this bug happened:
`test_stance_renders_into_prompts` asserts identity reaches the prompt string,
not just the YAML. A test checking only the spec file would have passed the whole
time the selectors were flying blind.

---

## 11. Where it stands

**Shipped:** `lectio-pageobject` catalogue v1.1.0 (commit `14ca43b`).

**Queued for overnight autonomous work:** monorepo setup, delete the
free-generation path, rename the runtime, catalogue bridge to Python, spec schema
v2, `resolve_candidates`, skeleton and two spec migrations, both selector prompt
files, coverage tests, `PlannedBlock` model, and a dry-run harness that runs the
selectors from a command line with no pipeline and no LLM spend.

**Two kill switches before any large commitment:**

1. **Renderer proof.** Hand-author one real pack as a v2 document, print it
   against the current PDF, put both on a desk. If it is not clearly better, the
   document model was never the problem. Two days.
2. **Selector test.** Ten real slots, read the `(intent, evidence, brief)`
   triples. If evidence restates the slot purpose, `not_when` is too thin. If
   eight objects come back prose, `earns_its_place_when` is too soft.

**Not started:** writer prompt, `section_builder`, `block_ready` events,
projections, visual pipeline, QC replacement, frontend, the remaining 21
catalogue records.

---

## 12. Corrections made along the way

Kept deliberately, because they are where the reasoning actually moved:

| Claim | Correction |
|---|---|
| 22 of 31 intents need no `not_when` | 31 of 32 do — the clusters chain through shared `valid_objects` |
| `density` is a quality rule | it is a count target; the founder caught it |
| exclude `worked-example` from worksheets | wrong object — the `demonstrate` intent is what re-teaches |
| run the selector test in the library | no selector exists there; it is a rendering package |
| delete the v3 Studio path | it is the shared runtime, not a path — 13 files import it |
| 8 high-risk intent pairs | derived from four clusters by eye; a CI test now computes the real set |

---

## 13. Where an outside view would be most useful

Ranked by how much a wrong answer would cost.

**1. Is the renderer proof actually decisive?**
The whole plan rests on: hand-author one document, print it, and judge. If the
first v2 print is better for reasons unrelated to the document model — better
CSS, more care taken because it was hand-authored — the test confirms the wrong
hypothesis. Is there a version of this test that isolates the model from the
craft?

**2. Are ten objects and thirty-two intents the right factorisation?**
The split is object = paper, intent = pedagogy. Some cases sit awkwardly:
`answer-key` is both an object and an intent; `heading` is an object with no
intent; `figure` is an object whose content comes from a separate generation
pipeline. Is the seam in the right place?

**3. Is `not_when` the right mechanism?**
It is a hand-written boundary between neighbours, and it scales as O(pairs). The
CI test computes which pairs are needed, but somebody writes each clause. An
alternative — worked examples per cluster, showing a decision rather than stating
a boundary — was considered and not chosen. Was that right?

**4. Is two LLM calls per block correct?**
The information barrier between intent and object is enforced by making them
separate calls. That doubles cost per slot. The alternative — one call with a
strict two-phase output — leaks, because the model knows what is coming. Is the
barrier worth the money, and is there a cheaper way to enforce it?

**5. Is strict scoping over-constraining?**
The model sees only the spec × skeleton intersection, typically 2–5 intents. The
escape hatch is `slot_concern`. Does closing the world this tightly lose good
choices that a wider view would have found, and is `slot_concern` a sufficient
release valve?

**6. Has anything been over-read from the three-orderings finding?**
It is the strongest evidence for the change and it is being used to justify
6–8 weeks of work. It proves the planner's order never reached print. It does
not by itself prove that fixing the order fixes print quality. Is that gap being
papered over?

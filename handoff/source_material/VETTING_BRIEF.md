# Vetting Brief — Concept-Path Restructure of a Lesson Generation Platform

## How to use this document

You are being asked to **critique a design, not implement it**. Everything below
has already been argued through once; what is needed now is adversarial review
before roughly six weeks of work is committed.

Please prioritise in this order:

1. Find the decision that is **hardest to reverse** and check whether it is right.
2. Find the claim that is **asserted but not evidenced**.
3. Find the failure mode that is **silent** — produces plausible output, no error.
4. Only then comment on sequencing, naming, or ergonomics.

Section 6 lists the specific arguments we are least confident about. If you only
have attention for one section, use that one.

Do not soften. If the core premise is wrong, say so plainly.

---

## Part 1 — The system as it exists today

All facts in this section were verified by reading the repository. They are not
recollections.

### Stack and shape

FastAPI + Postgres backend, SvelteKit frontend, DeepSeek for generation
(Anthropic for one visual-QC slot), Lectio as a versioned rendering contract
package. Modular monolith. Currently on branch `xplore`, 20 commits ahead of `v3`.

### What it does

A teacher describes a topic and context. The system:

1. Narrows the topic, then runs a **structural planner** (one LLM call) that
   produces a `StructuralPlan`: lesson mode, anchor, prior knowledge, an ordered
   list of up to 6 sections, concept cards, question placement, answer-key style.
2. Halts at `awaiting_review` — durable across process restart — for the teacher
   to review and edit the concept cards.
3. On approval, generates **one shared set of 5 multiple-choice items per card**,
   then fans out **variant booklets** (up to 3 learner groups) concurrently.
4. QC checks each generated card section, repairs failures, renders print.

### Structures worth knowing

```
ConceptCard      id, title, objective, prereqs, misconceptions[],
                 no_known_misconceptions, opens_by
Misconception    id, description, source(drafted|teacher)
VariantSpec      label, voice(register, tone, notation), group_description
StructuralPlan   lesson_mode, lesson_intent, anchor, prior_knowledge,
                 cards[], sections[], repair_focus, answer_key_style
SectionPlan      id, title, role, card_id|null, visual_required, transition_note
```

### Properties that already hold (do not propose changes that break these)

- **The item wall.** Item generation receives one `ConceptCard` and three scalars
  (subject, level, notation) via private attributes. It cannot import section,
  component, or generated-content types — enforced by test, not by prompt.
  Items therefore cannot test recall of the prose that teaches them.
- **Items are pack-owned**, not variant-owned. Every learner group gets the same
  quiz. This is what makes group comparison possible at all.
- **QC verdicts are derived, not asserted.** A validator recomputes pass/repair
  from the individual checks and raises if the model's stated verdict disagrees.
  It also requires one check per declared misconception id.
- **Distractors may be tagged `null`.** The model is instructed not to stretch a
  misconception id onto a distractor that does not fit. A live run produced 5
  untagged distractors, surfaced for human review rather than force-mapped.
- **Sibling variant failure does not block siblings.**
- **Teacher edits survive regeneration** via preserve-and-flag.
- **`awaiting_review` survives process restart** — verified by running approval
  from a second process with no in-memory state.

### Defects found while preparing this brief

These are real and currently unaddressed:

1. **Role validation is dead code.** `_allowed_roles_from_resource_spec()` reads
   `required_roles` / `optional_roles` / `sections[].role` from the active
   resource spec. The active spec (`guided-concept-path.json`) contains none of
   those keys — only `available_components`, `component_budget`,
   `max_per_section`. The allowed-roles set is therefore always empty and the
   validation is skipped. Meanwhile the planner prompt instructs the model to
   "emit role using the exact role strings allowed by the active resource spec"
   and to "choose components only from that role's preferred or allowed set."
   Neither exists. **Section roles are unvalidated free text invented per call.**

2. **Component descriptions never reach the planner.** All 30 components in the
   registry carry a distinct `cognitive_job` string ("Create felt need",
   "Inoculate against error", "Watch reasoning in action", etc.). These are
   passed to the section *writer*. The *planner* — the component that chooses
   which components to use — does not receive them.

3. **`StructuralPlan` was relaxed to `extra="ignore"`** to tolerate a legacy
   field during the last refactor. The strictest contract in the system now
   silently accepts unknown keys.

4. **`max_six_sections` is hard-enforced** on `StructuralPlan`. Any proposal
   producing more than six sections is invalid.

---

## Part 2 — What is being proposed

### The core problem

Two distinct failures, both traced to the same cause.

**Overload.** The single planning call makes roughly nine independent decisions
at once: lesson mode, anchor, objectives, prerequisites, misconceptions, section
sequence, component mapping, visual flags, question temperatures. On the most
recent live run it failed a field-length contract on first attempt and required
a structured-output retry. Quality on any one decision is bounded by attention
divided across all of them.

**No cross-lesson object.** Scope is enforced within a lesson. Nothing in the
system constrains lesson 4 based on what lesson 2 established. A teacher building
a six-lesson unit gets six independently planned documents.

### Change 1 — Split planning into path and lesson

A **concept path** is planned first: an ordered sequence of lesson *shells*
(title, objective, prerequisites, concept id, exclusions). No prose, no items,
no variants. The teacher reviews and approves the route. Lessons are then
prepared one at a time.

```
Plan broadly  →  review  →  generate narrowly  →  review locally
```

### Change 2 — A unit-level scope contract

Written once per unit, obeyed by every lesson:

```
must_establish · may_include · must_not_introduce ·
assumed_prerequisites · terminology · notation
```

This is the object that does not exist today.

### Change 3 — Continuity from the plan, not the prose

When preparing lesson 4, inject what lessons 1–3 *will establish* — from the path
shells, not from generated text.

Rejected alternative: read the previously generated lesson. Reasons — it only
works if lessons are prepared in order; it inherits drift from any lesson that
needed repair; and it reintroduces the context bloat the split was meant to
remove. One exception carried forward: the concrete example a lesson used, so a
later lesson can reference it by name.

### Change 4 — Deterministic lesson skeletons

Currently the LLM chooses the section sequence and a validator checks legality.
Given defect (1), it does not even check legality.

Proposed, in three layers:

```
1. LLM classifies the objective     → 1 of 4 knowledge types
2. Lookup table expands it          → ordered slots (no model call)
3. LLM may request a deviation      → with a reason, teacher-approved, logged
```

**The stated target is not bad choices.** The model usually picks reasonably.
The target is *variation without a declared reason*, which produces five
consequences:

- differentiation between groups becomes unattributable (pedagogy or sampling
  noise? unanswerable from the artifact) — and unattributable differentiation
  makes the product's central claim unfalsifiable;
- QC has no structural baseline, so legal-but-wrong passes silently;
- a future prompt tweak shifts structure everywhere with no failing test;
- regenerating after an unrelated edit returns a differently shaped lesson;
- twenty lessons in a term have twenty unmotivated shapes.

**Slots are fixed; components are reasoned.** The table fixes the pedagogical
function of each section. Component choice *within* a slot stays with the LLM,
which now receives the `cognitive_job` descriptions (defect 2). Narrower
decision, cosmetic consequences, already contract-constrained.

### Change 5 — One lesson = one concept

Defined by an **assessability test**:

> Can you write a diagnostic item for concept A that a learner could answer
> without knowing concept B? If yes, they are two lessons. If no, they are one
> concept.

This replaces the vaguer "one dominant concept or tightly coupled capability",
which is a hedge that will be abused.

Note this is a **change**: `StructuralPlan.cards` is currently a list, and a
live run produced 2 cards in one lesson.

Four reasons:
- 5 quiz items across 3 cards is ~1.7 items per concept — not enough to
  diagnose anything;
- "did they get lesson 3" is unanswerable if lesson 3 holds three concepts;
- prerequisite edges become ambiguous (which of the three does lesson 5 need?);
- 2 cards × 2–3 misconceptions exceeds the 5-slot skeleton budget.

Consequence: a path "lesson" is ~15–30 minutes, not a 50-minute period. A period
holds two or three. The UI must group them; the planner must not be given a
period budget.

### Change 6 — Remove count and time bounds

Delete `lesson_count_target`, `lesson_duration_minutes` as a planner input, and
`estimated_minutes`. Delete the "3–10 lessons, bounded by time" rule.

**Reason:** a count target does not produce economy. It produces *silent
prerequisite dropping*. If nine concepts are needed and four are requested, five
are dropped, and the path looks complete while containing holes that surface
three weeks later.

Removing the bound converts a silent omission into a visible list the teacher
trims — and the teacher knows which concepts their class can survive without.

Path length becomes bounded by the assessability floor (below it, a fragment is
not a card) and the scope contract ceiling.

**New risk:** over-fragmentation. Countered by a merge critic — one question per
adjacent pair, "could these be taught together in one sitting without loss?" —
not by a number.

### Change 7 — Misconceptions kept, quota removed

Current prompt demands 2–4 per card. Objectives that are largely recall have one
real misconception or none; forcing three manufactures fiction, which corrupts
both the quiz and the QC rubric. Change to 0–3, gated on the existing test:
*could you write a wrong answer someone holding this belief would confidently
choose?*

Misconceptions are retained because they earn their place with no tracking
system at all: the printed answer key becomes diagnostic. "Nine of twelve chose
A — they think plants eat soil" is actionable by a teacher with a red pen.

### Change 8 — Resource type stops being a creation-time input

Today the teacher picks a resource type before content exists. Proposed: the
lesson is canonical, resources are projections.

Once material is card-shaped, most resource types are **selection, not
generation** — zero model calls:

```
answer key   items + misconception tags
homework     items only, exposition stripped
unit exam    items pooled across a module
revision     card objectives + key points
flashcards   card title / objective pairs
```

### Change 9 — The concept registry

A `concepts` table with stable ids. Path dots, cards, items, booklets, and
(later) learner responses all reference one id.

Without it: "have I taught this before", "did Support outperform Core", and any
longitudinal question are permanently unanswerable. Currently the concept slug
is unique only within one teacher's one unit's one path version, and is
regenerated on replan.

### Change 10 — Provenance on every generated lesson

`skeleton_id`, `skeleton_version`, `knowledge_type`,
`knowledge_type_source`, `toggles_applied[]`, `deviations_applied[]`.

Costs nothing now. Without it, once response data exists, "did lessons built on
shape A outperform shape B" cannot be asked.

---

## Part 3 — The skeleton table (draft)

Four knowledge types, classified from the objective verb. Base skeletons are
**five slots** because `max_six_sections` is enforced and one toggle must fit.

```
procedural   "Teaches a method"        calculate, solve, construct, derive
             needs modelling before practice; non-examples are useless

conceptual   "Builds understanding"    explain, relate, distinguish, predict
             needs contrast and non-examples; worked examples are useless

factual      "Organises facts"         identify, name, list, state
             needs structure + retrieval; usually too thin to stand alone

evaluative   "Develops judgement"      assess, critique, compare-and-decide
             criteria before cases; answer key must accept a range
```

Skeletons (11 total; `retrieval` and `transfer` collapse across all types):

```
procedural.first_exposure    orient  recall    model     guided       check
procedural.consolidation     recall  guided    independ  apply        check
conceptual.first_exposure    orient  explain   contrast  confront     check
conceptual.consolidation     recall  contrast  apply     confront     check
factual.first_exposure       orient  organise  guided    independ     check
evaluative.first_exposure    orient  criteria  contrast  apply        check
evaluative.consolidation     recall  contrast  apply     apply        check
procedural.repair            recall  confront  model     guided       check
conceptual.repair            recall  confront  explain   contrast     check
any.retrieval                recall  independ  check
any.transfer                 recall  apply     apply     check
```

The `check` slot is locked — never toggled, removed, or varied by group. It
carries the shared diagnostic.

Toggles produce differentiation as a structural diff:

```
SUPPORT (high support)   +contrast, −independent, procedural: independent→model
EXTENSION (low support)  +apply(transfer), −orient
CARD-DRIVEN              one confront slot per real misconception, max 2
```

Deviations are logged. If one skeleton accumulates deviations on >20% of its
lessons, the skeleton is wrong and the table is revised.

---

## Part 4 — Decisions still open

| Decision | Options | Cost of deferring |
|---|---|---|
| Is `concept_slug` canonical? | registry table vs. per-path label | Rewrite of bridge, composer, all fixtures |
| Who owns the objective? | path authoritative vs. lesson re-derives | Two sources of truth for the field QC checks against |
| Does `evaluative` survive? | 4 types vs. collapse into conceptual | Cheap — it is data |
| Shadow mode or direct flip? | log-only for 30 lessons vs. commit now | Shadow is free; direct risks 5 phases of UI on an unvalidated premise |

---

## Part 5 — Implementation order

Deliberately shaped so irreversible decisions are cheap and come first, and
expensive work sits behind a gate that can say no.

```
1  concepts table · provenance fields · objective ownership
   ~10 lines each. Additive. Impossible to retrofit cheaply.

2  skeletons.yaml + /skeletons:preview + SHADOW LOGGING
   Table computes what it WOULD emit. No authority. No output change.
   Run 30 real lessons.

3  units + path planner + bridge, rendered in the EXISTING UI
   GATE: does a path-planned lesson beat a whole-session-planned one?
   If no, stop here — five phases of UI saved.

4  path screen · version diff · trimming · period grouping

5  compose endpoint (projections) — mostly free, high perceived value

6  one marks-entry screen — turns tagged distractors into evidence
```

Steps 1–3 are additive and reversible. Step 4 is the first large spend.

New operations:

```
POST /units · POST /units/{id}/path:plan · PATCH path/lessons/{id}
POST path/lessons/{id}:skip|:split|:merge · POST path:replan|:approve
POST /skeletons:preview          ← shows lesson shape, zero model calls
POST /units/{id}/path/lessons/{id}:prepare   ← bridge to existing pipeline
GET  /concepts?q=
POST /units/{id}/compose         ← projections, zero model calls
```

Old routes (`/studio`, `/packs/*`, `/builder/*`) are retained under a legacy
section. An existing pack renders as a one-lesson unit. No data migration.

---

## Part 6 — What we most want challenged

Ordered by how much damage a wrong answer causes.

**1. Is the deterministic skeleton right, or is it premature rigidity?**
The counter-argument we take seriously: lessons legitimately vary, the LLM can
read scope and objective and choose sensibly, and a fixed table encodes today's
pedagogical opinions as tomorrow's constraints. Our defence is that the deviation
log gives the table a correction mechanism the LLM lacks — an LLM can be wrong
indefinitely without signalling it. Is that defence sufficient? Is the four-type
taxonomy the right axis, or is there a better one? We already discarded
`subject × lesson_mode` as wrong (maths/science differ because they are usually
procedural/conceptual, not because of subject).

**2. Does one-concept-per-lesson survive contact with real teaching?**
It roughly doubles path length and makes a "lesson" shorter than a period.
Is the assessability test actually applicable by a teacher, or will it be
argued over? Is there a category of genuinely paired concepts it handles badly?

**3. Is removing count/time bounds correct?**
We claim a target causes silent prerequisite dropping. Counter: unbounded
planners fragment, and a 25-dot path is unusable regardless of how visible the
trimming UI is. Is a merge critic sufficient, or is some ceiling necessary?

**4. Is continuity-from-plan sufficient?**
Injecting what prior lessons *will* establish, rather than what they *did*.
The gap: a lesson that had to be repaired now differs from its shell. How large
is that gap in practice?

**5. Is the split between "LLM decides" and "system decides" drawn correctly?**
The rule used: the model handles decisions that are local and human-checkable in
seconds; the system handles decisions that are global and invisible on
inspection. Applied, this removes lesson count, section order, section count,
scope, QC verdicts, and variant deltas from the model, and leaves it knowledge
type, misconceptions, examples, component choice, and prose. Is anything on the
wrong side?

**6. What silent failure has been missed?**
Every guard proposed exists to close a failure that produces plausible output
with no error. What plausible-looking wrong output can this design still produce?

**7. Is the sequencing correct?**
Specifically: is shadow mode worth the delay, or is it procrastination dressed
as rigour?

---

## Appendix — Non-goals

Explicitly out of scope for this phase: learner accounts, adaptive routing,
knowledge tracing, an AI tutor, A/B assignment, marketplace, microservices,
replacing Lectio, replacing the Builder, replacing PDF generation.

Learner response capture appears at step 6 as a *single marks-entry screen*
only — the minimum that converts existing misconception-tagged distractors into
data. It is not a learner platform.

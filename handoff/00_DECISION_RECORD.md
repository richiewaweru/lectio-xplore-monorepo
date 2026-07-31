# Decision Record

## D1 — Canonical concept registry

**Decision:** Add a durable `concepts` table and reference it everywhere.

**Reason:** Without a stable concept identity, longitudinal comparison, reuse, path history, response aggregation, and variant analysis become permanently unreliable.

**Rejected:** Treating per-path slugs as canonical.

## D2 — Objective ownership

**Decision:** The approved path lesson owns the objective.

The lesson planner receives the objective as immutable input. It may propose a correction, but it may not silently replace it.

```text
Path objective
   ↓ immutable
Skeleton selection
   ↓
Lesson generation
   ↓
QC against the same objective
```

## D3 — Unit of a path lesson

**Decision:** One path lesson represents one independently assessable capability.

A pair is allowed only when the relationship is the capability:

- distinguish accuracy from precision;
- compare supply and demand responses;
- relate potential and kinetic energy.

Avoid interpreting “one concept” as “one vocabulary noun.”

## D4 — Count and time bounds

**Decision:** Remove lesson-count and lesson-duration targets from concept decomposition.

Retain time as:

- teacher scheduling context;
- feasibility warning;
- period grouping;
- print planning.

Never silently drop concepts to satisfy a period count.

## D5 — Deterministic skeletons

**Decision:** Introduce skeletons as data, first in shadow mode.

A skeleton becomes authoritative only after shadow evaluation demonstrates acceptable fit.

Deviation remains possible, but must be:

- reasoned;
- visible;
- logged;
- teacher-approved when it changes structure.

## D6 — Knowledge taxonomy

**Decision:** Keep four primary types in V1:

- procedural;
- conceptual;
- factual;
- evaluative.

Also store an optional `secondary_demand` for mixed objectives. Do not create combinatorial skeletons yet.

## D7 — Factual lessons

**Decision:** Factual lessons are flagged for possible merge, not automatically rejected.

## D8 — Differentiation

**Decision:** Variants differ through declared structural toggles. Voice and prose adaptation remain secondary.

## D9 — Shared check

**Decision:** `check` is locked and identical across variants. It carries the shared diagnostic.

## D10 — Continuity

**Decision:** Use:

```text
planned prior establishment
+ teacher-confirmed actual outcome
+ named anchor/example
```

Do not inject full prior generated lesson prose.

## D11 — Resource types

**Decision:** Remove resource type from initial unit creation. Canonical content is composed into lesson, homework, revision, flashcards, quiz, answer key, and unit exam projections.

## D12 — UI investment gate

**Decision:** Steps 1–3 remain additive and reversible. Full path UI begins only after path-planned lessons are compared against current whole-session planning.

## D13 — Existing Xplore compatibility

**Decision:** Existing Studio, packs, Builder, Lectio, PDF, generation rows, and review flows remain operational. Existing packs can be represented as one-lesson legacy units without data migration.

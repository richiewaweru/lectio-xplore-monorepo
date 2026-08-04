# Master Prompt for Claude / Codex

You are implementing the **Xplore Learning Platform V2** in:

- repository: `richiewaweru/text-book-generator`
- base branch: `xplore`
- reference branch: `v3`

Read every artifact in this handoff before modifying code. Also read the source `VETTING_BRIEF.md` and `skeletons-v1-draft.yaml`.

## Mission

Implement and validate this product:

```text
Topic
→ Unit scope
→ Canonical concept path
→ One assessable capability per path lesson
→ Knowledge type
→ Deterministic skeleton
→ Controlled group variants
→ Existing Xplore generation/review/QC
→ Resource projections
→ Print + minimal marks evidence
```

## Non-negotiable invariants

Preserve:

- item generation receives card-only context;
- shared items are pack-owned;
- QC verdict is recomputed;
- null distractor tags remain allowed;
- sibling variant failure does not block siblings;
- teacher edits survive regeneration;
- awaiting_review survives restart;
- Lectio, Builder, and current PDF generation remain.

## Mandatory decisions

- canonical concepts table;
- path owns objective;
- one independently assessable capability per new path lesson;
- time does not truncate path;
- skeletons shadow first;
- check slot locked;
- variants are structural diffs;
- resource types become projections;
- continuity includes teacher actuals;
- no learner platform in this phase.

## Execution

Follow `14_IMPLEMENTATION_PHASES.md` exactly.

For each phase:

1. inspect current repository with grep before changing;
2. write failing regression tests for defects;
3. document contradictions;
4. use additive and reversible changes first;
5. run focused tests;
6. run full relevant gates;
7. run architecture validation;
8. update `PROGRESS.md`;
9. commit with phase-specific message.

## Gate discipline

Do not build the full path UI before:

- shadow skeleton review is complete;
- path planner and bridge work in a minimal existing UI;
- comparative evaluation supports continuing.

## No silent compromises

Never:

- drop concepts to meet lesson count;
- let lesson planner rewrite objective;
- truncate slots without warning;
- force-map distractors;
- silently merge concepts;
- silently adapt unknown legacy fields;
- report a partial path as complete.

## Deliverables

Return at the end:

- architecture summary;
- exact files/migrations;
- test results;
- shadow-study results;
- comparative gate result;
- browser evidence;
- deviations from handoff;
- remaining risks;
- deliberately deferred work.

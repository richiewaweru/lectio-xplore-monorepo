# Lectio Smart Lesson Planning + Coherence Pass

Repository: `richiewaweru/lectio-xplore-monorepo`
Baseline branch: `main`
Baseline inspected commit: `af7a3d46e684d9752c6e18034f9b86b322348936`
Date: 2026-09-16

## Goal

Improve the quality of the lesson itself **before** visual redesign of Print or Learn primitives.

The target is one shared instructional engine that:

1. chooses an appropriate teaching journey for the exact objective instead of treating the current skeleton order as absolute;
2. preserves one shared Teaching Plan for Print and Learn;
3. allows purposeful formative learner tasks before/during/after explanation without forcing every response task to be a pre-approved assessment item;
4. creates one canonical lesson sourcebook so independent writers cannot silently invent contradictory examples, numbers, dates, facts, or stimuli;
5. authors shared task meaning/content once, then lets Print and Learn realize it differently;
6. reviews each completed lesson as a whole and performs **targeted repair**, not full regeneration;
7. proves the result across a genuinely wide subject range before any UI/primitives redesign begins.

## The key architectural decision

Do **not** create a second competing lesson-flow artifact beside Teaching Plan.

The existing Teaching Plan is already close to the correct shared authority. Strengthen the stages immediately before and after it:

```text
Objective / scope / prior knowledge
              ↓
      SMART FLOW SELECTION
  skeleton = recommendation, not prison
              ↓
        SHARED TEACHING PLAN
 arc + ordered sections + blocks + learner actions
              ↓
       LESSON SOURCEBOOK
 canonical examples / data / facts / stimuli
              ↓
        SHARED TASK SPECS
       formative + assessment
              ↓
       TEACHER APPROVAL
              ↓
        ┌─────┴─────┐
        │           │
      PRINT       LEARN
        │           │
  paper treatment  interaction treatment
        │           │
   full output    full output
        │           │
   COHERENCE REVIEW + SURGICAL REPAIR
```

## What is deliberately preserved

Keep:

- Path objective ownership.
- Unit scope / must-establish / exclusions / terminology.
- Existing Teaching Plan approval/revision machinery.
- The closed learner-action vocabulary.
- The six ordinary document primitives: Paragraph, Heading, List, Figure, Table, Callout.
- Independent Print and Learn realizations.
- Learn retained interaction registry and shortlist selection.
- Print task-treatment mapping and print-only pagination/layout decisions.
- Existing authoring engine, call budgets, checkpoints, and reliability infrastructure.

## What changes

The current system fixes section order before the Teaching Plan LLM sees the lesson, and the current learner-action contract requires every response-bearing action to own a pre-approved assessment source. Primitive writers then author independently, which can produce contradictions even when every individual node is schema-valid.

This pass changes those boundaries without reopening the Print/Learn separation.

## Execution order

Read and implement in this order:

1. `01_TARGET_ARCHITECTURE.md`
2. `02_CURRENT_TO_TARGET_MAP.md`
3. `04_DATA_CONTRACTS.md`
4. `03_IMPLEMENTATION_PHASES.md`
5. `prompts/`
6. `patch-guidance/FILE_CHANGE_MAP.md`
7. `05_TEST_AND_LIVE_PROOF.md`
8. `06_ACCEPTANCE_MATRIX.md`

Do not begin visual primitive redesign in this pass.

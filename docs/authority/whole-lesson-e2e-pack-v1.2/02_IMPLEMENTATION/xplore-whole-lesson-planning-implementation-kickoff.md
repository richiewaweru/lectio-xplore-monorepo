# Xplore Native Whole-Lesson Planning — Implementation Kickoff Brief

**Target repository:** `richiewaweru/lectio-xplore-monorepo`  
**Target branch:** `pageobject-integration` or a new implementation branch created from it  
**Authority:** `xplore-whole-lesson-planning-resolved-proposal-v1.1.md`  
**Goal:** Produce four complete recorded lessons through the real Xplore path, from unit planning to strict teacher/student PDF, using native `LectioDocumentV2` and no legacy component conversion.

---

## 1. Non-Negotiable Invariants

```text
1. Teaching planning is one whole-lesson STANDARD-tier call.
2. The teaching planner receives zero page-object information.
3. Form planning is one whole-lesson FAST-tier call.
4. Teacher approval is mandatory after the teaching plan and before form/writer calls.
5. Question content comes only from approved PackItemModel records.
6. The native executor reads blocks, not components.
7. Both plan artifacts and validation reports are persisted.
8. Every native block emits block-level events.
9. Final PDF blocks while required figures are pending or failed.
10. No fixture or legacy fallback may make a failed run appear successful.
```

---

## 2. First Cutline — Make Planning Honest

### 2.1 Approved items

Implement a typed loader for non-stale `PackItemModel` records tied to the prepared concept card and pack. Populate:

- lesson packet approved item pool;
- planner-visible approved item IDs;
- `WriterContext.item_records` during deterministic question assembly.

Fail with `ITEM_POOL_EMPTY` before planning if the official proof lesson has no approved items.

### 2.2 Catalogue projections

Add `planning/catalogue_projections.py` with distinct typed projections:

- teaching guidance;
- form guidance;
- selected writer contract.

Add a negative test that serialises teaching guidance and checks every registered page-object ID is absent.

### 2.3 Model and timeout configuration

Add configurable `STANDARD` and `FAST` model routing plus dedicated page-planning/writer timeout settings. Do not reuse `allow_paid_llm_tests` as production routing.

**Cutline passes when:** a lesson packet can be created with approved items and a teaching projection that provably contains no objects.

---

## 3. Second Cutline — Produce and Approve the Teaching Plan

Implement:

- immutable lesson packet schema;
- whole-lesson teaching-plan schema;
- standard-tier agent;
- hard validator;
- deterministic brief checks;
- advisory QC report;
- maximum two-attempt retry/repair policy;
- persistence in native page state;
- native planning events;
- `awaiting_teaching_approval` status;
- GET/approve/reject endpoints with revision checks;
- frontend lesson-approach review surface.

No form planner or writer may run before approval.

**Cutline passes when:** local Xplore creates a real teaching plan, persists it, displays the arc and all blocks, and waits for explicit approval.

---

## 4. Third Cutline — Form Plan and Native Writing

Implement:

- whole-lesson FAST form planner;
- compatibility/order validation;
- persisted form artifact;
- tiered LLM writers;
- deterministic questions assembler using loaded item records;
- native block executor;
- `block_queued`, `block_started`, `block_ready`, and `block_failed` events;
- native document assembly and validation;
- durable final `GenerationModel.document_json`.

The v2 path must not instantiate `GeneratedComponentBlock`, `SectionContent`, or `V3SectionBuilder`.

**Cutline passes when:** an approved lesson generates a persisted and reloadable `LectioDocumentV2` using real model calls.

---

## 5. Fourth Cutline — Product Completion

Implement:

- frontend native event state and progress counters;
- stable figure request IDs and live asset callbacks;
- strict pending-asset print policy;
- teacher/student edition export;
- block content patch endpoint by stable block ID;
- evidence capture tooling.

**Cutline passes when:** the stored document renders in Xplore, a teacher can patch one block, and strict teacher/student PDFs succeed.

---

## 6. Four Official Runs

Run in order:

1. Grade 4 Science — Why Plants Need Light to Make Food
2. Grade 6 Mathematics — Understanding Equivalent Fractions
3. Grade 8 Economics — How Supply and Demand Affect Price
4. Grade 7 English — Distinguishing a Claim from Supporting Evidence

After Run 1, read the final brief first. Correct architectural defects before proceeding. Do not weaken the test by dropping questions or manually inserting a document.

---

## 7. Required Final Report

Return:

- commit SHA and changed-file list;
- tests run and results;
- model/tier and call counts;
- planner/form repair counts;
- four evidence-package paths;
- last-brief-first assessment for every run;
- advisory QC warnings;
- screenshots and teacher/student PDF paths;
- explicit proof that no fixture or legacy component path ran;
- remaining deferred work.

Stop and report a structured blocker rather than creating a fake successful artifact.

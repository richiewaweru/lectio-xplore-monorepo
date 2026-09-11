# CASA Master Execution Prompt

You are completing the **Lectio generation closeout** in `richiewaweru/lectio-xplore-monorepo`.

Known inspected baseline:
- branch: `fix/document-overhaul-correction`
- commit: `db8390335c085eca084ed758fc154d43aed3af41`

Verify the real branch and HEAD yourself before editing. Create a new implementation branch. Never edit main directly.

## This is not a redesign

```text
Unit
 ↓
approved Teaching Plan
 ↓
explicit path choice
 ├──────────────────────────┐
 ↓                          ↓
PRINT                      LEARN
shared document composer   shared document composer
shared ordinary writer     shared ordinary writer
+ Print treatments         + retained interactions
 ↓                          ↓
Print artifact             Learn artifact
```

Read repo instructions, then this closeout pack in order.

## Rule zero: implementation is runtime truth

Do not trust reports, comments, filenames, or phase checkboxes.

For every requirement produce:

```text
requirement
→ current canonical call graph
→ defect/gap
→ code/spec change
→ focused test
→ real production-path proof
→ PASS / FAIL / BLOCKED
```

If Unit/browser flow bypasses your new code, the requirement is not complete.

No `PASS WITH DEFERRED DEBT`.

## A. Externalize mutable intelligence

Use Markdown for LLM behavioral policy and YAML/JSON for stable option/mapping data. Do not bury mutable instructional philosophy in Python.

Register production prompt files in the existing prompt manifest/loader system.

At minimum externalize:
- learner-action policy;
- document composition guidance;
- document writing guidance;
- interaction selection guidance;
- interaction writing guidance;
- figure authoring guidance;
- Print realization guidance.

Prompt files must be genuinely loaded by production. Prove effective prompt hashes.

## B. Fix learner-action planning

`learner_action` means intentional observable learner behavior, not only formal assessment.

The Teaching Plan may place learner actions before, during or after explanation when they improve learning.

Do not make every block interactive. Do not hardcode `intent == check -> interaction`.

Feed the learner-action policy into planner generation and add semantic validation for clearly evidence-producing/check/practice cases that incorrectly return null while still preserving legitimate passive blocks.

Run fresh real Teaching Plans and inspect action density.

## C. Keep paths as twins

Teaching Plan decides whether a learner task exists. Learn and Print translate the same action differently.

Move action maps from hardcoded Python into policy files where practical.

Do not let Print invent a response task merely because an intent sounds assessive while Learn sees no learner action, except explicitly documented approved-item ownership semantics.

## D. Finish Print shared writing

The live Unit Print path must use the shared document writer for ordinary nodes.

Print page-object/layout/treatment code may adapt already-authored content. Do not keep a competing ordinary content authoring path.

Prove this with call/trace evidence from a live Unit Print run.

## E. Make realize-print symmetrical with realize-learn

Add a canonical Print handoff from approved Teaching Plan/preparation. Unit UI calls the handoff. Studio opens/edits the artifact after admission.

No re-approval dance. No Learn↔Print conversion.

## F. Fix asset serving and section identity

Use one absolute configured image-store root for both figure writer and FastAPI `/images` mount.

Preserve section identity/order/title/transition in LearnDocument so tabs and section-local editing do not need to reopen Teaching Plan.

## G. Prove natural Learn interactivity

Run a fresh Unit whose Teaching Plan itself emits learner actions. Do not inject actions by hand.

Render, submit, evaluate and persist resulting interactions through browser/runtime.

Then add tabs/navigation using realized section metadata.

## H. Add native Print editing

Edit native `LectioDocument v2` in the Print workspace. Do NOT build this on the LearnDocument print route.

First useful edit set:
- prose;
- lists;
- table cells;
- callouts;
- figure metadata/asset;
- questions/options;
- response-space settings where supported.

Save with optimistic revision control. Stale revision -> 409. Save/reload/PDF must prove persistence. Learn sibling must remain unchanged.

## Strict gate behavior

A phase is incomplete if:
- only fixtures prove it;
- a prompt is not actually loaded;
- UI does not call endpoint;
- a fallback hides intended stage;
- persistence/reload is missing;
- browser/runtime proof required by phase is missing;
- old competing canonical logic still runs.

If a required provider/browser/database dependency is unavailable, mark BLOCKED.

## Final evidence required

Return:
1. starting SHA and branch;
2. phase ledger A-I;
3. exact files added/changed/deleted;
4. canonical final call graph;
5. exact test commands/results;
6. real Unit ids / generation ids for Learn and Print proofs;
7. Teaching Plan snippets showing naturally generated learner actions;
8. prompt ids + effective hashes used;
9. live interaction proof;
10. figure URL proof;
11. realize-print proof;
12. Print edit/save/reload/PDF proof;
13. remaining FAIL/BLOCKED items.

Do not report completion until `verification/FINAL_ACCEPTANCE_MATRIX.md` has no failed critical item.

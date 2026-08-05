# Codex Master Goal — Native Whole-Lesson Xplore Vertical Slice

Work in `richiewaweru/lectio-xplore-monorepo` on the active page-object integration branch.

Treat the documents in this pack as authoritative and read them in the order listed by `00_READ_ME_FIRST.md`. Implement the native whole-lesson architecture through a complete local application proof. Do not stop after schemas, unit tests, isolated planners, or fixture documents.

## Required product outcome

A teacher can:

```text
prepare a lesson
→ receive one whole-lesson teaching plan
→ review and explicitly approve that plan
→ generate one whole-lesson form plan
→ run real page-object writers
→ assemble and persist LectioDocumentV2
→ reload and render it in Xplore through @lectio/page
→ export teacher and student PDFs
```

## Non-negotiable constraints

- Use one whole-lesson teaching-planner call and one whole-lesson form-planner call.
- Copy the supplied `lesson-approach-planner-v1.txt` and `form-planner-v1.txt` byte-for-byte. Do not improve them during implementation.
- The teaching planner must receive a structural teaching-guidance projection containing zero page-object IDs or names.
- Anchor and approved misconceptions are fixed upstream inputs. The lesson planner may choose misconception focus and anchor usage, not invent or replace them.
- Load approved question items from the canonical `PackItemModel`/concept-card relationship before planning. The planner may reference approved item IDs but may never write question content.
- Compute whether an intent is atypical in code. Typical means no departure reason; permitted but atypical requires one; excluded is rejected.
- Persist the teaching plan and form plan as first-class artifacts before downstream execution.
- Require explicit teacher approval after the teaching plan and before form planning.
- Replace native progress vocabulary with block-level events; do not route native output through legacy `component_ready` semantics.
- The native v2 route must bypass ComponentSlot, GeneratedComponentBlock, SectionContent, V3SectionBuilder, legacy field mapping, and v1 conversion.
- Writers must use real model calls according to the tier policy. Questions remain deterministic.
- Figure request identity must be stable. Printing while a required figure is pending must follow the resolved proposal’s explicit policy; never silently omit it.
- Persist the native document to the actual generation record and prove reload after persistence.
- Do not auto-install Playwright Chromium from package postinstall; use an explicit install command when required locally.

## Model tiers

- Lesson approach and its repair: STANDARD.
- Form plan and its repair: FAST.
- Prose and worked-example writers: STANDARD.
- List, table, and figure-brief writers: FAST.
- Questions: no model call.
- Answer-key formatting/derivation, where a model is genuinely required by existing design: FAST.

## Execution order

1. Connect approved item records to the immutable lesson packet.
2. Add catalogue projections, beginning with the object-free teaching view.
3. Apply the Cutline 1.5 prompt and vocabulary work exactly.
4. Implement the lesson-approach schema, standard-tier agent, hard validation, advisory QC, timeout, and one targeted repair.
5. Persist the teaching plan and expose the teacher review/approval gate.
6. Implement the whole-lesson form planner, validation, QC, timeout, and one repair.
7. Implement real typed writers and deterministic questions assembly.
8. Implement native block execution, events, persistence, reload, figures, render, and PDFs.
9. Run the four official lessons using `04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md`.
10. Produce the final four-run comparison report.

## Required proof lessons

- Science: why plants need light to make food.
- Mathematics: equivalent fractions.
- Economics: how supply and demand affect price.
- English: distinguishing a claim from supporting evidence.

Use the real unit/path workflow and conceptual first-exposure skeleton. Do not hand-create a plan or document halfway through.

After Run 1, read the final brief before the first and apply the protocol’s gate. Preserve all original prompts and responses before making any prompt revision. A revision must receive a new version.

## Verification

Run focused unit and integration tests throughout, then perform browser verification on the local frontend and backend. Capture all evidence required by the proof protocol, including exact prompts, raw responses, validation, repairs, events, timing, tokens/cost, persisted/reloaded documents, screenshots, and both PDFs.

Do not describe a task as complete unless the corresponding evidence artifact exists. If something fails, report the exact stage, error, affected invariant, and remaining correction. Never substitute a fixture, legacy conversion, or silent fallback to make a run appear successful.

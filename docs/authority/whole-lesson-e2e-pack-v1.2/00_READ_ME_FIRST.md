# Xplore Whole-Lesson Native Generation — Final Four-Run Pack

## Intended finish line

A teacher can prepare a lesson, review and approve its teaching plan, and print it through the native page-oriented Lectio path:

```text
prepare lesson
    ↓
teaching plan
    ↓
TEACHER APPROVAL
    ↓
whole-lesson form plan
    ↓
object writers
    ↓
assemble
    ↓
persist LectioDocumentV2
    ↓
render in Xplore using @lectio/page
    ↓
teacher PDF + student PDF
```

The proof is **four recorded lessons across four subjects**. Every stage must be real:

- no fixture planner;
- no placeholder writers;
- no v1 component conversion;
- no manually inserted document fixture;
- no question generation from lesson prose;
- no silent auto-approval.

Each run must preserve the planning artifacts, exact prompts as sent, raw model outputs, parsed outputs, validation and repair results, block events, timing and token/cost records, QC review, persisted document, screenshots, and teacher/student PDFs.

## Document authority and reading order

Read and execute in this order:

1. `01_ARCHITECTURE/xplore-whole-lesson-planning-resolved-proposal-v1.1.md`
   - Architectural authority.
   - Defines ownership, schemas, barriers, validation, repair, variants, approval, persistence, events, questions, figures, and acceptance.

2. `02_IMPLEMENTATION/xplore-whole-lesson-planning-implementation-kickoff.md`
   - Main implementation cutlines and end-to-end delivery order.

3. `03_CODEX_ADDITIONS/KICKOFF_ADDENDUM_cutline_1_5.md`
   - Inserts between kickoff Cutline 1 and Cutline 2.
   - Settles prompts, upstream anchor/misconception ownership, resource identity rendering, vocabulary migration, and writer prompt inputs.

4. `03_CODEX_ADDITIONS/lesson-approach-planner-v1.txt`
   - Copy verbatim into the repository resource path specified by the addendum.
   - Do not rewrite during implementation or the Run 1 quality result will not be attributable.

5. `03_CODEX_ADDITIONS/form-planner-v1.txt`
   - Copy verbatim into the repository resource path specified by the addendum.

6. `04_PROOF_RUNS/FOUR_RUN_PROOF_PROTOCOL.md`
   - Exact procedure for the four official runs and their evidence packages.

7. `05_HANDOFF/CODEX_MASTER_GOAL_PROMPT.md`
   - Pasteable execution goal for Codex/Cursor.

## Precedence

When wording appears to conflict:

1. The resolved proposal is the architectural authority.
2. The kickoff addendum explicitly amends the implementation kickoff where stated.
3. The supplied prompt files are immutable for the first four proof runs.
4. The proof protocol governs evidence collection and pass/fail reporting, not architecture.

Do not resolve ambiguity by reviving the legacy component pipeline. Record the conflict in the final report and choose the native page-object interpretation consistent with the resolved proposal.

## Official run subjects

Use four conceptually different subjects to expose hard-coded assumptions:

1. Science — why plants need light to make food.
2. Mathematics — equivalent fractions.
3. Economics — how supply and demand affect price.
4. English — distinguishing a claim from supporting evidence.

The exact grade and wording may follow the prepared unit input, but the four subjects must remain distinct.

## End-of-pack deliverable

Implementation is not complete when unit tests pass. It is complete when all four evidence folders exist and the application demonstrates:

```text
unit/path input
→ lesson preparation
→ whole-lesson teaching plan
→ teacher approval
→ whole-lesson form plan
→ real page-object writing
→ canonical questions assembly
→ figure lifecycle
→ native document persistence/reload
→ Xplore render
→ teacher PDF
→ student PDF
```

See `CHECKSUMS.sha256` to verify that the supplied Codex additions were included unchanged.

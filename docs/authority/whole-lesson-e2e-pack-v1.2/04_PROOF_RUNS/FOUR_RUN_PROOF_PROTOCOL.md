# Four-Run End-to-End Proof Protocol

## 1. Purpose

The four runs are not demo screenshots. They are an architecture and prompt-quality experiment intended to answer:

1. Can one whole-lesson planning call maintain a coherent teaching arc across all sections?
2. Is the final block brief as concrete as the first?
3. Does the form planner choose forms that earn their place without flattening the document?
4. Do writers follow the fixed intent, brief, object contract, terminology, exclusions, and neighbour context?
5. Does the application preserve every stage from unit planning through native PDF output?
6. Do timing, tokens, cost, retries, and quality support the selected model-tier policy?

A run that reaches a PDF through a fixture or legacy conversion is a failure, not partial success.

## 2. Official run set

| Run | Subject | Core concept | Primary architecture pressure |
|---|---|---|---|
| 01 | Science | Why plants need light to make food | anchor reuse, misconception, comparison, figure, questions |
| 02 | Mathematics | Equivalent fractions | worked example, notation, capacity, visual/form choice |
| 03 | Economics | How supply and demand affect price | causal chain, table/figure restraint, interpretation |
| 04 | English | Claim versus supporting evidence | non-STEM generality, text examples, question alignment |

All four should use the supported conceptual first-exposure skeleton:

```text
orient → explain → confront → check
```

Do not introduce a second lesson mode or knowledge type during this proof.

## 3. Required preconditions

Before Run 1:

- the teaching guidance projection exists and contains no page-object IDs;
- the exact rendered teaching prompt contains no page-object IDs;
- approved item records are loaded from the canonical item store;
- the teaching plan and form plan can be persisted and reloaded;
- the teacher approval state blocks form planning until approval;
- native block events are emitted;
- the v2 path bypasses ComponentSlot, GeneratedComponentBlock, SectionContent, and V3SectionBuilder;
- model names, tiers, prompt versions, timeout budgets, and repair limits are logged;
- the supplied planner prompts are installed byte-identically.

## 4. Run procedure

Perform every run through the actual local Xplore UI and API path.

```text
1. Create or load the unit.
2. Generate the path using the real path planner.
3. Review and approve the path through the normal workflow.
4. Prepare the selected lesson.
5. Capture the immutable lesson packet.
6. Render and capture the exact teaching-planner prompt.
7. Call the real lesson-approach model.
8. Store the raw response before parsing.
9. Parse, hard-validate, and record advisory QC.
10. If invalid, perform at most one targeted repair call and capture both attempts.
11. Persist the teaching-plan artifact.
12. Halt at the teacher review gate.
13. Review the plan, reading the last brief first.
14. Approve it through the actual approval endpoint/UI.
15. Render and capture the exact form-planner prompt.
16. Call the real form planner.
17. Store raw response, parsed plan, validation, QC, and any single repair.
18. Persist the form-plan artifact.
19. Execute real object writers with their exact prompts captured.
20. Assemble questions only from referenced approved item records.
21. Run the figure work-order lifecycle where the plan contains a figure.
22. Assemble and hard-validate LectioDocumentV2.
23. Persist it to the real generation record.
24. Reload it from persistence; do not render the in-memory copy as proof.
25. Render the lesson in the Xplore generation page through @lectio/page.
26. Export a teacher PDF.
27. Export a student PDF and verify answer-key policy.
28. Complete the quality scorecard and input-output trace.
29. Record elapsed time, stage latency, tokens, cost, attempts, and failures.
30. Write the run conclusion and required prompt/design changes.
```

## 5. Evidence folder

Create:

```text
docs/evidence/whole-lesson-runs/
  run-01-science/
  run-02-mathematics/
  run-03-economics/
  run-04-english/
```

Each run folder must contain:

```text
00-manifest.yaml
01-unit-input.json
02-scope-contract.json
03-path-plan-raw.txt
04-path-plan.json
05-path-approval.json
06-lesson-packet.json
07-teaching-guidance.json
08-lesson-approach-prompt.txt
09-lesson-approach-response-raw.txt
10-teaching-plan.json
11-teaching-validation.json
12-teaching-qc.json
13-teacher-plan-review.json
14-teaching-plan-approval.json
15-form-guidance.json
16-form-planner-prompt.txt
17-form-planner-response-raw.txt
18-form-plan.json
19-form-validation.json
20-form-qc.json
21-writer-call-ledger.csv
22-writer-prompts/
23-writer-responses-raw/
24-writer-results.json
25-approved-item-records.json
26-question-assembly.json
27-visual-work-orders.json
28-event-stream.jsonl
29-persisted-generation-record.json
30-reloaded-lectio-document.json
31-document-validation.json
32-input-output-trace.md
33-quality-scorecard.md
34-generation-page.png
35-teacher.pdf
36-student.pdf
37-timing-and-cost.json
38-run-log.txt
39-conclusion.md
```

When no figure is selected, keep `27-visual-work-orders.json` with an empty array and an explanatory note. Do not add a figure merely to fill the evidence folder.

## 6. Prompt and response attribution

For every LLM call, record:

- call ID and trace ID;
- generation ID;
- caller and stage;
- model provider and exact model name;
- tier: standard or fast;
- prompt resource file and prompt version;
- exact prompt after all substitutions;
- raw response before schema parsing;
- parsed result;
- validation result;
- repair relationship, when applicable;
- start and completion timestamps;
- latency in milliseconds;
- input, output, and thinking tokens where available;
- estimated or provider-reported cost;
- timeout and retry outcome.

A summarized prompt is insufficient. Preserve the exact string sent.

## 7. Quality review order

Review the teaching plan in this order:

1. Last block brief.
2. First block brief.
3. Arc.
4. Intent sequence across all sections.
5. Evidence sentences.
6. Evidence references.
7. Anchor usage.
8. Misconception focus and confrontation.
9. Check-section item IDs.
10. Departure reasons.

This order intentionally exposes end-of-output thinning before the stronger opening biases the reviewer.

## 8. Input-output trace

The final content must be traced back to the approved input. Map at least:

```text
objective
must_establish entries
must_not_introduce entries
terminology
anchor identity
approved misconceptions
prior-established entries
approved question item IDs
```

For each source input, identify:

- teaching-plan block(s) that reference it;
- form selected for those blocks;
- writer result(s) that express it;
- final document location;
- whether meaning was preserved;
- omissions, distortions, or unsupported additions.

## 9. Quantitative records

Record both wall-clock and stage metrics:

```text
path planning
lesson preparation
lesson-approach call
teaching-plan repair, if any
teacher review wait time (separate from system time)
form-planner call
form repair, if any
writer wall-clock and aggregate model time
question assembly
figure generation wait
assembly and validation
persistence and reload
render
teacher PDF
student PDF
total machine execution time
total user-observed elapsed time
```

Also report:

- total planner calls;
- total writer calls;
- repair count;
- timeout count;
- block count;
- departure count and rate;
- form distribution;
- validation warnings;
- total tokens and cost.

## 10. Run 1 gate

After Run 1, stop and assess before launching Runs 2–4.

Proceed only when:

- the final brief is not materially weaker than the first;
- no page-object name leaked into the teaching prompt or teaching plan;
- every evidence reference resolves;
- every intent is legal and departure rules hold;
- teacher approval genuinely blocked downstream generation;
- questions came from approved item IDs;
- the native document was persisted and reloaded;
- no legacy conversion participated;
- teacher and student PDFs rendered with correct answer visibility.

A prompt-quality weakness may be corrected before Runs 2–4, but preserve the original Run 1 prompts and outputs. Any prompt revision creates a new prompt version and must be recorded.

## 11. Pass/fail rules

A run fails if any of the following occurs:

- fixture planning or placeholder writing is used;
- a v1 component is created or converted on the native path;
- the planner invents question content or unknown item IDs;
- form planning begins before teacher approval;
- a plan artifact is not persisted;
- the rendered document is not reloaded from persistence;
- the teacher and student PDFs are identical when an answer key exists;
- a pending figure silently disappears or prints as completed;
- raw prompts or responses are missing;
- timing and model records are missing;
- the document violates contract or semantic hard validation.

## 12. Final four-run report

Produce one report containing:

1. Architecture implemented.
2. Deviations from the proposal and why.
3. Per-run summaries.
4. Side-by-side plan quality comparison.
5. First-brief versus last-brief comparison.
6. Form distribution and visual rhythm comparison.
7. Writer fidelity comparison.
8. Question-wall verification.
9. Timing, tokens, cost, retries, and timeouts.
10. Teacher/student PDF findings.
11. Bugs fixed during the run sequence.
12. Prompt changes made between runs.
13. Remaining blockers before teacher use.
14. Legacy code now unreachable and safe to remove.
15. Recommendation: retain whole-lesson planning, split expansion by section, or redesign.

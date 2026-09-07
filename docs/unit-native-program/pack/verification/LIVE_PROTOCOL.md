# Live verification campaign

## Prerequisites
P08 PASS; real provider credentials and network access; dedicated test teacher and learner identities; test DB; app build; browser capability; current package exports. Use the configured application provider, record actual provider/model and settings relevant to output. No credentials in evidence.
If browser or provider unavailable, mark corresponding live gates BLOCKED. Complete deterministic tests and document exact unblock action. Do not simulate live evidence.

## Four cases (both paths for each)
| Case | Objective shape | Expected Learn evidence | Print inspection |
|---|---|---|---|
| A cycle | Order butterfly life-cycle stages and explain repeat | Generated Sequence activity; meaningful independent order check | Order task and accurate teacher key, cycle content |
| B classification | Distinguish examples by explicit classification criteria | Classify; confirm category feedback | Valid comparison/classification presentation |
| C procedure | Apply a short arithmetic procedure with a worked example | Numeric or supported response and guided→independent progression | Worked example and new problem, readable notation |
| D visual concept | Identify named parts of an approved diagram and their roles | ImageChoice or validated spatial interaction; text-supported alternative only if spatial remains explicitly unavailable | Required figure, labels and placement |

Choose grade/curriculum scope from real approved material. Fixtures in this pack are illustrative planning inputs, not authority to invent curriculum standards.
A match-pairs/choice/multiselect/blank example may be added to cases when pedagogically appropriate. Do not force every interaction into one lesson for coverage; use separate integration/package fixtures for full catalogue coverage.

## Per-case workflow
1. In UI create a designated test Unit, scope and concepts; plan and approve its PathLesson. Record IDs, objective and source.
2. Prepare and approve shared teaching through normal product route. Inspect intent/action briefs and scope; record revision/hash.
3. Produce Print and Learn from that same revision, with live selectors/writers. Record outbound trace references and candidate snapshots. Do not inject plan fixtures or payloads.
4. Watch status through completion; refresh during execution once. Confirm no duplicate run or path switching.
5. Open Print through product route. Export student and teacher PDFs; render every page to images. Inspect no clipping, lost rows, misplaced figures, answer disclosure or missing content. Save both PDFs and inspection notes.
6. Open Learn in Builder. Make a meaningful safe edit, save and reload. Preview and submit a practice interaction; confirm no production attempts/evidence added.
7. Publish release v1, assign to designated test learner, sign in through learner path. Answer at least one incorrectly then retry where allowed; answer independent task; refresh. Verify UI state and persisted response/outcome/score, concept bindings and release ID.
8. Edit draft and publish v2. Confirm v1 assigned instance and hash unchanged. Do not stamp current Unit revisions onto old drafts.
9. Review instructional fidelity across paths: same objective/scope, meaningful support, task equivalence, no premature answer, accurate feedback and appropriate native form.
10. Record timing per stage, calls, retries, total duration and remaining concerns.

## Controlled failure
On one designated run, use existing safe failure injection at provider/writer boundary or a test-only fault hook isolated from ordinary users. Trigger one recoverable failure. Resume through normal retry UI/API; assert successful sibling block hashes and opposite-path output unchanged. Record failure stage and repair. Never disrupt a production provider/account globally.

## Submission proof
For one instance inspect persisted attempt/progress/evidence rows through supported read-only DB access. Confirm client-supplied score/binding is rejected/ignored in a controlled request and cannot alter records. Verify duplicate submission creates no extra attempt. Confirm unrelated self-started instance does not enter assignment analytics.

## Review rubric (per output)
Rate each 0 missing/wrong, 1 needs material repair, 2 acceptable, 3 strong:
objective fidelity; factual correctness; coherent sequence; support→independence; assessment validity; native usability.
No critical factual error, missing required block/visual, invalid score, broken persistence or unauthorized access is acceptable regardless of total. Require all dimensions >=2; repair and rerun affected steps otherwise.
This is a practical acceptance rubric, not validated educational efficacy research.

## Evidence record
Use tracking/LIVE_RUN_TEMPLATE.json per case. Include starting/ending commits, plan/contract/policy hashes, generation IDs, realization IDs, editable/release/assignment/instance IDs, PDF paths, screenshots, DB/trace references, timings, reviews and exact PASS/FAIL/BLOCKED status. Redact private learner details and secrets.

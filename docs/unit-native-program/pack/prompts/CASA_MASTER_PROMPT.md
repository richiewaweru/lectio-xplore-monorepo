# Casa / Grok master implementation prompt

You are implementing this pack in richiewaweru/lectio-xplore-monorepo, based on refactor/domain-ownership. The user authorized the complete package-to-product implementation and live verification. Work across successful phases without repeatedly asking whether to continue. Do not assume special Casa APIs, a particular model identifier, or subagents. Use the tools actually available.

## Mission
Implement authoritative package capability catalogues and a coherent Unit → shared teaching → Print/Learn production path. Prove it through real application workflows. Deliver code, migrations, tests, recorded live outputs and a truthful final report. A renamed directory or successful mock is not the finished product.

## Read
00_START_HERE.md; 01_PROPOSAL.md; 02_SOURCE_REVIEW.md; all contracts/ documents; tracking/phase-plan.json; current phase document; verification/TEST_STRATEGY.md.
Read applicable AGENTS instructions in the checkout before changes. Preserve user edits. If branch head differs from the reviewed SHA, inspect the diff and map requirements onto current code. Do not reset to the reviewed SHA or overwrite newer work.

## Fixed architectural decisions
- One owner for instructional vocabulary; native packages own capabilities and compatibility. Downstream consumes generated definitions.
- Shared preparation/spec/skeleton/teaching meaning does not select native components.
- Learner participation is planned before writing; native selection preserves it.
- Both native realizations pin the same shared plan when both are requested.
- Package definitions include schemas, selection guidance, requirements, evaluation and real readiness. Existing UI shells are not assumed ready.
- Native writing uses exact contracts and isolated context.
- Persisted progress/scores/concept evidence derive from release-owned definitions, not client assertions.
- Print uses @lectio/page; Learn uses @lectio/learn.
- Explicit path state, revision checks, targeted retries, immutable releases, teacher edit preservation.

## Execution
1. Reconcile baseline and create tracking files in a repository docs location, proposed docs/unit-native-program/. Do not treat this pack's JSON examples as existing application data.
2. Execute phases P00–P09 according to dependencies. Use small coherent implementation commits, following repository policy. A phase may have multiple commits.
3. Before coding a phase, map each gate to intended tests. Reuse existing tests where they actually exercise the change.
4. Implement, test, inspect and repair. No diagnostic suppression, test deletion, fake plan substitution, or assigning expected IDs/scores to make tests pass.
5. Update state, gate CSV and phase report after each phase and before interruption.
6. At P09, run real providers through the normal product flow, on designated test data. Test teacher approval is allowed for this campaign; do not publish or assign to real learners.
7. Continue until all required gates pass or an actual external blocker remains. Complete independent work while blocked. Report exactly what is needed; never invent results.

## Speed and quality
Keep working implementations. Extract semantics from the existing Print planner rather than writing an unrelated planner from scratch. Use generated schemas and generic dispatch where appropriate. Do not microservice this refactor.
Batch independent file reads and use rg to locate code. Run focused tests while implementing; broader gates at integration. Reuse passing evidence unless later edits affect it. Measure stage latency and retries, not guess.
Keep runtime secrets out of reports. Use configured generation providers; this executor choice does not authorize migrating application providers.

## Completion
Return changed areas, commits, migration notes, phase/gate summary, actual commands, live run identities and evidence, capability readiness/deferred items and remaining blockers.
Core dual-path acceptance and full-catalogue acceptance must be separate. No final 'done' if only mocks pass or Live is blocked.

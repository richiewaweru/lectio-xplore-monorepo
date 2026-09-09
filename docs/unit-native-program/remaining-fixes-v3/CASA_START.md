# Casa execution prompt — remaining fixes v3

Implement the attached Lectio Remaining Fixes v3 pack on richiewaweru/lectio-xplore-monorepo, branch feat/unit-print-learn. Baseline reviewed: db157f0. Inspect current head and preserve all later fixes and dirty work. This is a focused completion round, not another architecture rewrite.

Read repository instructions, README.md, SPECIFICATION.md, acceptance/POLICY.md and REGRESSION_SCENARIOS.md. Read the existing Authoring Correction v2 pack and reports. Execute phases R00–R05 in order. Before every phase write a concrete plan referencing current functions, required behavior and tests; then implement, verify, record evidence and commit. Continue autonomously without pausing for routine permission.

Five non-negotiable corrections:
1. Learn must author or faithfully preserve complete student-facing activities: prompt, config and required feedback. Planning briefs are not question stems. Trusted assessment/identity policy stays code-controlled.
2. Resolve only explicit approved-item references. Never take approved_items[0] when the work order declares none. Never expose the whole pool in a request or repair. Missing/incompatible sources fail before generation.
3. Connect actual pinned preparation objective/facts/learner context/dependencies to normal production. Remove hardcoded empty facts and add mode-specific completeness validation without rejecting legitimate optional emptiness.
4. Implement actual configured model selection for ambiguous legal shortlists in relevant Learn/Print production paths. Keyword overlap and hardcoded bonuses do not qualify as semantic selection. Preserve a valid existing sealed model decision without duplicate selection.
5. Replace overstated acceptance proofs with actual offline production, DB reload, publish/edit/v2, learner attempt and component-render tests. Deepcopy is not persistence, hash changes are not publishing, and one Print block is not dual-path completion.

Reopen affected A02/A04/A05/A06 gates before implementation; preserve historical logs. Every PASS needs exact behavioral evidence and tested commit. Do not weaken assertions, rename heuristics as compliance, mark required capabilities unavailable, skip mandatory checks or claim completion from a test count.

Mock only external boundaries. Test provider request inputs as well as outputs so fixed fixtures cannot conceal empty context. Demonstrate regressions against old behavior, then exercise normal routes using the corrected engine. Fix implementation defects exposed by these checks. Do not deploy, merge to main or modify production data.

Live verification remains deferred. Missing live access is not a blocker for these offline corrections. If an environment prevents a mandatory offline gate, record it as BLOCKED and continue independent feasible work; do not convert it to PASS or silently relabel it live-only.

Final handoff: commits, changed behavior, exact gate-to-test/evidence mapping, prior acceptance claims corrected, remaining blockers and future live checklist. Say 'Remaining fixes verified offline; live/model-quality verification deferred' only when all mandatory gates pass. Otherwise report incomplete with precise remaining work. Do not stop after planning, scaffolding or documentation.

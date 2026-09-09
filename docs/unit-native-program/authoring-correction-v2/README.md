# Lectio authoring correction pack v2
Prepared 2026-09-09. Implementation proposal, not implementation evidence.

Repository: richiewaweru/lectio-xplore-monorepo
Target branch: feat/unit-print-learn
Reviewed baseline: 998e9f36e75f81899a6405a5d199e2f246bcbf9c

Goal: package-owned authoring definitions consumed by a reusable writing engine, with faithful Print and Learn production from the same approved teaching revision.

Start with CASA_START.md, then ARCHITECTURE.md, phases/A00 through A06 and acceptance/GATES.csv. Each phase has a proposal and an execution prompt. Templates and example data are design artifacts, not drop-in production implementations or evidence of passing gates.

This pack carries forward unresolved defects from the previous corrective round. It supplements the original Unit Print/Learn pack. Current user instruction defers live verification; earlier requirements for live evidence remain deferred, not waived or silently passed. Resolve ordinary implementation details autonomously within these requirements. Preserve subsequent branch work. No requirement is attributed to a separate named acceptance framework: gates here encode the concrete expectations agreed in this conversation.

Phases: A00 baseline and failing regressions; A01 package definitions; A02 shared execution; A03 Print migration; A04 Learn authoring; A05 selection and ownership; A06 integrated offline acceptance.

Acceptance means all mandatory offline gates passed with evidence. Report real-provider generation quality and full live journeys separately as NOT_RUN. No deploy, merge to main, or production data mutation is authorized by this pack. Commit phase changes on the target branch; push only under the existing agent/session authorization.

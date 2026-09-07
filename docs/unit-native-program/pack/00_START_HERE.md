# Lectio Unit → Print + Learn implementation pack
Version 1.0 • Prepared 2026-09-07 • Target executor: Casa / Grok AI

## Outcome
Make package-owned capabilities flow through Unit planning, shared instructional planning, native production, and verified delivery in both Print and Learn. This is an implementation specification, not a claim that the changes have already shipped.

Repository: https://github.com/richiewaweru/lectio-xplore-monorepo
Working base: refactor/domain-ownership
Reviewed and reconfirmed head: 5d1563903a22d6d40e12a86dcc4d9021ca8202a3
Comparison main: a5e68a2e79d370ddc34691099deb5e086eb75319

## Start
1. Read 01_PROPOSAL.md and 02_SOURCE_REVIEW.md.
2. Read contracts/01_CAPABILITY_CONTRACT.md through contracts/04_RUNTIME_AND_RELEASE.md.
3. Read prompts/CASA_MASTER_PROMPT.md.
4. Execute phases/P00_BASELINE.md, then follow tracking/phase-plan.json.
5. Record results in tracking/STATE.json and a phase report copied from tracking/PHASE_REPORT_TEMPLATE.md.
6. Finish with verification/LIVE_PROTOCOL.md and verification/FINAL_ACCEPTANCE.md.

Paste prompts/START_CASA.txt into your implementation agent with this whole directory attached or extracted in the repository. Use prompts/RESUME_CASA.txt after interruptions.

## Authority and interpretation
The user's explicit instructions and applicable repository safety/ownership rules take precedence. Within this pack, the master prompt controls execution; contract documents control data meaning; phase gates control acceptance; examples are explanatory proposed data, not existing production schemas.
Use existing public contracts where they meet requirements. Concrete new names are targets and may be adjusted to match repository conventions without changing semantics. Document such adjustments.
Resolve stale repository documentation against current implementation and CURRENT_SYSTEM.md; record contradictions rather than silently obeying an obsolete architecture.
Do not recreate this proposal instead of implementing it. Do not treat mock integration as live proof.
No agents or provider-specific APIs are assumed. Casa/Grok is the implementation executor; retain the application's configured generation providers.

## Scope
Includes both packages, exported catalogues, shared vocabulary, preparation, teaching, native selectors/writers, persistence, Builder, publishing, PDF, Learn runtime, progress, and verification. Includes all newly added interaction shells in the readiness inventory and contract work.
Exclude unrelated product redesign, forced repository cleanup, public deployment, unrelated data changes, a new assessment research platform, and arbitrary intent expansion.
Spatial interactions must have a recorded readiness decision. Incomplete capabilities remain unavailable; this cannot be described as full catalogue completion. Core dual-path acceptance and full-catalogue acceptance are reported separately.

## Phase completion
A phase is PASS only with executable evidence for every required gate. BLOCKED is never PASS. Reuse focused verification unless a concrete dependent risk requires broader tests. Keep the work moving across successful phases without requesting routine confirmation.

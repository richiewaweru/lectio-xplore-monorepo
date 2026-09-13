# Lectio reliability and repository health implementation pack
Prepared 2026-09-12 for Casa by Grok. Status: PROPOSED; no implementation or live verification performed by the preparing agent.

Reviewed remote baseline: fix/treasure-joe-final-cleanup @ a6b75e33d2a56452e05033a510f86db1566891b2.
Other observed branches: fix/generation-spec-closeout @ 6f782e94769d0dfce34b2dd80d1d462a9c38bd04; fix/document-overhaul-correction @ db8390335c085eca084ed758fc154d43aed3af41; main @ cebb61f2073311b5f7fd2daca8c10ce81e8ed117. Do not assume main contains the cleanup.

## Start immediately with login
Run prompts/00_LOGIN_FIRST.md in the SAME environment and browser that will perform implementation verification. Establish authentication before long work. A cloud browser was connected during proposal preparation, but it contains only about:blank: NO Lectio login was established. Casa starts the local application with Docker and discovers its local URL from the repository configuration. That browser is not presumed transferable to Casa by Grok. Do not promise session lifetime; use normal supported refresh only.

## Reading and execution order
1. 01_PROPOSAL.md and 02_CODE_INSPECTION.md.
2. prompts/00_LOGIN_FIRST.md, then prompts/01_CASA_MASTER.md.
3. phases/P00 through P06, in order; each has mandatory gates.
4. 03_STRICT_GATES.md, 04_LIVE_VERIFICATION.md, 05_COMMANDS.md.
5. Fresh verifier uses prompts/02_VERIFIER.md after implementation.

The requested twelve tasks are mapped in 03_STRICT_GATES.md. PASS requires evidence; BLOCKED and NOT_RUN are never PASS. No automatic merge/deployment authorization is conveyed by this pack. Implement locally/on a work branch, preserve unrelated work, and prepare a reviewable result.

Deliverable structure: proposal, actual code findings, seven phase instructions, 24 strict gates, login-first and implementation prompts, independent verifier prompt, live proof protocol, command inventory, and tracking templates.

## Confirmed execution environment
Implementer: Casa by Grok. Application: local Docker services. Browser: local Chromium controlled by Playwright. Casa discovers the URL and establishes authentication first in that local session. No staging URL is required.

# Casa by Grok implementation prompt
Implement the twelve-task reliability/health round using this pack. FIRST execute 00_LOGIN_FIRST.md so the user can authenticate before sleeping. Reuse the same supported browser session for later live proof; never promise permanent or cross-environment access.

Read repository AGENTS.md, 00_START_HERE.md, 01_PROPOSAL.md, 02_CODE_INSPECTION.md and 03_STRICT_GATES.md. Reviewed baseline is a6b75e33d2a56452e05033a510f86db1566891b2 on fix/treasure-joe-final-cleanup. Inspect actual local branch/history; if newer work exists, record its relationship and rebase the plan onto it without discarding unrelated changes. Use an isolated work branch. Do not merge or publish production changes automatically.

Freeze architecture: shared Teaching Plan; six primitives; shared LLM composer and ordinary writer; closed upstream learner actions; native independent Print/Learn artifacts. Preserve Markdown prompt/YAML policy ownership, Learn interactions, Print paper behavior, stable sections and node IDs. Do not split shared authoring engines or reintroduce old components.

Execute P00–P06 in dependency order. First restore backend validation; then introduce minimal durable stage/admission contracts, checkpoints/bounded recovery, telemetry APIs and frontend separation. Read existing implementations before changing them. Reuse Print leases/transitions and eliminate actual retry multiplication in document/writer.py rather than layering another retry loop. Trace provider/SDK calls so the default is three actual calls total per work item including repair/fallback; persist consumption across resumes.

Allocate run and node/work-item identities before calls. Make repeated requests idempotent via caller-scoped keys and DB uniqueness, with changed payload conflicts and explicit regeneration. Persist checkpoints atomically, protect against stale workers, cancellation, incompatible versions and duplicate final effects. Keep model work outside long DB transactions. No cross-sibling mutations. Record media/fallback truthfully.

Expose durable status and replayable events. Frontend must have separate domain operation state, retain dirty edits on progress refresh, handle 409 conflicts, reconnect accurately and derive allowed actions from server state. Extract existing large controllers without a wholesale UI redesign.

For every phase write tracking/Pxx-REPORT.md and update STATE.json with exact tested commit, changed files, commands/cwd/exit, gate assertions and retained evidence. New tests must prove outcomes rather than mirror implementation. Do not delete coverage, add broad ignores/skips or downgrade gates. Baseline pre-existing failures still require fixing; label genuine external blockers honestly and continue independent work.

After implementation run 04_LIVE_VERIFICATION.md on exact final code, retaining real PDF and continuous Unit→Learn→attempt evidence plus Print edit/revision/409/PDF/sibling proof. Inject failures only in disposable verification environment. Keep injected and real-provider evidence separate. Full commands in 05_COMMANDS.md remain mandatory.

Give the completed branch and evidence to the independent verifier using 02_VERIFIER.md. Overall READY requires all G01–G24 PASS; otherwise NOT READY with exact blockers. Deliver reviewable changes and evidence, with no empty completion stamps or fabricated test results.

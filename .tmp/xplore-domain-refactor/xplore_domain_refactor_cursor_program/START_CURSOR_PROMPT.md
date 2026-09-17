You are executing the Xplore domain-oriented refactor in `C:\Projects\lectio`.

Unpack/read this refactor packet and begin with **R0 only**.

Before each phase:
1. reread all files under `permanent/`,
2. reread that phase's `CURSOR_PROMPT.md`,
3. read `docs/refactor-program/REFACTOR_STATE.md`,
4. read `docs/refactor-program/OWNERSHIP_MANIFEST.json`,
5. read the previous phase report.

This is a **behavior-preserving refactor only**. Do not implement any deferred runtime/security/analytics/UI fixes while moving code.

For each phase:
- inspect actual usage,
- plan source→destination moves,
- prefer mechanical moves,
- run all gates,
- write the phase report,
- update refactor state,
- stop.

Proceed to the next phase only when the current phase is PASS.

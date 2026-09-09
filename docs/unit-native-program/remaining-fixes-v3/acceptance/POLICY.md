# Strict gate policy
Statuses: NOT_RUN, IN_PROGRESS, PASS, FAIL, BLOCKED. No PASS_WITH_BLOCKERS. Live tasks remain separately DEFERRED.

A passing test name/docstring is not evidence that the named behavior occurs. Audit the body. A gate may map to multiple tests but every clause must be exercised. If legacy tests cover persistence, cite those exact tests and ensure they consume newly authored output where that is the requirement.

Require a before-fix failing regression or proof that the defect was already fixed. Keep isolated worktrees for baseline checks; never reset or destroy user work. Add assertions on input scope, output meaning, saved state and actual calls, not only types and hashes.

No gate waiver without an explicit user scope change. No forced capability disabling to reduce scope. No final payload injection as writer evidence, no direct DB edits as Builder evidence, no copied dictionary as reload evidence, no evaluator-only checks as rendering evidence.

All changes must preserve source ownership and published release immutability. Do not claim mocked provider tests establish real-model factual accuracy, distractor quality or overall lesson quality. Those remain future verification.

Each report includes actual tested commit and dirty worktree identity if relevant; exact command, exit code, evidence file and negative/positive assertions. Store clean logs without secrets. A commit containing only updated STATE does not imply its preceding code was retested.

Overall completion: all mandatory offline gates PASS -> 'Remaining fixes verified offline; live/model-quality verification deferred.' Otherwise -> 'Remaining corrective implementation incomplete' with exact blockers and next actions. Continue all feasible work before stopping.

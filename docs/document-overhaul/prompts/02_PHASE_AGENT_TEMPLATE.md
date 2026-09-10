# Phase Agent Prompt Template

Implement **Phase <X> — <title>** from the Lectio Document + Interaction Overhaul pack.

Before coding:
- read AGENTS/ENTRY/project/refactor workflow
- read the master implementation prompt
- read the phase file
- inspect every active file listed by the phase
- search all consumers of symbols you will change/delete
- record current branch + HEAD SHA
- run the focused baseline tests for this slice

Rules:
- follow the new architecture, not old lesson compatibility
- do not introduce adapter/fallback debt for retired ordinary components
- do not weaken contracts/tests merely to pass
- keep Print and Learn independent after Teaching Plan
- keep native details out of Teaching Plan
- document all moved/deleted files
- update the visible tracking checklist as work progresses

At completion return:
1. files added
2. files changed
3. files deleted
4. dependency changes
5. behavior changes
6. exact validation commands/results
7. unresolved risks
8. commit SHA
9. whether the phase gate is PASS or FAIL

Do not proceed to the next phase on a failed gate.

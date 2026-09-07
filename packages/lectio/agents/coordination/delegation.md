# Delegation and Handoff

How to assign work to subagents and hand off between sessions. The goal is clean boundaries and zero lost context.

## Delegating a Subtask

When assigning work to a subagent, provide all of the following:

```markdown
## Delegation

| Field | Value |
| --- | --- |
| Parent task | [link to PR, issue, or runbook] |
| Assigned by | [orchestrator identity] |
| Scope | [exactly what to do -- be specific] |
| Boundary | [what NOT to touch] |
| Deliverable | [what the worker should produce: code, tests, report] |
| Validation | [what commands to run to verify the work] |
| Done when | [specific condition for completion] |
```

**Rules**:
- Be specific about scope. "Implement the frontend" is too vague. "Add the /login route with Google OAuth, matching the design in the existing /onboarding route" is specific.
- Include the validation commands. Don't make the worker guess which tests to run.
- State what's out of scope explicitly if there's any ambiguity.

## Receiving a Delegation

When you receive a subtask:
1. Read the delegation carefully. Confirm you understand the scope.
2. If anything is unclear, ask before starting.
3. Stay within scope. If you discover something that needs fixing outside your scope, note it and report it back -- don't fix it yourself.
4. When done, write a status report (see below).

## Status Report (Worker → Orchestrator)

When completing a subtask:

```markdown
## Status Report

| Field | Value |
| --- | --- |
| Parent task | [link to PR, issue, or runbook] |
| Worker | [your identity] |
| Scope | [what was assigned] |
| Status | [complete / blocked / partial] |

### Changes Made
- [list of files changed and what was done]

### Validation
- [commands run and results]

### Blockers or Issues
- [anything that prevented completion or needs orchestrator attention]

### Recommendations
- [follow-up work, risks noticed, suggestions]
```

## Handoff Between Sessions

When you're ending a session and work will continue later (same or different agent):

```markdown
## Handoff

**What changed**: [files modified, features added, bugs fixed]

**Current state**: [what works, what doesn't, what's partially done]

**Validated**: [which checks pass, what was manually verified]

**Not done yet**: [remaining work, in priority order]

**Start here**: [specific file/function/test the next session should look at first]

**Risks**: [anything the next session should be careful about]
```

**Rules**:
- A handoff must be self-contained. The next agent should NOT need access to your conversation.
- Be honest about what's done and what isn't. Don't describe partial work as complete.
- "Start here" is the most important field. Don't make the next agent re-discover your context.

## Where to Put These Documents

- Delegation tickets: in the PR body or as comments on the tracking checklist
- Status reports: in the PR body or as responses to the delegation
- Handoffs: in a runbook file (`docs/project/runs/`) or in the PR body

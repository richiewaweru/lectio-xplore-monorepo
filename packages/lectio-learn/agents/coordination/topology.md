# Agent Topology and Coordination

How to organize work when multiple agents or sessions are involved. Read this before delegating or accepting delegated work.

## Default Model: One Orchestrator

For most tasks, one agent (the orchestrator) owns the work end-to-end:
- Owns the tracking checklist
- Makes scope decisions
- Runs final validation
- Writes the PR and handoff

This is the default. If you're working alone, you are the orchestrator.

## When to Delegate

Delegate to a subagent or parallel worker when:
- The task has clearly separable subtasks (e.g., backend + frontend can proceed independently)
- A subtask requires deep exploration that would consume the orchestrator's context window
- You need to parallelize for speed

Don't delegate when:
- The subtasks are tightly coupled and need constant coordination
- The overhead of explaining the task exceeds the time to just do it
- You're delegating to avoid understanding the problem yourself

## Orchestrator Responsibilities

The orchestrator:
- Defines the overall scope and success criteria
- Assigns subtasks with explicit boundaries (see delegation template below)
- Integrates results from workers
- Resolves conflicts between worker outputs
- Owns the final tracking checklist and PR
- Runs final validation after integration

## Worker Responsibilities

A worker (subagent):
- Works only within the assigned scope. Don't expand beyond what you were asked.
- Reports back with: what changed, what's validated, what's blocked.
- Does NOT merge, push, or modify the tracking checklist directly.
- Asks the orchestrator if scope is unclear or if you discover something outside your assignment.

## Dual-Lead Exception

Rarely, two agents may co-own work (e.g., one owns backend, one owns frontend). This still requires:
- One designated integrator who owns the final PR and merge
- Clear boundary: which files/modules each agent owns
- Explicit coordination points where they sync

## Communication Between Agents

Agents communicate through artifacts, not conversation:
- Tracking checklists in PR bodies or runbook files
- Commit messages that explain what and why
- Handoff notes (see `delegation.md`)

If you're passing work to another session, the artifact must be self-contained. The next agent should be able to pick up without access to your conversation history.

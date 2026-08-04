# Communication

Rules for commit messages, PR descriptions, handoffs, and decision records. Clear communication is how you keep a project understandable over time.

## Commit Messages

Format: `type(scope): summary`

**Types**: feat, fix, refactor, docs, test, chore, ci, build
**Scope**: the subsystem or module affected (e.g., `auth`, `api`, `frontend`)
**Summary**: imperative mood, lowercase, no period. Explain *what* the commit does.

```
feat(auth): add Google OAuth login flow
fix(pipeline): handle empty input gracefully
refactor(domain): extract port interface from base provider
docs(project): update architecture rules after layer restructure
test(api): add integration tests for /generate endpoint
```

**Rules**:
- One logical change per commit. If you need "and" in the summary, consider splitting.
- The summary should be specific enough that someone reading `git log --oneline` can understand the change without looking at the diff.
- If a commit needs more explanation, add a body after a blank line. Keep it concise.

## PR Descriptions

A good PR description answers three questions:
1. **What** changed? (a brief summary of the actual changes)
2. **Why** was it changed? (the motivation -- bug report, feature request, tech debt)
3. **How** should it be verified? (validation steps, test commands, manual checks)

**Structure**:
```markdown
## Summary
Brief description of what this PR does and why.

## Changes
- List of specific changes (grouped by subsystem if applicable)

## Validation
- Commands run and their results
- Manual verification steps taken

## Risks
- What could go wrong
- How to roll back if needed
- Follow-up work created
```

**Anti-patterns**:
- Empty PR descriptions. Never.
- Descriptions that just repeat the commit messages. Add context.
- "See ticket" without any summary. The PR should stand on its own.

## Tracking Checklists

Every multi-step task needs a visible checklist (see `agents/workflows/` for templates). The checklist lives in the PR body or a runbook file.

**Rules**:
- Update the checklist as you work. Don't batch updates at the end.
- Record validation evidence inline: "Backend tests: 70 passed, 0 failed"
- Don't mark items complete until they're actually done.
- If you're blocked, note the blocker in the checklist.

## Handoffs

When handing off work to another agent, session, or human:

1. **What changed**: files modified, features added, bugs fixed
2. **What's validated**: which checks passed, what was manually verified
3. **What's left**: open items, known risks, follow-up work
4. **Where to start**: which file/function/test to look at first

A good handoff means the next person can pick up without re-reading the entire codebase.

## Decision Records

When you make a non-obvious technical decision, record it near the code:
- In a code comment if it's implementation-specific
- In the PR description if it affects the whole change
- In `agents/project.md` if it's a project-wide convention

Format: **Decision**: what you decided. **Reason**: why. **Alternatives considered**: what you didn't do and why not.

Don't record obvious decisions. Only record things that someone might question later.

## Visibility Hierarchy

| Surface | Contains | Audience |
| --- | --- | --- |
| Commit message | What and why for one change | Anyone reading git log |
| PR description | Summary, validation, risks for a set of changes | Reviewers |
| Tracking checklist | Detailed step-by-step progress | Current and next agent |
| Handoff | Final state and next steps | Next owner |

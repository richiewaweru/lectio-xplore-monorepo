# Bug Fix Workflow

Step-by-step playbook for fixing a bug. Keep it focused -- fix the bug, prove it's fixed, move on.

## 1. Understand the Bug

- What's the expected behavior?
- What's the actual behavior?
- Can you reproduce it? Under what conditions?
- What subsystem is affected?

## 2. Find the Root Cause

- Read the relevant source code. Trace the execution path.
- Check recent changes (`git log --oneline -20`) -- was this introduced by a recent commit?
- Don't guess. Understand *why* the bug happens before writing a fix.

## 3. Create Your Tracking Checklist

Copy this to your PR body or a runbook file:

```markdown
## Bugfix: [title]

**Classification**: minor
**Root cause**: [brief description of what's wrong]

### Progress
- [ ] Reproduced the bug (or identified the failing code path)
- [ ] Identified root cause
- [ ] Implemented the fix
- [ ] Added regression test
- [ ] Ran validation
- [ ] Self-reviewed the diff

### Validation Evidence
<!-- Paste test output showing the fix works -->

### Risks
<!-- Could this fix break anything else? -->
```

## 4. Fix It

- Apply the smallest targeted fix. Don't refactor surrounding code in the same change.
- Write a regression test that fails without the fix and passes with it. This is non-negotiable.
- If the fix requires changes in multiple places, check whether the bug has a deeper structural cause.

## 5. Validate

- Run all relevant validation commands from `agents/project.md`.
- Verify the regression test specifically tests the bug scenario.
- Check that no existing tests broke.
- Self-review: is the fix correct, minimal, and clear?

## 6. Communicate

- Commit message: `fix(scope): description of what was wrong`
- PR description: what the bug was, what caused it, how you fixed it, how the test proves it.
- Record validation evidence in your tracking checklist.

## 7. Done Criteria

- [ ] Root cause identified and documented
- [ ] Fix is minimal and targeted
- [ ] Regression test exists and passes
- [ ] All validation checks pass
- [ ] No unrelated changes in the diff

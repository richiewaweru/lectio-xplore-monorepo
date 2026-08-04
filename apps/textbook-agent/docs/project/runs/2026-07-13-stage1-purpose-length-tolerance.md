# Bugfix: Stage 1 purpose length tolerance

**Classification**: minor  
**Root cause**: Stage 1 treated the 80-character component-purpose writing guide as a hard Pydantic limit. Production output exceeded it, Pydantic AI exhausted output validation, and the application-level Stage 1 retry did not classify the current `output validation` exception wording as retryable.

### Progress

- [x] Reproduced the failing path from the Studio response and Railway logs
- [x] Identified the root cause
- [x] Implemented the fix
- [x] Added regression tests
- [x] Ran final validation
- [x] Self-reviewed the final diff
- [ ] Deployed and verified a real generation

### Validation Evidence

- Production generation `1b5fe830-3bbd-40be-a283-5c1d69649912` failed because two `ComponentSlot.purpose` values exceeded 80 characters.
- Focused planning/lifecycle tests: 29 passed.
- Focused Ruff: passed.
- Architecture check: passed after the final tolerance adjustment.
- Full backend suite: 381 passed, with the known unrelated skeleton-preview test failure.

### Risks

- Longer purpose text now flows into Stage 2 prompts; this matches Stage 2's existing guidance-first treatment of narrative brief text.
- Non-validation `UnexpectedModelBehavior` errors remain fatal and are not masked.

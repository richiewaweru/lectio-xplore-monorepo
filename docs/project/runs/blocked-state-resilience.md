# Bugfix: blocked-state resilience

**Classification**: minor  
**Root cause**: generic stage-2 exceptions were persisted as `assembly_blocked` without failed section IDs, leaving the teacher without a recovery action and relying on SSE to discover the state.

## Progress

- [x] Reproduced the bug (identified the generic stage-2 exception persistence path)
- [x] Identified root cause
- [ ] Implemented the fix
- [ ] Added regression tests
- [ ] Ran validation
- [ ] Self-reviewed the diff

## Validation Evidence

Pending implementation.

## Risks

The status contract is additive. SSE events and the planning resume/retry mechanisms remain unchanged.

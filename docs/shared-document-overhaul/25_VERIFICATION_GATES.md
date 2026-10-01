# Verification Gates

Every phase requires:

## Contract gate
Schema/invariant unit tests, hash fixtures, invalid-state rejection.

## Integration gate
Adjacent layers work together using real contracts.

## Failure gate
Deliberately break provider output, transport, leases, checkpoints, hashes and retries.

A happy-path-only phase is not PASS.

## Runbook evidence

Record:
```text
starting SHA
ending SHA
tests/commands
failure tests
live IDs if applicable
known limitations
deletion performed
guards added
```

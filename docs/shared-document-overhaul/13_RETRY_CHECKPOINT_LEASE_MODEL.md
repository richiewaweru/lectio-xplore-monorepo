# Retry, Checkpoint, Lease and Failure Model

## Retry layers

**Transport retry:** timeout, connection reset, 429/5xx. Infrastructure-owned, bounded/backoff-aware.

**Authoring repair:** malformed/invalid semantic output. AuthoringEngine-owned, bounded.

**Work-item retry:** after `failed_recoverable`; reacquires lease and reuses compatible healthy checkpoints.

**Regeneration:** creates a new artifact revision/run. It is not retrying a ready artifact in place.

## Checkpoint compatibility

Reuse only when these match:

```text
checkpoint schema
source revision
source hash
input hash
definition hash
composition identity
```

## Leases/fencing

Running mutable work items carry:

```text
lease_owner
lease_token
lease_expires_at
```

Late stale workers cannot commit over a newer fence.

## Failure contract

Every failure carries:

```text
error_code
error_class
retryable
stage
item_key
attempt
safe_summary
recovery_action
```

Suggested classes: validation, provider_transport, provider_output, source_conflict, lease_lost, budget_exhausted, unsupported_contract, internal_programming, cancelled.

Programming/auth/configuration errors never trigger semantic fallback.

## Sibling preservation

Retrying one section does not regenerate healthy sections. Learn failure does not mutate SharedDocument or Print; Print failure does not mutate SharedDocument or Learn.

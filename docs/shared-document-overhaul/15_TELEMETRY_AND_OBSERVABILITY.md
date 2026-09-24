# Telemetry and Observability

## Questions the system must answer

For any run:

1. Where is it?
2. What is active?
3. What is waiting?
4. What failed?
5. What can the user safely do next?
6. Which model/provider calls occurred?
7. Which exact source/output hashes were involved?

## Durable records

Persist:

- run status/stage transitions;
- work-item transitions;
- lease claims/loss;
- retry schedules;
- model calls;
- slot/resolved model;
- prompt/schema/policy hashes;
- tokens/cost where known;
- provider request IDs;
- latency;
- validation failures;
- final artifact identity/hash.

An in-memory ProgressStore may remain only as cache/projection.

## Status API

Return backend-authoritative:

```text
run_id
build_id
run_type
status
stage
completed/total
active_items
retry_schedule
latest_error
allowed_actions
source identity/hash
output identity/hash
links
```

Frontend does not infer legal transitions.

## Privacy

Redact secrets and learner responses from generic telemetry. Store only diagnostics required for operations.

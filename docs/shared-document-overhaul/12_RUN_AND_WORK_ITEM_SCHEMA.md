# Run and Work-Item Persistence

## Recommendation

Create generic runtime entities instead of stretching `NativeRealizationModel`.

## GenerationBuild

Correlation only:

```text
id
path_lesson_id
owner_user_id
created_at
```

## GenerationRun

Queryable columns:

```text
id
build_id
run_type
owner_user_id
status
stage
attempt

source_artifact_type
source_artifact_id
source_revision
source_hash

output_artifact_type
output_artifact_id
output_revision
output_hash

request_key

error_code
error_class
error_summary
recovery_action

created_at
started_at
updated_at
completed_at
```

## GenerationWorkItem

```text
id
run_id
item_key
stage
status
attempt
max_attempts

input_hash
definition_hash
composition_identity

lease_owner
lease_token
lease_expires_at

checkpoint_json
output_json
output_hash

error_code
error_class
error_summary
recovery_action

created_at
started_at
updated_at
completed_at
```

Stable keys: `section:explain`, `boundary:explain->check`, etc.

## GenerationEvent

Append-only:

```text
id
run_id
work_item_id | null
seq
event_type
status
stage
attempt
error_code | null
safe_payload_json
created_at
```

Run/work-item rows are current-state authority. Events are history/telemetry, not an event-sourced state engine.

## Model-call trace

Persist run/work-item identity, slot, resolved provider/model, prompt/policy/schema hash, attempt, token/cost data if known, request ID and latency.

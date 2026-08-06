# State Machine and Worker Design

## Repository API

Add or extend methods equivalent to:

```python
class PageDocumentRepository:
    async def transition(self, *, expected: set[str], target: str,
                         event: str, error: dict | None = None) -> None: ...
    async def claim_execution(self, *, worker_id: str,
                              lease_seconds: int) -> bool: ...
    async def heartbeat(self, *, worker_id: str) -> None: ...
    async def release_execution(self, *, worker_id: str) -> None: ...
    async def load_block_results(self) -> dict[str, dict]: ...
    async def save_block_outcome(self, execution_key: str,
                                 outcome: dict) -> None: ...
    async def load_expected_writer_results(self, *, form_plan,
                                           variant_id: str): ...
```

## Execution metadata

Persist under `page_document_v2.execution`:

```json
{
  "worker_id": null,
  "attempt": 0,
  "claimed_at": null,
  "heartbeat_at": null,
  "lease_seconds": 90,
  "last_error": null
}
```

## Atomic claim

Claim only when the generation is queued or active with an expired heartbeat. Use an atomic guarded update or `SELECT ... FOR UPDATE SKIP LOCKED`. Exactly one worker may claim a generation.

## Heartbeat

- interval: 20–30 seconds;
- default lease: 90 seconds;
- a separate periodic heartbeat must continue during long LLM calls.

## Worker loop

```python
async def native_worker_loop() -> None:
    while running:
        job = await claim_next_job()
        if job is None:
            await asyncio.sleep(2)
            continue
        try:
            await execute_generation(job)
        except Exception as exc:
            await persist_worker_failure(job, exc)
```

A worker crash leaves a stale lease that another process can reclaim.

## Structured error

```json
{
  "type": "APIConnectionError",
  "code": "PROVIDER_CONNECTION",
  "message": "Connection reset by provider",
  "stage": "writing_blocks",
  "section_id": "explain",
  "block_id": "explain-b2",
  "execution_key": "explain:explain-b2:everyone",
  "attempt": 2,
  "retryable": true,
  "recorded_at": "..."
}
```

Never persist only an empty string.

## Legal transitions

```text
awaiting_teaching_approval → queued
queued → planning_forms
planning_forms → writing_blocks
writing_blocks → assembling
assembling → awaiting_visuals
assembling → ready
awaiting_visuals → ready
planning_forms/writing_blocks/assembling → failed_recoverable
planning_forms/writing_blocks/assembling → failed_terminal
failed_recoverable → queued
any nonterminal → cancelled
```

Invalid transitions fail and record an invariant error.

## Idempotency

- repeated accepted approval returns current state without duplicate execution;
- persisted form plan is reused;
- ready blocks are skipped;
- a persisted ready document is a no-op;
- visual callbacks are idempotent by request ID.

## Shutdown

Stop claiming new jobs, allow a short drain, stop heartbeats, and leave unfinished work reclaimable after lease expiry. Do not mark it terminal merely because the process is shutting down.

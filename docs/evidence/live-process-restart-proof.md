# Live process-restart proof

Date: 2026-08-16

Generation: `9d863b9a-360b-4aea-ba43-b7769e000fce`

This generation was created and advanced through the authenticated normal UI.
It reached section writing in Studio. The backend process listening on port
8000 was terminated at `2026-08-16T22:34:04.8509987+03:00` (PID `28356`). A
new backend process was started and reached `/health/ready` with a new runtime
instance ID `4f900d72-5090-4e56-98be-398c4b07276f`.

On the first restart sweep, the persisted generation was reconciled as:

- top-level status: `failed_recoverable`
- error code: `v3_interrupted_by_restart`
- error type: `server_restart`
- UI message: `Generation was interrupted. You can resume from where it left off.`

The UI `Resume generation` action was then used. The resumed generation
advanced to `awaiting_teaching_approval` with no terminal error. This proves a
literal process kill, startup reconciliation, user-visible recovery state, and
checkpointed resume for this run. The run was interrupted before visual work;
this is restart/resume evidence, not a visual-QC acceptance run.

The same generation was then approved through the UI and reached native
`writing_sections` with `work_kind=post_approval_execution`. The backend was
terminated again at `2026-08-16T22:52:01.3195627+03:00` (PID `8396`). After
restart, the worker reclaimed the checkpoint and surfaced the real retryable
writer failure in the UI rather than leaving the lesson spinning. The UI
`Retry generation` action resumed only that failed stage, and the generation
reached top-level `ready` with four document sections. The ready viewer route
and `Download Final PDF` control were present after reload.

Finally, a second UI-created generation (`69d5ec98-03db-4d94-ba7f-49f6e77dca6a`)
was used for the provider-call boundary. Backend logs showed a DeepSeek
request body sent at `19:58:56.617Z`, response headers at `19:58:57.433Z`, and
the response body still being received when the backend was killed at
`2026-08-16T22:59:26.9146087+03:00` (PID `4124`). After restart, the worker
reclaimed the teaching checkpoint: the old lease was replaced by lease token
`2` under worker `native-6a6667614fd4`. The retry ultimately reached
`awaiting_teaching_approval`, proving provider-call interruption recovery
without losing the prior structural checkpoint.

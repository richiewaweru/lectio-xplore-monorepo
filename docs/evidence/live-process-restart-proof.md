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

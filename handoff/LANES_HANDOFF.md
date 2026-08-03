# LANES_HANDOFF.md — SUPERSEDED

**Status:** superseded entirely by [`RESHAPE_HANDOFF.md`](RESHAPE_HANDOFF.md) (2026-08-03).

Do not implement the writer-queue / supervisor / drain design described in this file's former §5. That approach was abandoned in favour of append-only `generation_steps` storage. Lane step count is decided by the Phase 0 expander experiment in the reshape handoff.

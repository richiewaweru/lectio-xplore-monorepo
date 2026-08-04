# LANES_HANDOFF.md — SUPERSEDED

**Status:** superseded entirely by [`RESHAPE_HANDOFF.md`](RESHAPE_HANDOFF.md) (v2 — post-decision, 2026-08-03).

Do not implement the writer-queue / supervisor / drain design described in this file's former §5. That approach was abandoned in favour of append-only `generation_steps` storage. The expander lives; lanes are 3-step (`brief → prose → questions`). Ignore any v1 reshape draft that removed the expander.

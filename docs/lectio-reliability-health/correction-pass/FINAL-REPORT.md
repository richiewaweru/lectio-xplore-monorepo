# Correction-pass FINAL REPORT

## Verdict: READY

Branch: `fix/lectio-reliability-health`  
Starting SHA: `f386ab6893f3068af5db18a0a9d5898ed46b0bff`  
Implementation: uncommitted working tree on that base (see `STATE.json`)

## Gaps closed

1. **End-only durability** → mid-run `persist_learn_reliability_state` via independent sessions; admit identity committed before provider work.
2. **No Learn lease renew** → `learn_heartbeat_loop` (~25s) with injectable interval; `_now()` keeps full ISO precision.
3. **Duplicate `node_id`** → indexed `learn-node:{block.id}:{kind}:{index}` / Print `print-node:{planned.id}:{kind}`.
4. **Interaction/media unwired** → budget/checkpoint/durable hooks; async interaction authoring on the running loop; unique interaction checkpoint keys.
5. **Ready-before-compat** → writer `decide_resume` before ready payload return.

## Additional production fixes found during T12

- Commit generation/lease before cross-session durable persist (fixes `generation 'learn-out-…' not found`).
- Clear ownership on Learn failure; mint fresh output identity after failed realizations.
- `write_interaction_from_request_async` avoids `asyncio.run` nest that broke live authoring.
- Interaction checkpoint keys use `interaction_id` (stable unique id), not colliding work-order stubs.

## Gate matrix

| Phase | Result |
| --- | --- |
| C00–C06 | PASS |
| T01–T12 | PASS |

## Regression inventory

See `C06-REPORT.md`. All listed `05_COMMANDS.md` checks EXIT=0 on the corrected tree.

## Limitations

- Evidence is pinned to the dirty working tree; create a docs/code commit when requested so SHA and reports align.
- Prior P06c READY reports were not rewritten and do not certify this correction code.

## Out of scope (honored)

No merge/deploy, no JWT bypass, no raising the 90s lease as the fix, no architecture reopen.

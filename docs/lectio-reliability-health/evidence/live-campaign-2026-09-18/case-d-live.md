# Case D — visual concept

Status: `BLOCKED`

## Durable identities

- Unit: `d6b4920c-317c-468c-86ed-6e3cdd510918` — Balanced and Unbalanced Forces
- Lesson: `8c376703-68d3-4fff-b6ba-e91397d91c2d`
- Historical preparation: `f66a8848-f6ad-4fba-b7fe-8aefeec134a0`
- Learn output: `learn-out-c66150d558b9`, ready
- Learn Teaching Plan revision/hash: `1` /
  `346bb789ab3e887bb269af21811417c7201f663cd9db28bac18a8d41`
- Print output: `f66a8848-f6ad-4fba-b7fe-8aefeec134a0`, still queued

## Observed live result

- Learn creation succeeded through the normal UI and rendered figures, tables,
  and 18 nodes. Learn was published and assigned to the campaign class.
- The Print route loaded but displayed `Figure pending`, and the underlying
  Print realization remained queued.
- Before the repair, the Plan output card incorrectly presented a queued Print
  row with an output ID as ready. The frontend mapping was corrected so queued,
  running, and preparing statuses remain `preparing` even when an output ID is
  present. The targeted regression test passes.
- After hot reload, the live Plan correctly showed `Print · preparing` and the
  preview continued to expose the pending figure. This is truthful failure/
  in-progress handling, not a successful Print result.

## Exact unblock action

Complete or retry the visual Print realization with the configured visual
provider/model enabled, then rerun Print preview, both PDF editions, visual PDF
inspection, publishing/assignment confirmation, and learner consumption. If the
visual provider remains unauthorized, retain this gate as BLOCKED and record the
provider-account/model permission required.

## Not claimed

No successful D Print output, PDF visual QA, or D learner completion is claimed.

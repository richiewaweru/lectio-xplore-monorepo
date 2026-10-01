# API and Status Contracts

Exact URLs may follow current conventions, but new product surfaces must be architecture-neutral rather than `/v3` branded.

Concepts:

```text
prepare lesson
approve Teaching Plan
start SharedDocument run
get run/build status
retry/cancel run
realize Learn
realize Print
publish Learn
export Print PDF
```

Universal status response includes:

```text
status
stage
active_items
completed
total
latest_error
allowed_actions
source/output identity+hash
links
```

Frontend polls/streams only while active. Stop at ready, awaiting_review, failed_recoverable, failed_terminal or cancelled until explicit user action changes state.

Retry identifies a run/work item; backend decides legal recovery scope.

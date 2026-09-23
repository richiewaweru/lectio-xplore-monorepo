# End-to-End Native Acceptance

The migration is not complete until the current product flow is proven after legacy code deletion.

Use the existing app, test fixtures, or a fresh small lesson. Prefer one known-good Unit/lesson and one newly created lesson if practical.

---

## Core proof

```text
Create/Open Unit
    |
    v
Path Lesson exists
    |
    v
Prepare lesson
    |
    v
Structural Plan appears
    |
    v
Approve Structural Plan
    |
    v
required item/source stage completes
    |
    v
Teaching Plan appears
    |
    v
Approve Teaching Plan
    |
    +--------------------------+
    |                          |
    v                          v
Create Learn               Create Print
    |                          |
    v                          v
ready/open                 ready/open
    |                          |
edit/save/reload           edit/save/reload
    |                          |
publish/release            export/PDF
```

Record IDs/status transitions sufficient to prove the workflow, but do not expose secrets/tokens.

---

## Required checks

### Preparation
- [ ] preparation starts once;
- [ ] structural plan is visible;
- [ ] structural review is actionable;
- [ ] approval advances to Teaching Plan generation;
- [ ] no legacy section writer is invoked.

### Teaching Plan
- [ ] Teaching Plan loads;
- [ ] revision/hash identity is present where expected;
- [ ] approval persists;
- [ ] refreshing retains approved state;
- [ ] requesting/retrying a failed teaching stage uses native retry semantics.

### Learn
- [ ] Learn realization is admitted from approved Teaching Plan;
- [ ] realization status progresses;
- [ ] Learn opens;
- [ ] ordinary document content renders;
- [ ] supported interactions render;
- [ ] edit/save/reload works;
- [ ] publish/release works if currently supported.

### Print
- [ ] Print realization is admitted from the same approved Teaching Plan;
- [ ] Print opens;
- [ ] ordinary document content renders;
- [ ] task treatments render;
- [ ] editor/save behavior works if currently supported;
- [ ] PDF/export completes.

### Visuals
- [ ] at least one figure path resolves through the moved `media/generation` implementation;
- [ ] visual failure/retry path is not wired to deleted V3 runtime;
- [ ] optional visual failure behavior remains as designed.

### Retry/reliability
Exercise at least:
- [ ] Teaching Plan recoverable retry;
- [ ] Learn realization retry;
- [ ] Print realization retry;
- [ ] visual retry if applicable;
- [ ] page refresh while status is in progress.

### Duplicate/identity safety
Do not weaken:
- [ ] Teaching Plan revision/hash pins;
- [ ] realization identity;
- [ ] current idempotency/admission handling.

---

## Negative proof

After the E2E run, search logs/code evidence to ensure the successful native flow did **not** invoke:
- old V3 section writer;
- old Stage 2 component writer;
- old V3 pack builder;
- old Studio generation runner.

---

## Final search proof

Record output for current-code searches:

```text
rg "v3_execution|v3_blueprint|v3_studio|V3[A-Z]" \
  apps/textbook-agent/backend/src \
  apps/textbook-agent/frontend/src
```

Each remaining match must be explained in the closeout report.

Also search:

```text
rg "execute_section|section_writer" apps/textbook-agent/backend/src
```

Desired production result: zero.

---

## Acceptance rule

The undertaking passes only when:

1. current native E2E works;
2. legacy execution files are actually removed;
3. current code no longer depends on legacy ownership;
4. remaining historical compatibility is explicit and inert;
5. the repo is simpler to explain than before.

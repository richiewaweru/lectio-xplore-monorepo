# Verification Gates

These gates are mandatory. A failed gate blocks progression.

---

## General gate protocol

For every phase:

```text
IMPLEMENT
   |
   v
STATIC CHECK
   |
   v
TARGETED TESTS
   |
   v
APP START / IMPORT
   |
   v
REPOSITORY SEARCH
   |
   v
GATE PASS?
  / \
 no yes
 |   |
FIX  COMMIT + NEXT PHASE
```

Never use "tests mostly pass" as a gate result. Record pre-existing failures separately.

---

## Gate evidence format

In `07_RUNBOOK.md`, record:

```text
Gate: B2 item extraction
Commit:
Commands:
- ...
Results:
- PASS ...
Search evidence:
- ...
Known pre-existing failures:
- ...
Decision: PASS / BLOCKED
```

---

## Static dependency gates

### After moving a survivor
Search the repository for the old import path.

Expected:
- current native callers = zero;
- only unfinished legacy code may remain until Phase E.

### Before deleting a legacy file
Must prove:
1. no current production import;
2. no dynamic import/string loader;
3. no router registration requiring it;
4. no current test contract that should be migrated instead of deleted.

### After deleting
Import/start the application immediately. Do not batch many deletions before checking.

---

## Native-path boundary gates

### Planning gate
Current path must resolve:

```text
application/unit_lesson
    -> curriculum/planning
```

not:

```text
application/unit_lesson
    -> v3_blueprint
```

### Authoring infrastructure gate
Current authoring must resolve:

```text
infra/authoring
    -> infra/*
```

not:

```text
infra/authoring
    -> v3_execution
```

### Media gate
Current media must resolve:

```text
learn/print
    -> media/generation
```

not:

```text
learn/print
    -> v3_execution.visual_executor
```

### UI gate
Current Unit Plan must resolve:

```text
Unit Plan
  -> lesson planning API
  -> teaching plan API
  -> realization API
```

not an omnibus legacy `$lib/api/v3`.

---

## Legacy deletion gate

Before old `section_writer` deletion:

```text
rg "section_writer|execute_section" apps/textbook-agent/backend/src
```

Every remaining production reference must either:
- be deleted in the same phase, or
- be proven current and migrated first.

Deleting only `section_writer.py` while leaving callers is a failed migration.

---

## Route gate

At the end of Phase D:
- native business logic must live under current routers/services;
- old `/v3` compatibility routes, if retained temporarily, must call current handlers only;
- legacy route code must not be required for application import.

At the end of Phase F/G:
- current frontend should not call legacy V3 routes unless explicitly justified.

---

## Persistence gate

Because historical generation records may exist:
- do not mutate persisted shape merely for naming cleanup;
- if a persisted field contains "v3" but is still required, document it as compatibility nomenclature;
- reading historical records must not require keeping the old generation engine executable.

This distinction is important:

```text
Historical data compatibility != historical execution compatibility
```

It is acceptable to preserve a parser/model needed to read old data while deleting the old writer/runtime that produced it, provided the parser is moved under current compatibility/document ownership.

---

## Test gate

Casa must inspect the repository to determine exact commands.

At minimum use:
- targeted unit tests for moved modules;
- backend route/service tests for native preparation/Teaching Plan/realizations;
- frontend page/API tests for Unit plan + Learn + Print;
- application startup/import;
- frontend build/type check if available.

Do not invent a command and mark the gate complete if the repository uses a different test runner.

---

## Commit gate

Each phase should end with a coherent commit.

Suggested pattern:

```text
chore(architecture): extract shared authoring infra from v3
chore(curriculum): move current planning out of v3_blueprint
refactor(api): move native lesson routes out of v3 studio
chore(legacy): remove retired v3 execution back half
chore(frontend): remove legacy studio generation surfaces
test(e2e): prove native lesson flow after v3 retirement
```

Exact messages are flexible; phase separation is not.

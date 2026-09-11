# Lectio Generation Closeout Pack

Repository: `richiewaweru/lectio-xplore-monorepo`  
Inspected baseline branch: `fix/document-overhaul-correction`  
Inspected baseline commit: `db8390335c085eca084ed758fc154d43aed3af41`

## Purpose

This is **not another architecture redesign**. The document overhaul is now substantially correct. This pack closes the remaining production gaps and turns the architecture into a reliably tunable product.

```text
Unit
 ↓
Teaching Plan
 ↓
explicit Print / Learn choice
 ├─────────────────────────────┐
 ↓                             ↓
PRINT                         LEARN
shared document composition   shared document composition
shared ordinary writing       shared ordinary writing
+ Print treatments            + retained interactions
 ↓                             ↓
editable Print artifact       editable Learn artifact
 ↓                             ↓
PDF                           web/runtime
```

Main goals:
1. make learner-action planning deliberate and tunable;
2. externalize mutable LLM behavior into Markdown;
3. externalize legal path mappings into YAML/JSON policy;
4. complete Print use of the shared document writer;
5. make Print admission symmetrical with Learn;
6. fix Learn figure serving and preserve section structure;
7. prove natural Unit-generated interactions in the browser;
8. add native Print artifact editing;
9. finish with strict evidence-based gates.

## Hard completion rule

A phase is complete only when its **canonical production path** uses the change and its gate passes. File creation, helper tests, mocks, or fixture proofs alone do not count.

Allowed gate states: `PASS`, `FAIL`, `BLOCKED`. There is no `PASS WITH DEFERRED DEBT`.

If live proof cannot run because a provider, browser, or database is unavailable, mark the phase `BLOCKED`.

## Branch rule

Start from the real current correction branch/merged equivalent, record the true SHA, then create a new implementation branch such as `fix/generation-spec-closeout`. Do not edit main directly.

## Read order

1. `01_LOCKED_DECISIONS.md`
2. `02_PROMPT_POLICY_ARCHITECTURE.md`
3. `03_ACTIVE_FILE_MAP.md`
4. `04_PHASE_SEQUENCE.md`
5. `05_STRICT_DEFINITION_OF_DONE.md`
6. `verification/FINAL_ACCEPTANCE_MATRIX.md`
7. `prompts/CASA_MASTER_EXECUTION_PROMPT.md`

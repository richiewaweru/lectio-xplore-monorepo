# Cutover, Coexistence, and Rollback

## 1. Feature flags

Recommended flags, adapted to existing settings conventions:

```text
XPLORE_PAGE_DOCUMENTS_ENABLED=false
# Accepted values: all | conceptual_first_exposure (emergency rollback)
XPLORE_PAGE_DOCUMENT_SCOPE=all
XPLORE_PAGE_WRITER_RETRIES=1
XPLORE_PAGE_SEQUENTIAL_PLANNING=true
```

The creation flag controls new generation. Reading existing v2 documents must remain enabled whenever the application ships the v2 renderer.

## 2. Creation routing

```text
flag off                        → v1 creation
flag on + scope matched         → v2 native creation
flag on + scope not matched     → v1 creation, explicit telemetry reason
v2 fails after commitment       → blocked v2 generation, not silent v1 fallback
```

A silent fallback after the user starts v2 would hide defects and make provenance false.

## 3. Read routing

```text
document_version=1 → legacy renderer
 document_version=2 → @lectio/page
unknown version     → explicit unsupported-document error
```

## 4. Database migration policy

Prefer the existing canonical JSON/document field and generation-state store. Add a database column only when no existing field can safely discriminate version and persist the final document.

If a migration is required:

- additive nullable/versioned fields only;
- no rewriting old rows;
- downgrade leaves v1 fields intact;
- backfill only metadata that can be derived without interpreting content;
- migration test covers old and new rows.

## 5. Rollback levels

### Level 1 — stop new v2 creation

Set creation flag false. Existing v2 documents remain readable.

### Level 2 — revert phase commit

Each phase is one or a small number of cohesive commits. Use the run report’s rollback SHA.

### Level 3 — restore monorepo import baseline

Tag: `pageobject-import-baseline`.

### Level 4 — independent source recovery

The original `C:\Projects\lectio - Copy` is never modified by bootstrap. The original GitHub repositories remain authoritative remotes.

## 6. Cutover gate

V2 may become default for the first scope only when:

- 30-section planner evaluation is acceptable;
- at least 10 full lessons complete on production-like infrastructure;
- deterministic validation failure rate is understood;
- no question-wall violation;
- browser/PDF smoke passes;
- reload/resume test passes;
- v1 read regression passes;
- rollback drill succeeds.

## 7. Cleanup gate

Delete legacy creator code only when:

- no current route imports it for migrated scope;
- no test fixture relies on it unintentionally;
- old documents still have a maintained reader;
- the deletion is isolated from runtime renames;
- the removal has a clear revert commit.

# Safe Monorepo Bootstrap

## Target

```text
C:\Projects\lectio\
├── .git\
├── package.json
├── pnpm-workspace.yaml
├── docs\implementation-runs\
├── apps\
│   └── textbook-agent\          imported from text-book-generator:xplore
└── packages\
    └── lectio-page\             imported from C:\Projects\lectio - Copy
```

The application directory is named `textbook-agent` because that is the requested path. Repository-internal documentation may still call the product Xplore.

## Why one root repository

A directory that contains two nested `.git` folders is a shared workspace, not a monorepo. It can be useful temporarily, but atomic changes across the page contract and consumer cannot be reviewed or reverted together.

The default bootstrap therefore creates a new root repository and imports both histories with `git subtree`.

## Safety rules

- Never move or delete `C:\Projects\lectio - Copy`.
- Never remove its `.git` directory.
- Refuse to import a dirty local Lectio source in history-preserving mode; uncommitted work must be committed or explicitly snapshot-imported.
- Refuse to overwrite a non-empty `C:\Projects\lectio`.
- Record both source HEADs before import.
- Clone/fetch `xplore` explicitly; never rely on the remote default branch.
- Create a root backup tag immediately after import.

## Recommended import

Run `scripts/bootstrap-monorepo.ps1` from PowerShell.

Default behavior:

1. verifies Git, pnpm, Node, Python, and `uv` availability;
2. checks the local Lectio source is a clean Git repository;
3. initializes `C:\Projects\lectio`;
4. imports the local Lectio HEAD into `packages/lectio-page` with history;
5. imports `text-book-generator:xplore` into `apps/textbook-agent` with history;
6. creates workspace metadata;
7. records source SHAs in `docs/implementation-runs/IMPORT_PROVENANCE.md`;
8. tags `pageobject-import-baseline`.

## Workspace package policy

The packages have distinct names: legacy `lectio` and new `@lectio/page`. They must coexist during migration.

Root workspace:

```yaml
packages:
  - "packages/*"
  - "apps/textbook-agent/frontend"
```

The app frontend keeps the legacy dependency until the v2 rendering phase. Later it adds:

```json
"@lectio/page": "workspace:*"
```

Do not replace `lectio` with `@lectio/page`; both are needed for v1/v2 reading.

## Root scripts

```json
{
  "scripts": {
    "page:test": "pnpm --filter @lectio/page test",
    "page:check": "pnpm --filter @lectio/page check",
    "page:pdf": "pnpm --filter @lectio/page pdf:fixture",
    "app:check": "pnpm --dir apps/textbook-agent/frontend check",
    "app:test": "pnpm --dir apps/textbook-agent/frontend test",
    "contracts:sync": "python apps/textbook-agent/tools/update_lectio_page_contracts.py",
    "verify:phase": "powershell -ExecutionPolicy Bypass -File scripts/verify-phase.ps1"
  }
}
```

Cursor must inspect actual script names and preserve the repository’s established package manager. It may adjust root wrappers, not replace working toolchains.

## Alternative: snapshot import

Use only when the local Lectio copy has essential uncommitted work that cannot be committed before the run. The snapshot mode:

- archives the entire source directory first;
- copies files but excludes `.git` from the destination;
- records a tree hash and source status;
- commits one import snapshot;
- does not claim history preservation.

This is a deliberate fallback, not an automatic recovery.

# A. Fork Plan — Fresh Lectio v2 Repository

## Executive decision

Create a fresh repository named provisionally `lectio-page` or `lectio-document`. Do not clone Lectio and delete its components.

The old repository structure encodes the component-first worldview in its folders, exports, tests, registries, templates, styles, and naming. Carrying that structure forward would make the old model the path of least resistance. A fresh repository forces the new system to begin with the document contract and paper behavior.

The old Lectio package remains installed only for rendering `document_version: 1` records. The new package renders only `document_version: 2`. There is no conversion between them.

## 1. Repository boundary

```text
lectio (legacy package)
└── renders document_version: 1 only

lectio-page (new package)
└── defines and renders document_version: 2 only

text-book-generator
├── old routes read v1 and use legacy Lectio
└── new generation routes create v2 and use lectio-page
```

This is version routing, not a compatibility layer. Old documents are not transformed. New documents never enter the old schema.

## 2. Scaffolding to carry

Copy only infrastructure that is neutral to the old content model.

### Build and package infrastructure

Carry:

- `package.json` scripts as a starting skeleton
- Svelte package build configuration
- `svelte.config.js`
- `vite.config.ts`
- `tsconfig.json`
- `vitest.config.ts`
- ESLint and formatting configuration
- package export-map structure
- CI workflow skeleton
- release/versioning workflow
- npm provenance and package metadata structure

Review every dependency. Do not carry UI dependencies merely because the old package used them.

### Utilities worth carrying after inspection

Carry only if they are independent and covered by tests:

- HTML sanitization utility
- safe Markdown-to-inline-content utility
- URL and asset sanitization
- KaTeX rendering wrapper
- stable ID helper
- contract export script skeleton
- JSON canonicalization helper
- test fixture loader
- Svelte action/utilities that are not component-specific

Copy the code into the new repository rather than importing legacy Lectio as a dependency.

### Test and development scaffolding

Carry:

- Vitest setup
- Playwright PDF smoke-test harness shape
- package smoke test
- contract snapshot test pattern
- visual regression directory conventions

Do not carry old expected snapshots.

## 3. Leave behind completely

Do not copy:

- all old Lectio rendering components
- shadcn cards or card wrappers
- `src/lib/schema/types.ts`
- `SectionContent`
- `src/lib/teacher/document.ts`
- `BLOCK_FIELD_ORDER`
- document conversion functions
- component registry
- component field map
- component metadata registry
- component-specific validators
- old template configurations
- print-mode context
- print branches inside components
- `print-theme.css`
- screen color presets
- behavior modes such as drawers, accordions, scrubbers, toggles, sticky panels, and carousels
- old component examples
- old component-specific prompt cards
- old print snapshots

The new repository must have no import from the old package.

## 4. Proposed repository structure

```text
lectio-page/
├── src/
│   ├── lib/
│   │   ├── contract/
│   │   │   ├── document.ts
│   │   │   ├── blocks.ts
│   │   │   ├── inline.ts
│   │   │   ├── intents.ts
│   │   │   └── validation.ts
│   │   ├── catalogue/
│   │   │   ├── objects.ts
│   │   │   ├── intents.ts
│   │   │   └── compatibility.ts
│   │   ├── render/
│   │   │   ├── LectioDocumentView.svelte
│   │   │   ├── SectionView.svelte
│   │   │   ├── BlockView.svelte
│   │   │   ├── HeadingBinding.svelte
│   │   │   └── objects/
│   │   ├── review/
│   │   │   ├── ReviewFrame.svelte
│   │   │   └── ReviewDocumentView.svelte
│   │   ├── print/
│   │   │   ├── base-print.css
│   │   │   ├── furniture.ts
│   │   │   └── presets.ts
│   │   ├── normalize/
│   │   │   ├── document.ts
│   │   │   ├── inline.ts
│   │   │   └── ids.ts
│   │   └── index.ts
│   └── routes/
│       └── fixtures/
├── contracts/
│   ├── lectio-document-v2.schema.json
│   ├── intent-catalogue.v1.json
│   ├── object-catalogue.v1.json
│   └── manifest.json
├── fixtures/
├── tests/
│   ├── contract/
│   ├── rendering/
│   ├── pagination/
│   └── package/
├── scripts/
│   └── export-contracts.ts
└── package.json
```

## 5. Development dependency without npm publication

Use a workspace/path dependency during the experiment.

Recommended local layout:

```text
workspace/
├── lectio-page/
└── text-book-generator/
```

In `text-book-generator/frontend/package.json`:

```json
{
  "dependencies": {
    "lectio": "0.3.x",
    "@lectio/page": "file:../../lectio-page"
  }
}
```

For pnpm, prefer a workspace:

```yaml
packages:
  - lectio-page
  - text-book-generator/frontend
```

Then:

```json
{
  "dependencies": {
    "@lectio/page": "workspace:*"
  }
}
```

CI should checkout both repositories into a known workspace location. A temporary Git dependency may be used for remote preview deployments:

```json
"@lectio/page": "github:richiewaweru/lectio-page#<commit-sha>"
```

Pin to a commit SHA. Do not point production previews at a moving branch.

## 6. Simultaneous installation and routing

Both packages may be installed because they have different package names.

```ts
import { LegacyLectioDocumentView } from 'lectio';
import { LectioDocumentView } from '@lectio/page';
```

The consuming app routes by persisted version:

```ts
switch (document.document_version) {
  case 1:
    return LegacyLectioDocumentView;
  case 2:
    return LectioDocumentView;
  default:
    throw new UnsupportedDocumentVersionError(document.document_version);
}
```

Rules:

- The v1 route is read-only except for existing legacy behavior.
- The v2 generation endpoint always persists `document_version: 2`.
- The v2 builder refuses v1 payloads.
- The v1 builder never imports v2 contracts.
- There is no `upgradeDocument()` function.
- No mixed v1/v2 blocks inside one document.

## 7. Source-of-truth contracts

The new repository exports:

- document JSON Schema
- object catalogue
- intent catalogue
- object-intent compatibility matrix
- contract manifest with hashes and versions

The textbook backend reads these from `LECTIO_CONTRACTS_DIR_V2`.

Do not reuse the old environment variable silently. A distinct variable makes accidental cross-loading detectable.

```text
LECTIO_CONTRACTS_DIR       → legacy v1
LECTIO_CONTRACTS_DIR_V2    → page-object v2
```

## 8. Release strategy

The experimental package begins at `0.1.0-experimental.0`.

Release gates:

1. Contract validates in TypeScript and Python.
2. Hand-authored fixture renders.
3. Chromium pagination suite passes.
4. One generated lesson renders end to end.
5. Comparison report is accepted.
6. Only then publish a stable `0.1.0`.

## 9. Failure modes

### Old UI primitives leak in

Reject any pull request importing old card, badge, carousel, accordion, or component registry modules.

### Package becomes a style kit rather than document engine

The public API must center on `LectioDocument`, validation, rendering, and exported contracts—not individual decorative components.

### Version routing becomes migration pressure

Do not promise indefinite support. Existing v1 documents age out according to pilot policy. New work happens only in v2.

### Local package drift

Every generated document stores:

```json
{
  "document_version": 2,
  "contract_version": "1.0.0",
  "renderer_version": "0.1.0-experimental.4"
}
```

This allows exact reproduction during the experiment.

## Done criteria

- Fresh repository exists.
- No legacy Lectio import exists.
- Package builds and installs locally beside legacy Lectio.
- v1 and v2 render routes can coexist.
- A v2 fixture validates and renders.
- Exported contracts are readable by the backend.
- No saved-document migration exists.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** B, D, E  

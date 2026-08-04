# @lectio/page

Print-native Lectio document engine.

The printed booklet is the product. Screen review is a thin layer around the same markup.

## Model

```text
10 page objects  ×  32 pedagogical intents
        ↓
ordered LectioDocument (document_version: 2)
        ↓
positive base-print.css (scholar's margin)
```

Objects: `heading`, `prose`, `list`, `table`, `figure`, `aside`, `worked-example`, `questions`, `choices`, `answer-key`.

Only `aside` may use a border. There is no `printMode` branch and no `@media print` stripping.

## Develop

```bash
pnpm install
pnpm dev
```

- `/` — deliverables index  
- `/fixtures/photosynthesis-ref` — reference booklet pages  
- `/objects` — object gallery  

```bash
pnpm check
pnpm test
pnpm export-contracts
pnpm pdf:fixture
```

## Contracts

Exported from `contracts/`:

- `lectio-document-v2.schema.json` (includes `front_matter`)
- `object-catalogue.v1.json`
- `intent-catalogue.v1.json`
- `base-print.css`
- `manifest.json`

## Architecture pack

See `docs/architecture/page-objects/` for the full A–G briefs and PATCH v1.1.

## Coexistence

Legacy Lectio (`document_version: 1`) remains in the original `lectio` package. This package renders only v2. There is no adapter and no saved-document migration.

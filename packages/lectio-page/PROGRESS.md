# @lectio/page — Page-Object Experiment Progress

Branch: `page-objects-v2` (from `xplore` @ f71e78c)  
Work folder: `C:\Projects\lectio - Copy`  
Legacy Lectio: `C:\Projects\lectio` (untouched)

## Gates

- [x] Wave 0 — Align + restore architecture pack
- [x] Wave 1 — Destructive scaffold (legacy deleted)
- [x] Wave 2 — Contracts + types + FIX 1 front_matter
- [x] Wave 3 — Geometry shell + v1.1 base-print.css
- [x] Wave 4 — Ten page objects
- [x] Wave 5 — Photosynthesis fixture + document renderer
- [x] Wave 6 — Web showcase + PDF gate
- [x] Wave 7 — Screen layer + FINDINGS.md
- [x] Catalogue v1.1.0 — discrimination + capacity fields

## Catalogue v1.1.0 acceptance

- [x] both `catalogue_version` fields read `1.1.0`
- [x] 8 objects have `earns_its_place_when`, `reject_when`, `capacity`
- [x] `heading` and `answer-key` objects unchanged
- [x] 11 intents have `choose_when` and `not_when`
- [x] `answer-key` intent has `selectable: false` and nothing else new
- [x] no `density` field anywhere
- [x] every `not_when` key is a valid IntentId
- [x] every `not_when` key shares ≥ 1 `valid_object` with its parent
- [x] `IntentRecord` / `ObjectRecord` updated; new fields optional
- [x] `isSelectable` / `listSelectableIntents` exported
- [x] `validation.ts` reads `aside.capacity.maxPerSection`
- [x] structural list/table/choices warnings (min sizes)
- [x] docs catalogue duplicates removed; pack points at repo-root `contracts/`
- [x] `pnpm check`, `pnpm test`, `pnpm export-contracts`, `pnpm pdf:fixture` pass

### Capacity vs photosynthesis fixture (measured)

| Limit | Fixture | Status |
| --- | --- | --- |
| aside ≤40 words, ≤2/section | 10–12 words; 1 per section | within limits |
| table 2–4 cols, 2–8 rows | 2×2 comparison table | within limits |
| 3 asides / 4-col table stress | not in fixture | deferred — no stress variant this pass |

Remaining 21 intent discrimination fields wait for selector integration.

## Meters

| Meter | Target | Current |
| --- | --- | --- |
| intents | 28–35 | 32 |
| objects | 10 | 10 |
| legacy imports in v2 | 0 | 0 |
| section_field in v2 | 0 | 0 |
| component_id in v2 | 0 | 0 |
| boxes outside aside | 0 | 0 (aside border only; figure plate uses hairline fallback) |

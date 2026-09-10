# Phase O — Full Verification Report

**Date:** 2026-09-11  
**Branch:** `refactor/document-model-overhaul`  
**HEAD SHA:** `1dabd746af65ac9d9272fcb7c49f000632407754`  
*(working tree includes Phases A–N changes not yet committed; SHA is current `git rev-parse HEAD`)*

## Command results

| Command | Result | Notes |
| --- | --- | --- |
| `pnpm contracts:test` | **PASS** | 3 files, 20 tests |
| `pnpm contracts:check` | **PASS** | Initially failed (`vocabulary.test.ts` possibly-undefined); fixed with non-null assertion on `pageCatalogue.intents[id]!`; re-run exit 0 |
| `pnpm page:test` | **PASS** | 11 files, 64 tests |
| Backend pytest (document/learn/print_learn/curriculum gates) | **PASS** | `36 passed, 1 warning` (`GenerationFieldContract.schema` name shadow — pre-existing) |

Pytest invocation:

```text
cd apps/textbook-agent/backend
uv run python -m pytest tests/document tests/learn \
  tests/print_learn/test_document_realizers.py \
  tests/print_learn/test_print_document_align.py \
  tests/curriculum/test_p02_shared_plan_gates.py -q --tb=line
```

Raw logs: `.tmp/phase-o-contracts-test.txt`, `.tmp/phase-o-contracts-check2.txt`, `.tmp/phase-o-page-test.txt`, `.tmp/phase-o-pytest.txt`, `.tmp/phase-o-zero-legacy.txt`.

## Architecture map (text)

```text
Unit → Concepts → PathLesson → Teaching Plan (curriculum/)
                              │
                              ├─ PRINT path
                              │    document primitives (src/document/)
                              │    → print/generation/document_realizer.py
                              │    → page objects / @lectio/page → PDF
                              │
                              └─ LEARN path
                                   document primitives + KEEP interactions
                                   → learn/generation/document_realizer.py
                                   → LearnDocument v2
                                   → Builder / Runtime / LearnRelease

Packages:
  @lectio/contracts  — instructional intents / learner actions
  @lectio/page       — Print page-document engine
  @lectio/learn      — retained interaction UI only (ordinary document path is app-owned)

FE Learn document canvas: frontend/src/lib/learn/document/
```

## Zero-legacy search

```bash
rg -n "component_lectio|ExplanationBlock|DefinitionCard|SectionContent|RuledLines|VideoEmbed|SimulationBlock" \
  apps/textbook-agent/backend/src apps/textbook-agent/frontend/src \
  packages/lectio-learn/src packages/lectio-contracts \
  --glob '!**/migrations/**' --glob '!**/*.md'
```

**Result:** ~358 matching lines (see `.tmp/phase-o-zero-legacy.txt`).  
**RuledLines:** zero matches in scoped trees (Learn-owned Print helper deleted in Phase M).  
**component_lectio:** production package deleted; remaining refs are retirement guards only (below).  
**@lectio/contracts:** zero matches for the search terms.

### Remaining matches — justification

| Bucket | Where | Justification |
| --- | --- | --- |
| Retirement / reject path | `learn/authoring/builder/{routes,service}.py`, `learn/generation/pipeline_dispatch.py` | Detect historical `component_lectio` rows and return 410 / retired errors — not a generation path |
| DB schema | `infra/database/models.py` partial unique index | Live DDL still matches migration `20260905_0034`; migrations excluded but model must keep predicate |
| Denylist | `document/composition.py` `LEGACY_LEARN_COMPONENT_IDS` | Prevents document composition from selecting retired content IDs |
| Historical SectionContent types | `contracts/section_content.py`, print PDF helpers, `v3_execution` validation, FE print studio adapters | Pre-overhaul Print/Studio SectionContent types still used by v3 pack/PDF surfaces; not Learn document generation |
| FE builder preview | `frontend/.../BlockPreview.svelte` | Still maps legacy component ids for opening historical builder content; new path uses `learn/document/` |
| FE SectionContent imports | print viewer/export, `parse-section.ts`, types, PrintSectionLink | Print/studio compatibility; student shell comments explicitly prefer ordered document blocks |
| `@lectio/learn` package | templates, ExplanationBlock, DefinitionCard, VideoEmbed, SimulationBlock, SectionContent schema, capabilities/content projection | **Deferred package debt (Phase N)** — interaction UI retained; ordinary content components not yet stripped. Production Learn generation does not select them |

## Overhaul gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Teaching Plan shared | **PASS** | `curriculum/teaching_plan/`; `tests/curriculum/test_p02_shared_plan_gates.py` in green suite |
| Document vocabulary | **PASS** | `backend/src/document/` (Paragraph/Heading/List/Figure/Table/Callout); `tests/document` |
| Path document realizers | **PASS** | `learn/generation/document_realizer.py`, `print/generation/document_realizer.py`; `tests/print_learn/test_document_realizers.py` |
| LearnDocument v2 | **PASS** | Native learn persistence / `learn_document` markers; learn tests green |
| Interactions KEEP set | **PASS** | KEEP set locked in OVERHAUL_STATE; `learn/interactions/`; capability KEEP interactions retained |
| Print mapping | **PASS** | `print/generation/document_form_map.py`, `PRINT_DOCUMENT_MAPPING.md`; `test_print_document_align.py` |
| FE document canvas | **PASS** | `frontend/src/lib/learn/document/` (DocumentCanvas + primitive renderers/editors) |
| Hard delete `component_lectio` | **PASS** | Package + obsolete tests deleted (Phase M); production dispatch cannot launch; remaining refs are reject/schema only |

## Overall status

**PASS with deferred debt.**

Required verification commands pass after the one-line contracts check fix. Production ordinary content generation is document-primitive based; `component_lectio` is unreachable as a live path. Remaining legacy string matches are justified (retirement guards, historical SectionContent Print/studio types, and deferred `@lectio/learn` ordinary-content package cleanup).

Not run in this phase (out of listed command set): live LLM Unit→Print/Learn end-to-end generations, clean-install checkout, full `pnpm app:test` / `program:domain-guards`.

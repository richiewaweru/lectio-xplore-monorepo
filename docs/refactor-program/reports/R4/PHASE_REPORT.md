# R4 PHASE REPORT — Prompts, Writers, Validators, Resources

Status: PASS

## Starting state
- branch: `refactor/domain-ownership`
- dirty state: R0–R3 domains present

## Move plan executed
| Source | Destination | Ownership | Notes |
|---|---|---|---|
| `contracts/lectio_page.py` (+ generated) | `print/contracts/` | PRINT | Fixed `_backend_root` parents depth |
| `contracts/lectio.py` | `learn/contracts/lectio.py` | LEARN | Shim exports `_EXTERNAL_FIELDS` |
| `contracts/lesson_document.py` | `learn/contracts/lesson_document.py` | LEARN | |
| `planning/page_blocks.py` | `print/generation/page_blocks.py` | PRINT | |
| `planning/page_projections.py` | `print/generation/page_projections.py` | PRINT | |
| `planning/catalogue_projections.py` | `print/generation/catalogue_projections.py` | PRINT | |
| `core/pdf_export_runtime.py` | `print/rendering/pdf/runtime.py` | PRINT | |

Left in place (shared / seam / not final product prompts):
- `contracts/document.py`, `section_content*`, `generation_manifest.py`, `template_contract.py`
- `resource_specs/loader.py|schema.py|renderer.py` (shared registry mechanics; candidates already under print/learn)
- `core/prompts/` loader infrastructure
- `generation/prompts.py`, `v3_studio/prompts.py`, `v3_execution/prompts/` (Studio-era; REMOVE_LATER / seam)
- `infra/` has no final product prompt modules (only a DB migration named prompt_overrides)

## Compatibility shims
Historical `contracts.*`, `planning.page_*`, `core.pdf_export_runtime` forward to print/learn paths (R7 removal).

## Behavior changes
Expected: NONE. Observed: NONE.

## Tests
| Command | Result |
|---|---|
| lectio_page contracts + page_object_writers + component_lectio_lifecycle + builder_lessons | PASS (40) |

## Import/dependency checks
- Print prompts/writers/resources discoverable under `print/`
- Learn contracts/resources under `learn/`
- `infra/` contains no final product prompts

## Ending state
- safe for next phase: YES

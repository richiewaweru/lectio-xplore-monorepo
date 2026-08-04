# Confirmed Baseline and Evidence

## Snapshot caution

The `xplore` branch was inspected by repository path and per-file blob through GitHub. This pack records confirmed files and symbols, but Cursor must still capture the exact local branch HEAD in Run 00 because the remote branch may advance.

## Confirmed Xplore paths

| Path | Confirmed role | Observed blob SHA |
|---|---|---|
| `backend/src/planning/bridge.py` | active approved-path lesson preparation; invokes component selector per skeleton slot, builds structural plan, persists generation | `f852913e58fbee6ce9c0d4f2da3f7228848e0174` |
| `backend/src/planning/agents.py` | structured LLM runner and current component/structural planners | `12d25bc80af88b3cbdb279f9e794fd51360de2` |
| `backend/src/planning/prompts.py` | prompt resource loader | `19467744c135d7c1467aa87ed937f20768a1525c` |
| `backend/resources/component-selector-v1.txt` | current slot-to-component selection prompt | `a2dd1a914244e09a634c246677c5f10e345a2d52` |
| `backend/resources/path-structural-planner-v1.txt` | current approved-path structural prompt; assumes component selection is already done | `82e614e3a44808f04235762fbec85b2588d9a836` |
| `backend/src/v3_blueprint/planning/models.py` | `ComponentSlot`, `SectionPlan.components`, and `StructuralPlan` | `24d2fe0a640f0217a75be7f8a1ebbe12b475fa6a` |
| `backend/src/planning/models.py` | `ComponentSelection`, `PathStructuralPlan` response models | `b1b55897e2e5dc771293d6d3d7212a7b6741ac98` |
| `backend/src/resource_specs/schema.py` | current component-oriented resource-spec schema | `41523267d72715ea6bd516952ec4d17f5d6ca74f` |
| `backend/src/resource_specs/renderer.py` | current prompt rendering for resource type, intent, depth, sections, components, and validation | `968fe13444833f6f41053775b6bc019035bae5d4` |
| `backend/resources/skeletons.yaml` | deterministic lesson shape and current `allowed_components` slots | `02423872bba8c5db4fa2354893fc170df947719f` |

## Confirmed page-library baseline

Baseline commit: `14ca43b5fac17f4c5a268eb626f3f96eac63a7be`.

| Path | Confirmed role |
|---|---|
| `contracts/lectio-document-v2.schema.json` | canonical JSON Schema for ordered v2 documents |
| `contracts/intent-catalogue.v1.json` | pedagogical intent catalogue, version 1.1.0 |
| `contracts/object-catalogue.v1.json` | page-object catalogue and capacities |
| `src/lib/contract/document.ts` | typed document discriminated union |
| `src/lib/catalogue/compatibility.ts` | object/intent compatibility and selectable-intent behavior |
| `src/lib/contract/validation.ts` | schema and semantic validation, including index/position equality |
| `src/lib/render/` | page-object rendering |
| fixture/Playwright pipeline | PDF generation and page-count checks |

## Current active flow

```text
skeleton slot.allowed_components
      ↓
planning.bridge component_selector(...)
      ↓
ComponentSelection
      ↓
structural planner receives component selections
      ↓
SectionPlan.components: ComponentSlot[]
      ↓
legacy writer/build/SectionContent path
```

The exact downstream writer and persistence symbols must be resolved in Run 00 using imports and tests. Cursor must not infer their names from this pack where the repository has changed.

## Known architecture facts from supplied handoff

- Planner order, builder field order, and print order currently diverge.
- The product path is the skeleton/component-selector path, not the free-generation planner palette.
- Projections read hardcoded component field names.
- Visuals attach to sections but lack committed block positions.
- Practice questions can be conditionally dropped when `practice-stack` was not selected.
- The new library validates ordered blocks and separates structure validation from semantic validation.

## Run 00 must resolve these exact owners

Before editing, locate and record:

1. the final legacy section-writer entry point;
2. the canonical persisted final-document field or state key;
3. the route that returns a generation document to the frontend;
4. the frontend component/route that renders generated lessons;
5. the existing PDF/export route and Playwright readiness signal;
6. the visual request model and completion writeback function;
7. the item-generation output store and question-to-section assembly function;
8. projection functions that read legacy component fields;
9. current SSE event names consumed by the frontend;
10. existing contract-sync tooling (`tools/update_lectio_contracts.py` or successor).

Run 00 must write these to `docs/implementation-runs/BASELINE_MAP.md` with exact paths and symbols. Later runs may not proceed without it.

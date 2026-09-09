# Reviewed source map
All links below refer to the reviewed baseline, not a promise about later branch state.
Base URL: https://github.com/richiewaweru/lectio-xplore-monorepo/blob/998e9f3/

| File relative to repository | Finding / intended action |
|---|---|
| packages/lectio-page/src/lib/catalogue/views.ts | Existing selection and writer projections. Extend rather than replace. |
| packages/lectio-learn/src/lib/learn/capabilities/views.ts | Existing capability writer projection. Add complete authoring definition. |
| packages/lectio-learn/src/lib/learn/capabilities/interactions.ts | Core readiness was promoted despite shortcut writers; re-evaluate readiness. |
| apps/textbook-agent/backend/src/print/rendering/page_objects/registry.py | Has provider/repair machinery, competing prompt construction, advisory contract fallback and table/figure exception fallback to stubs. |
| apps/textbook-agent/backend/src/print/rendering/page_objects/prompts.py | Active prebuilt prompt path; explicit specialized resource currently figure only. Consolidate package instruction loading. |
| apps/textbook-agent/backend/src/print/generation/whole_lesson/executor.py | Preserve worker behavior; connect actual dispatch to common engine. |
| apps/textbook-agent/backend/src/print/generation/work_orders.py | Existing scoped requests and contract hashes; include authoring instructions in identity. |
| apps/textbook-agent/backend/src/learn/generation/interaction_writer.py | Arbitrary answer heuristics; replace with faithful conversion/provider authoring. |
| apps/textbook-agent/backend/src/learn/generation/ordered_assemble.py | Writes briefs as final content and runs interaction writing inside assembly; separate authoring and assembly. |
| apps/textbook-agent/backend/src/learn/generation/native_production.py | Connect selected work orders to actual engine, then assemble. Audit temporary component hosting conversion against current renderer/editor contracts. |
| apps/textbook-agent/backend/src/learn/generation/native_execution.py | Normal persistence entrypoint must invoke corrected production. |
| apps/textbook-agent/backend/src/learn/generation/native_selection.py | First content choice and token-overlap interaction ranking remain. |
| apps/textbook-agent/backend/src/learn/resources/selection.py | Backend fallback map and incomplete fallback eligibility checks remain. |
| apps/textbook-agent/backend/src/learn/generation/component_lectio/payload_strategies.py | Audit reusable legacy authoring assets, not a reason to restore legacy orchestration. |
| apps/textbook-agent/backend/src/print/generation/whole_lesson/teaching_agent.py | Verify earlier missing-action/source ownership corrections and repair flow. |
| docs/unit-native-program/ | Update reports, readiness, gate results and state consistently. |

Existing Print prompt resources include prose-writer-v1.txt, list-writer-v1.txt, table-writer-v1.txt, worked-example-writer-v1.txt and figure-brief-writer-v1.txt under backend/resources. Compare their instructions with package guidance before consolidation; preserve useful teaching and formatting rules.

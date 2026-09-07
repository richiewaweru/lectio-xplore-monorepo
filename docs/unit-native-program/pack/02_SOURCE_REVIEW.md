# Reviewed baseline and uncertainty
Sources were inspected through GitHub in this conversation; branch head was reconfirmed during pack creation. No application tests or provider runs were executed to author this pack. Recorded D6 results are historical repository evidence.

All paths below are relative to the reviewed repository. Source links use the pinned commit:
https://github.com/richiewaweru/lectio-xplore-monorepo/tree/5d1563903a22d6d40e12a86dcc4d9021ca8202a3

| Finding | Source | Implementation consequence |
|---|---|---|
| Domain ownership exists | docs/architecture/CURRENT_SYSTEM.md | Build within curriculum/application/print/learn/infra |
| Recorded frontend build/check failures and two Learn test failures | docs/d6/TEST_MATRIX.md | P00 re-run, repair actual head failures |
| Unit preparation forces use_page_docs=True | apps/textbook-agent/backend/src/application/unit_lesson/prepare.py | Shared preparation must lose native shape assumptions |
| Variant synthesis can select first allowed component | same prepare.py | Create semantic slot instances only |
| Learn D6 test replaces prepared structural plan | apps/textbook-agent/backend/tests/routes/test_d6b_unit_learn_publish.py | Add uninterrupted production handoff test |
| Print integration uses fake plans/writers and avoids full assessment path | docs/d6/reports/D6A/PHASE_REPORT.md | Test approved items and live public export route |
| Reuse centers on lesson.pack_id | apps/textbook-agent/backend/src/application/unit_lesson/status.py | Separate preparation from path realization identity |
| Dispatch mixes native flags with component control | application/unit_lesson/dispatch.py; learn/generation/pipeline_dispatch.py | Explicit versioned native identity |
| Detailed teaching model is Print-owned | print/generation/whole_lesson/teaching_plan.py | Extract semantic contract, preserve existing execution |
| Learn exporter omits teachingIntent and web hints | packages/lectio-learn/src/lib/lectio/build-content-contract.ts | Complete exported contract |
| Learn candidate filtering is role/template/budget based | learn/resources/component_candidates.py | Add intent/action compatibility filtering |
| Student shell delegates through SectionContent/template | frontend/src/lib/learn/student/StudentLessonShell.svelte | Preserve arbitrary ordered blocks and repeated types |
| Publish validates broad shape | learn/publishing/release_routes.py | Full release validation and provenance rules |
| Attempts accept scores/outcomes/bindings | learn/runtime/runtime_service.py | Server-owned evaluation and binding |
| UI→attempt bridge, auth, passive completion and analytics debt | docs/d6/permanent/KNOWN_TECHNICAL_DEBT.md | Required learner delivery work |
| Entry project guide still names old architecture | apps/textbook-agent/agents/project.md | Reconcile authoritative guide in P00 |

## Earlier main evidence to re-check after rename
Print's catalogue has explicit valid_objects mappings and choose/reject guidance. Catalogue projections separate teaching/form/writer inputs. Learn component modules bundle metadata, schema and examples, but short-response evaluation was numeric and new interactions were outside classic generation selection.
Do not presume these remain unchanged; P00 inventory confirms their current locations and behaviour.

## Existing foundations to preserve
Path-owned objectives; optional approved misconceptions; concept identity; immutable release snapshots; stage checkpoints and recoverable failure handling; exact work orders; package-derived schemas; teacher edit persistence; Print native document rendering.

## Claims this pack does not make
It does not assert current live generation passes, that all interaction shells are complete, that D6 browser tests ran, or that proposed new schemas already exist.

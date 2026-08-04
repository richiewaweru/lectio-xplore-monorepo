# Review of the Supplied Claude Direction

## Executive judgment

The supplied work correctly identified several real requirements but arranged them around the wrong first milestone. It planned a horizontal selector foundation and explicitly stopped before the writer, document builder, renderer, projections, visual pipeline, and frontend. That would have produced a sophisticated decision harness without proving the application can generate a page-oriented lesson.

This pack retains the useful analysis and changes the implementation order.

## Accepted without material change

- Intent and object are distinct dimensions: intent is pedagogy; object is physical form.
- Resource vocabulary and skeleton vocabulary should narrow candidates by intersection.
- Candidate sets should be closed; `slot_concern` is preferable to a forced poor choice.
- Catalogue compatibility and capacity must be available in Python.
- `PlannedBlock` is the right replacement planning primitive.
- v1 and v2 documents should coexist without mass migration.
- Questions need explicit placement and should not be dropped because a particular component was absent.
- Visuals need stable block positions.
- Projections should eventually filter ordered blocks by intent rather than read hardcoded wide-record fields.
- The free-generation path is conceptually inconsistent with the approved-path product flow, but its deletion is deferred until the native slice is proven.

## Accepted with correction

### Candidate resolution

Keep resource × skeleton narrowing, but first migrate only the lesson/first-exposure conceptual route. Do not migrate every resource before the application can print one v2 lesson.

### Heading behavior

Keep heading structural and intent-free. However, generated section headings should come from `section.title`. The heading object remains for nested subheadings, not for repeating section titles.

### Catalogue bridge

Do not make production depend on `LECTIO_CATALOGUE_DIR` pointing outside the backend tree. Use a sync script that vendors generated contract snapshots into the backend. An environment override may exist for development verification.

### Prompt resource context

The model must know it is building a lesson, but the context should be assembled from `spec.id`, `spec.label`, `spec.intent`, text policy, runtime `prior_established`, lesson mode, and scope contract. It should not become a new `StanceSpec` unless a later deterministic consumer proves those fields need independent persistence.

## Rejected

### `StanceSpec` as a new persistent schema

The proposed fields duplicated existing ownership and mixed static resource identity with runtime learner state. In particular, `student_arrives_with` cannot be truthfully owned by a resource type when Xplore already computes actual prior established knowledge for each lesson.

### Two LLM calls for every block as the default architecture

The information barrier is theoretically clean but doubles calls, increases local-choice failure, and hides section composition from each decision. The first implementation uses one section-level planner, then deterministic checks. A/B evaluation may justify splitting later.

### Selector dry-run as the morning payoff

A dry-run remains useful, but the first product gate is a persisted and rendered document. The run harness is an intermediate verification tool, not the goal.

### Early runtime rename and deletion work

Renaming `v3_studio` and deleting routes expand the change surface without proving the new document path. Cleanup occurs after native output, not before it.

### Full resource migration before the first lesson

Worksheet and other resource vocabularies are postponed. The first lesson reveals whether the catalogue, writers, renderer, and persistence boundary are correct.

## Authority replacement

On conflicts, this pack replaces:

- the supplied overnight `BUILD_GOAL.md`;
- `PATCH_resource_stance.md` and its duplicate;
- `intent-selector-v1.txt` as the production selection strategy;
- `object-selector-v1.txt` as the production selection strategy.

Those documents remain valuable reasoning history and should be archived under `docs/history/`, not executed as current build instructions.

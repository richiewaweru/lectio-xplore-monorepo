# Water Cycle native visual handoff diagnostic

Date: 2026-08-11  
Unit: `ff30f847-dad2-4ab7-8335-b88a35c2b18a`  
Generation: `71ccd987-d562-4233-9c05-7268de3c842a`  
Status: parked at `awaiting_review`; not approved and not eligible as final proof

## Browser-native path

The run started through the authenticated product UI:

`/units` -> `+ New unit` -> constructor readback -> path planning -> path approval -> lesson 2
`Prepare Lesson` -> `/studio?generation_id=71ccd987-d562-4233-9c05-7268de3c842a`.

Input was the required Grade 6 Science Water Cycle instruction:

> Include a clear labelled diagram showing evaporation, condensation, precipitation,
> collection, and the movement of water through the water cycle.

No Builder, legacy conversion, hidden progression endpoint, or manual database progression was
used.

## Live blocker

Studio reached structural review, but all five sections displayed `No visual required`. Persisted
state confirms the diagram requirement survives in the unit destination, lesson objective,
`scope_contract.must_establish`, `signals.teacher_goal`, and resource specification. It is lost only
when the structural skeleton is materialized: every section is persisted with
`visual_required=false` and the question plan has `diagram_required=false`.

The generation was deliberately stopped before teacher approval, downstream execution, or visual
provider spend.

## Sol classification

`resources/skeletons.yaml` already declares the `visual.spatial_objective` modifier, but
`v3_blueprint/skeletons.py` hard-codes preview slots to `visual_required=False` and does not apply
that modifier. Structural generation and validation then accept the false value. This is an
implementation omission of the existing architecture rule.

Required recovery is a code fix followed by regeneration through the visible product workflow.
The parked generation must not be edited or approved in place.

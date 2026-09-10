# Decisions Locked Before Implementation

## Shared teaching ownership

The Teaching Plan is the last shared instructional commitment. It owns:
- ordered teaching moves
- intent
- concrete teaching brief
- learner tasks
- expected evidence
- difficulty
- concepts/objectives/misconceptions/source ownership where still useful

A learner task describes **what the learner should do**, never the UI mechanism.

Target minimum shape:

```text
learner_task
├── action
├── target
├── purpose
├── expected_evidence
└── difficulty
```

Do not put `Sort`, `Match`, `ruled_lines`, `Table`, `textbox`, or other native form identifiers in this shared contract.

## Shared document vocabulary

Only these ordinary content forms are first-class for this program:

```text
Paragraph
Heading
List
Figure
Table
Callout
```

Do not add another wrapper taxonomy such as ExplanationBlock/DefinitionBlock unless a future requirement proves unique behavior.

## Path ownership

Print and Learn both consume an approved Teaching Plan independently.

```text
Teaching Plan
     /   \
    /     \
 Print   Learn
```

They do not consume each other's final artifact.

## Interactions

A strict interaction contract is justified only when software behavior depends on it. Keep only proven interactions after inventory. Likely candidates already present in the repo include Choice, MultiSelect, FillBlank, Classify/Sort, MatchPairs, Sequence, Numeric and ShortResponse; the implementation phase must deliberately decide the final retained set.

## Print-only presentation

Keep these downstream of the Print boundary:
- pagination
- page breaks
- fixed page geometry
- PDF export
- ruled lines
- response areas
- working/drawing space
- Print-specific typography/layout

## Unsupported media

Delete current paths for video/simulation/other unsupported rich media rather than maintaining dormant abstractions.

## Legacy policy

No old lesson migration. No compatibility generation route. No legacy fallback at program completion.

Temporary transition code is acceptable only inside the implementation branch and must be removed before the final gate.

## Package policy

Package boundaries must earn their existence.

- `@lectio/page`: keep during this program because it contains real Print/page-engine machinery; extract or adapt only what the new architecture needs.
- `@lectio/contracts`: currently has a valid neutral vocabulary role; keep unless the implementation proves it unnecessary. Move canonical intent ownership out of Print so the shared contract is actually shared.
- `@lectio/learn`: current package is dominated by the old registry/component model. Migrate retained interaction/rendering code into the application or a much smaller interaction-only boundary, then remove the old package if no independent consumer remains.

# Model Slot Policy

## Hard rule

Reuse:

```text
ModelSlot.FAST
ModelSlot.STANDARD
ModelSlot.PREMIUM
```

plus the current ModelSpec/provider/environment-override/structured-output infrastructure.

Do not add another routing abstraction.

Current capability constants still carry V2/V3 names. Introduce truthful new capability names in the existing infrastructure, migrate callers, then delete obsolete V2/V3 capability constants.

## Recommended defaults

| Capability | Slot | Reason |
|---|---|---|
| Structural planning | STANDARD | global planning quality |
| Teaching Plan generation | STANDARD | pedagogy/continuity is high-value |
| Teaching Plan semantic validation | STANDARD | few, quality-sensitive calls |
| Shared task writer | FAST | narrow constrained output |
| Section Composer | STANDARD | consequential structure decision |
| Section Writer | STANDARD | main learner-facing content |
| Targeted section repair | FAST | narrow correction |
| Boundary continuity validator | STANDARD | subtle pedagogical check |
| Document semantic QA | FAST | deterministic checks dominate |
| Interaction shortlist selector | FAST | closed classification |
| Print treatment mapping | deterministic first | closed mapping preferred |
| Visual QC | FAST | constrained validation |
| PREMIUM fallback | none initially | require measured evidence |

## PREMIUM

No normal path should require PREMIUM initially. Add a narrowly scoped escalation only after acceptance data proves STANDARD is insufficient.

## Reasoning

Do not enable provider reasoning by default. Prefer typed schemas, closed vocabularies, deterministic validation and explicit outer repair.

## Domain isolation

Domain code requests an authoring capability. Infrastructure resolves slot/provider/model. Vendor model names do not belong in curriculum/document/Learn/Print code.

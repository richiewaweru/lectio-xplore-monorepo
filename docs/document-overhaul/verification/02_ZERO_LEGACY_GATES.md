# Zero-Legacy Gates

Run after Phase M and again in Phase O.

Search active source (excluding archived historical docs if archives are intentionally retained) for:

```text
component_lectio
ExplanationBlock
DefinitionCard
SummaryBlock
InsightStrip
KeyFact
PitfallAlert
SectionContent
componentRegistry
getComponentById
component_id
template_id        # inspect results; may have unrelated legitimate uses
VideoEmbed
SimulationBlock
RuledLines         # must not appear in active Learn ownership
```

Expected outcome:
- no retired ordinary content component in the active generation path
- no active fallback to component_lectio
- no Learn-owned Print response rendering
- no root/package scripts requiring deleted exports
- no generated backend contract refresh that recreates the retired component model

Also verify architecture imports:

```text
print → learn      forbidden
learn → print      forbidden
teaching → native ids forbidden
```

The final report must list every remaining match and justify it. "Historical documentation only" is acceptable only when clearly archived and not used by tools/runtime.

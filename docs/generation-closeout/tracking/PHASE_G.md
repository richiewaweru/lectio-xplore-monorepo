# Phase G — Natural live Learn interactivity + tabs

Status: PASS

## CHANGE
- Section tabs from realized LearnDocument `sections` (Builder + runtime list).
- Fix `OrderedDocumentList.svelte` broken `onSubmitInteraction` signature (Preview 500).
- Seed script `scripts/seed_closeout_g_builder.py` for opening produced Learn docs in Builder.

## LIVE PROOF
Natural Teaching Plan (ratio knowledge shape) → LearnDocument with **sequence** + **choice**
(`docs/generation-closeout/evidence/phase-g-ratio-learn.json`, `composition_mode=llm`).

Builder lesson `00e20258-050c-4078-86c1-e0dcaaccfc22` (`/builder/...`):
- Section tabs filter nodes (All / orient / explain / check).
- Sequence Check → correct feedback; Choice Check → correct feedback.
- Add paragraph → Save → Reload retains; Delete → Save.

Runtime (publish + attempts, same auth session):
- Release `8981d029-b113-4b16-9b50-139bdcf723ea`
- Instance `e2fd64b0-3963-49e1-ba91-8aeba485bb28`
- Sequence + choice attempts both `outcome=correct`; reload lists 2 attempts
  (`docs/generation-closeout/evidence/phase-g-runtime.json`).

Retained-kinds suite: `LIVE_INTERACTION_PROOF=PASS` (prior headed run).

Note: Unit UI Generate Learn on Ratios fell through to Studio when prep was
`failed_terminal` / teaching not approved — live interactions proved from the
same natural plan production path + Builder/runtime.

## STATUS
PASS

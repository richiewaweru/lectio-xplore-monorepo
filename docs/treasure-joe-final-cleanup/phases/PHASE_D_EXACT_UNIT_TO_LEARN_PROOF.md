# Phase D — Exact Unit To Learn Proof

## Goal

Prove the full user-facing Learn flow beginning at the Unit page.

## Tasks

- Create a fresh Unit likely to produce a learner action.
- Generate Teaching Plan normally.
- Approve it normally.
- Trigger Generate Learn from Unit UI.
- Verify canonical realize-learn endpoint.
- Verify LearnDocument v2 and composition_mode=llm.
- Open Builder from returned open_href.
- Verify a natural interaction.
- Submit/evaluate it and verify persistence after reload.
- Capture all relevant IDs.

## Gate

PASS only if Unit UI → Generate Learn → Builder → natural interaction → evaluation → persisted attempt completes without seed scripts, manual learner actions, DB edits, or failed-preparation Studio fallback.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED

# Phase B — Truthful Interaction Selection

## Goal

Make implementation match the claim: deterministic when obvious, LLM reasoning only when multiple legal candidates exist.

## Tasks

- Inspect candidate lists and current selector behavior.
- Keep one-candidate cases deterministic with zero LLM calls.
- For 2+ legal candidates, use a small structured LLM selector with interaction-selection.md.
- Expose only learner action, expected evidence, difficulty, context, and legal candidate names.
- Validate selected kind is legal.
- Record selection mode: deterministic_single, policy_default, or llm_multi_candidate.
- If no meaningful multi-candidate case exists, keep deterministic behavior and remove misleading LLM-selection claims.

## Gate

PASS only if prompt behavior and runtime behavior are truthful; no prompt may be loaded merely for hashing while unable to affect a claimed reasoning stage.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED

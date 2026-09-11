# Phase A — Close Learner Action Vocabulary

## Goal

Prevent Teaching Plans from containing learner actions that downstream paths cannot realize.

## Tasks

- Make learner-actions.yaml authoritative at planner validation time.
- Resolve aliases from YAML; do not duplicate the vocabulary in a Python enum.
- Unknown action must trigger planner repair/retry before approval.
- Resolve `describe-in-own-words` deliberately.
- Prove every canonical non-passive action has an intentional Learn and Print realization.
- Test canonical, alias, passive, and unknown actions.
- Run a fresh Teaching Plan proof.

## Gate

PASS only if no unknown learner action can enter an approved plan and silently disappear downstream.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED

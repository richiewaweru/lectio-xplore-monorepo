# Phase F — Repository Health And Finality

## Goal

Run every remaining gate and make tracking metadata final and honest.

## Tasks

- Run contracts/page/app/domain-guard commands.
- Run relevant backend tests and architecture validation.
- Run zero-legacy searches.
- Ensure intended clean git diff; exclude temp/capture noise.
- Commit implementation.
- Update tracking with real implementation/final tracking SHA(s).
- Run independent verifier.
- Do not claim remote CI passed if no checks exist.

## Gate

PASS only if all required commands are green, tracking contains real SHAs, no critical matrix item is falsely checked, and independent verifier recommends merge YES.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED

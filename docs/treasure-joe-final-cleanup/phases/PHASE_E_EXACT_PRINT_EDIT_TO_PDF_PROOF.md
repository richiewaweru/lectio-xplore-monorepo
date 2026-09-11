# Phase E — Exact Print Edit To PDF Proof

## Goal

Prove a native Print edit reaches the final PDF artifact.

## Tasks

- Open real LectioDocument v2.
- Insert a unique marker into an editable prose block.
- Save and verify revision increment.
- Reload and verify marker.
- Export/download actual PDF.
- Open or extract PDF text and verify marker present.
- Verify stale revision still returns 409.
- Verify Learn sibling unchanged.

## Gate

PASS only if actual PDF bytes visibly/textually contain the saved marker. A UI export status message is insufficient.

## Required evidence

- files changed/deleted
- exact commands/results
- canonical call graph
- positive live proof
- negative proof excluding prior wrong behavior
- PASS / FAIL / BLOCKED

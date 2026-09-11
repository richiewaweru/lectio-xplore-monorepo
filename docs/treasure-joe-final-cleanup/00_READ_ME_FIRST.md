# Lectio — Treasure Joe Final Cleanup

Repository: `richiewaweru/lectio-xplore-monorepo`  
Inspected branch: `fix/generation-spec-closeout`  
Inspected commit: `6f782e94769d0dfce34b2dd80d1d462a9c38bd04`

This is the **final architectural closeout**, not another redesign.

The remaining work is limited to six things:

1. Close `learner_action.action` against the file-backed vocabulary.
2. Make interaction-selection semantics truthful.
3. Remove the residual v1 Learn salvage path.
4. Prove the exact Unit → Generate Learn → Builder → interaction runtime path.
5. Prove a native Print edit appears in the actual exported PDF.
6. Run all repo gates and finalize tracking with real commit SHAs.

## Strict completion rule

A phase is complete only when:

```text
canonical production path
  → new behavior is actually invoked
  → positive proof passes
  → old/wrong behavior is excluded
  → PASS
```

Allowed statuses: `PASS`, `FAIL`, `BLOCKED`.

Forbidden: `PASS WITH DEBT`, `MOSTLY PASS`, `DEFERRED`, `GOOD ENOUGH`.

Recommended implementation branch:

```text
fix/treasure-joe-final-cleanup
```

# Migration and Clean Cutover

Temporary parallelism is proof infrastructure, not permanent product architecture.

```text
current path
   ├──────── new path shadow/proof
   │              ↓
   └──────── comparison
                  ↓
          acceptance gates pass
                  ↓
               CUTOVER
                  ↓
       new path sole creation route
                  ↓
          zero-caller sweep
                  ↓
               DELETE old
```

## No compatibility obligation

Do not create converters/readers simply to preserve historical generated artifacts or stale routes.

## Rollback

Use Git history, deployment rollback, DB backup/snapshot and additive build migrations.

Do not use “keep the old engine alive forever” as rollback strategy.

## Cutover requirements

- contract/invariant tests;
- failure injection;
- hash/restart/retry proof;
- SharedDocument quality proof;
- Learn end-to-end proof;
- Print/PDF proof;
- no major metadata leakage/continuity defects.

Deletion is part of the same program immediately after proof.

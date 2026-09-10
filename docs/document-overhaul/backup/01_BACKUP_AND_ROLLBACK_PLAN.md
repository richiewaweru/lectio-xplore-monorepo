# Backup and Rollback Plan

This overhaul intentionally deletes old production architecture and may delete old lesson data. Backups exist for **rollback safety**, not backward compatibility.

## 1. Immutable Git baseline

Before the first implementation commit, create a backup ref at:

`1dabd746af65ac9d9272fcb7c49f000632407754`

Recommended names:

```bash
git tag backup/document-overhaul-precut-2026-09-10 1dabd746af65ac9d9272fcb7c49f000632407754
git push origin backup/document-overhaul-precut-2026-09-10

git switch -c refactor/document-model-overhaul
git push -u origin refactor/document-model-overhaul
```

Do not implement directly on `main`.

## 2. Database backup before destructive persistence work

Immediately before Phase K/M destructive DB/data cleanup:

```bash
pg_dump --format=custom --file=lectio-pre-document-overhaul.dump "$DATABASE_URL"
```

Also record:
- database host/environment name
- migration head before change
- row counts for tables being dropped/truncated/reshaped
- SHA of the code that produced the backup

Verify the dump is non-empty and can be listed with:

```bash
pg_restore --list lectio-pre-document-overhaul.dump
```

If the deployment provider offers managed snapshots, create one in addition to the logical dump.

## 3. File/object/volume backup

Before deleting generated lesson artifacts or changing artifact paths:
- identify whether artifacts live in a mounted volume, local filesystem, object store, or DB
- copy/snapshot that storage once
- record the snapshot/copy identifier in the phase report

Do not guess that Railway/app storage is a persistent volume; inspect the deployment configuration first.

## 4. Implementation checkpoints

Use coherent commits at phase gates. Suggested high-level tags:

```text
overhaul/a-shared-contracts
overhaul/d-path-admission
overhaul/f-learn-document
overhaul/h-print-aligned
overhaul/m-legacy-removed
overhaul/o-verified
```

Tags are optional; clear commits plus the immutable pre-cutover backup are mandatory.

## 5. Rollback levels

```text
LEVEL 1 — phase rollback
git revert <phase commit(s)>

LEVEL 2 — branch rollback
reset/recreate implementation branch from last green phase

LEVEL 3 — full code rollback
deploy backup/document-overhaul-precut-2026-09-10

LEVEL 4 — data rollback
restore DB dump/provider snapshot + artifact storage snapshot
then deploy matching code SHA
```

Never restore old DB state underneath new code or new DB state underneath old code without checking schema compatibility.

## 6. Destructive-cutover rule

Phase M may delete legacy source only after:
- new Learn generation passes its focused gate
- new Print generation passes its focused gate
- new persistence save/reload passes
- backup artifacts are verified

Old lesson readability is not a gate.

# Phase H — Native Print editor

Status: PASS

## CHANGE
`PrintDocumentEditor` on `/studio/print/[id]`; GET/PUT `/lectio-document` with revision; JSON clone fix for LectioDocument.

## LIVE PROOF
Generation `8b855594-9577-44f1-8652-cf2a4dae699d`:
- View/Edit toggle works
- Prose edit with `CLOSEOUT_H_EDIT_MARKER` saved → revision 5
- Stale PUT expected_revision=0 → 409 `stale document revision`
- Download PDF → status "PDF export started"
- Learn sibling remains separate artifact

## STATUS
PASS

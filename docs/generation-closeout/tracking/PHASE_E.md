# Phase E — Symmetric realize-print

Status: PASS

## CHANGE
`realize_print_handoff.py`, `POST .../realizations:generate-print`, Unit UI calls handoff when prep exists (`pack_id` / preparation status).

## LIVE PROOF
Unit `303c8455-6812-4918-90d6-0503af082f2a` lesson `199fd8fa-…`:
- `generate-print` → 200, `open_href=/studio/print/8b855594-…`
- `generate-learn` → 200, separate `output_id=learn-out-9892160ce0e6`, `open_href=/builder/fa90ae02-…`
No conversion; sibling from same teaching plan hash.

## STATUS
PASS

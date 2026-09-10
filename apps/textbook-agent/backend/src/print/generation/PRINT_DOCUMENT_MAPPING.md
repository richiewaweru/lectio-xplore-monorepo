# Phase C — Print document form mapping

Print catalogue objects that are ordinary document forms map to the shared
vocabulary. Paper-only treatments stay in Print.

| Print object (catalogue) | Shared primitive | Ownership after extract |
| --- | --- | --- |
| `prose` | Paragraph | shared document + Print layout |
| `heading` | Heading | shared document (Print may still emit section chrome) |
| `list` | List | shared document + Print layout |
| `figure` | Figure | shared document + Print asset/PDF rules |
| `table` | Table | shared document + Print layout |
| `aside` | Callout | shared document + Print margin/placement |
| `worked-example` | *(Print task treatment)* | Print only |
| `questions` | *(Print task treatment)* | Print only |
| `choices` | *(Print task treatment)* | Print only |
| `answer-key` | *(teacher edition)* | Print only |

## Shared vs Print-only

**Shared (no pagination/PDF/ruled-line assumptions):**
- Choose among Paragraph / Heading / List / Figure / Table / Callout for a teaching block
- Node id + teaching_block_id provenance

**Print-only:**
- placement (`main` / `margin` / `spanning`)
- page breaks, geometry, ruled lines, response areas
- PDF stylesheet and page-object assembly

## Mapping helper

See `print/generation/document_form_map.py` for the runtime map used by the Print realizer.

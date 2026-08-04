# Run 09 Report

## Result
DONE

## Implemented
- Default `xplore_page_documents_enabled=true` for scope `conceptual_first_exposure`
- Other knowledge types / modes still use v1 creation (scope gate)
- Rollback: set `XPLORE_PAGE_DOCUMENTS_ENABLED=false` (v2 reads remain via document_version)
- No legacy renderer/contracts deleted; no runtime rename

## Rollback drill
1. Set env `XPLORE_PAGE_DOCUMENTS_ENABLED=false`
2. Restart API
3. New conceptual first-exposure preparations use component selector path
4. Existing `document_version=2` payloads still render via `@lectio/page`

## Tag
`pageobject-cutover-baseline` (created with this phase)

## Next
READY — RUN_10

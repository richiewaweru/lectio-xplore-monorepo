## Feature: Template Runtime Port for Preview Fidelity

**Classification**: medium  
**Subsystems**: frontend, lectio-integration, docs

### Progress
- [x] Understood the visual mismatch and confirmed the cause from both repos
- [x] Audited the current Textbook Agent preview/document rendering path
- [x] Audited the Lectio preview/runtime surface and theme layer
- [x] Ported Textbook Agent preview/document rendering to shared Lectio runtime surfaces
- [x] Restricted the product UI to the one fully wired preset and compatible templates
- [x] Added regression coverage for shared preview/runtime consumption
- [x] Updated handoff/setup documentation in the touched repos
- [x] Ran frontend validation for the consuming app
- [ ] Re-ran a clean Lectio package build without the local `.svelte-kit/__package__` lock
- [ ] Fixed pre-existing unrelated Lectio template-check errors outside this slice

### Summary

This pass fixes the main reason template previews looked visually flat in Textbook Agent: the app was only consuming Lectio's raw template render component and seeded preview data, not the wider runtime surface that gives Lectio templates their actual visual identity.

The implementation changed the integration model from:

- `template.render + app-local overlay chrome`

to:

- `Lectio theme layer + shared Lectio preview surface + shared Lectio runtime wrapper + real selected preset`

The product also now behaves more honestly:

- only `blue-classroom` is exposed as the live preset
- only templates that support `blue-classroom` are shown in the picker

That prevents the UI from advertising visual choices that are still only metadata.

### What Changed in Textbook Agent

| Area | Outcome | Primary files |
| --- | --- | --- |
| Theme consumption | The frontend now imports Lectio's shared theme stylesheet instead of relying only on local app styling. | `frontend/src/app.css` |
| Template preview overlay | The overlay now renders through Lectio's shared `TemplatePreviewSurface` rather than an app-local metadata shell plus raw template body. | `frontend/src/lib/components/TemplatePreviewOverlay.svelte` |
| Generation form | The picker now exposes only the live preset and templates that support it, preserving the same request shape while improving visual honesty. | `frontend/src/lib/components/ProfileForm.svelte` |
| Document renderer | Generated documents now render inside Lectio's shared runtime wrapper so preview and real document surfaces use one visual system. | `frontend/src/lib/components/LectioDocumentView.svelte` |
| Dashboard messaging | The dashboard copy now reflects the current live preset/runtime reality. | `frontend/src/routes/dashboard/+page.svelte` |
| Regression tests | Added coverage for shared preview surface use, live preset restriction, and shared document runtime wrapper use. | `frontend/src/lib/components/ProfileForm.test.ts`, `frontend/src/lib/components/LectioDocumentView.test.ts` |

### Why It Was Broken Before

- Textbook Agent was importing `template.render`, but not the rest of Lectio's visual system.
- Lectio's real look depends on shared theme tokens and utility shells such as `lesson-shell`, `glass-panel`, `eyebrow`, and the `primary`/`accent` token family.
- The old overlay was wrapping previews in app-local beige styling that flattened the template output instead of reinforcing it.
- Presets were mostly being treated as labels and outer-frame tint hints, not as actual applied theme state.

### Validation Evidence

| Command | Result |
| --- | --- |
| `npm test` in `frontend/` | `10 files passed, 29 tests passed` |
| `npm run check` in `frontend/` | Passed with `0 errors, 0 warnings` |
| `npm run build` in `frontend/` | Passed |

### Known Caveats

- `C:\Projects\lectio` still has pre-existing `npm run check` failures in `guided-discovery` and `interactive-lab`; these were not introduced by this work.
- A clean `npm run package` in `C:\Projects\lectio` hit a local lock on `.svelte-kit\__package__` during validation.
- The frontend build still emits the known non-blocking chunk-size warning and Svelte circular warning.
- Only `blue-classroom` is treated as live in-product right now; other preset ids remain part of the data model but are not exposed as working visual choices.

### Start Here Next Time

1. Review `frontend/src/lib/components/ProfileForm.svelte` for the current live-preset gating logic.
2. Review `frontend/src/lib/components/TemplatePreviewOverlay.svelte` and `frontend/src/lib/components/LectioDocumentView.svelte` for the new shared Lectio runtime consumption.
3. Review `C:\Projects\lectio\src\lib\theme.css`, `C:\Projects\lectio\src\lib\templates\TemplatePreviewSurface.svelte`, and `C:\Projects\lectio\src\lib\templates\TemplateRuntimeSurface.svelte` to extend the runtime contract cleanly.
4. If the next slice is preset expansion, implement a second real preset in Lectio first, then widen the product picker in Textbook Agent.

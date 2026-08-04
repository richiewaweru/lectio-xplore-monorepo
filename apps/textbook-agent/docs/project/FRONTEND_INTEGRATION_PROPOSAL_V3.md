# Frontend Integration Proposal — v3
**Grounded in actual codebase as of current state**
**Replaces:** v1 and v2 — both written without seeing the real code

---

## What the Real System Already Has

Reading the actual files reveals the system is significantly
more complete than either previous proposal described.

**Already built and working:**

```
Route: /textbook/[id]             ← not /generate (v1 was wrong)
Route: /dashboard                 ← generation form + history list

POST /api/v1/generations          ← starts generation, returns generation_id
GET  /api/v1/generations/{id}/events ← SSE stream (EventSource, not fetch)
GET  /api/v1/generations/{id}/document ← full PipelineDocument
GET  /api/v1/generations          ← history list

PipelineDocument                  ← canonical model (not flat SectionContent[])
  generation_id, subject, context, mode
  template_id, preset_id
  sections: SectionContent[]
  qc_reports, quality_passed
  status, created_at, completed_at

LectioDocumentView.svelte         ← renders sections using LectioThemeSurface
  LectioThemeSurface receives preset object (not preset_id string)
  templateRegistryMap[template_id].render → correct layout component

File document repo                ← saves PipelineDocument as JSON file
  (not Supabase tables as v1/v2 described)

SSE event types (fully typed on both sides):
  pipeline_start    → includes generation_id, section_count, template_id,
                       preset_id, mode — preset_id ALREADY PRESENT
  section_started   → section_id, title, position
  section_ready     → section_id, section: SectionContent, completed/total
  qc_complete       → passed, total
  complete          → document_url
  error             → message

Auth:                             ← Google OAuth + JWT, fully wired
StudentProfile:                   ← education_level, learning_style etc.
Generation history:               ← dashboard lists past generations
Enhance flow:                     ← draft → balanced/strict enhancement
```

**What this means for the previous proposals:**
v1 and v2 described building things that already exist.
The `LectioTemplateRenderer` we planned — already done as
`LectioDocumentView`. The dashboard — already done. The history
list — already done. The persistence — already done with the
file repo. The SSE stream — already done with EventSource.
The `preset_id` in SSE events — already present in
`PipelineStartEvent`.

---

## What Is Actually Still Missing

Three things. Only three.

---

### 1. Zod validation at the SSE boundary (Layer 4)

**Status:** Not present. The `section_ready` handler in
`/textbook/[id]/+page.svelte` does a raw cast:

```typescript
// Current — no validation
source.addEventListener('section_ready', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as SectionReadyEvent
    plannedSections = payload.total_sections
    upsertSection(payload.section)   ← payload.section is trusted blindly
})
```

**What to add:**

**File:** `src/lib/parse-section.ts` (new)

```typescript
import { z } from 'zod'
import type { SectionContent } from 'lectio'

// Validates the required structural shape.
// Optional fields (diagram, definition, worked_example etc.) pass
// through via .passthrough() — pipeline already validated them.
const SectionContentSchema = z.object({
  section_id:  z.string().min(1),
  template_id: z.string().min(1),
  header: z.object({
    title:      z.string(),
    subject:    z.string(),
    grade_band: z.enum(['primary', 'secondary', 'advanced']),
  }),
  hook: z.object({
    headline: z.string(),
    body:     z.string(),
    anchor:   z.string(),
  }),
  explanation: z.object({
    body:     z.string(),
    emphasis: z.array(z.string()),
  }),
  practice: z.object({
    problems: z.array(z.object({
      difficulty: z.enum(['warm', 'medium', 'cold', 'extension']),
      question:   z.string(),
      hints:      z.array(z.object({
        level: z.union([z.literal(1), z.literal(2), z.literal(3)]),
        text:  z.string(),
      })),
    })).min(2).max(5),
  }),
  what_next: z.object({
    body: z.string(),
    next: z.string(),
  }),
}).passthrough()

export function parseIncomingSection(raw: unknown): SectionContent {
  const result = SectionContentSchema.safeParse(raw)
  if (!result.success) {
    const first = result.error.errors[0]
    throw new Error(
      `[Lectio] Invalid section from pipeline `
      + `at '${first.path.join('.')}': ${first.message}`
    )
  }
  return result.data as SectionContent
}
```

**Update the handler in `/textbook/[id]/+page.svelte`:**

```typescript
// Change this:
source.addEventListener('section_ready', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as SectionReadyEvent
    plannedSections = payload.total_sections
    upsertSection(payload.section)
})

// To this:
source.addEventListener('section_ready', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as SectionReadyEvent
    plannedSections = payload.total_sections
    try {
        upsertSection(parseIncomingSection(payload.section))
    } catch (e) {
        console.error('[Lectio] Section validation failed:', e)
        // Section is skipped — pipeline continues
    }
})
```

**Dependency:** `npm install zod` in the frontend project.

---

### 2. `LectioThemeSurface` wiring in `LectioDocumentView`

**Status:** The component exists and uses `LectioThemeSurface`
correctly. But it depends on `LectioThemeSurface` being exported
from Lectio — which requires the runtime surface work to be
completed first (theme.css, surfaces exported from index.ts).

**Current `LectioDocumentView.svelte` already does this correctly:**

```svelte
<script lang="ts">
  import { LectioThemeSurface, basePresetMap, templateRegistryMap } from 'lectio'

  const template = $derived(templateRegistryMap[document.template_id])
  const preset   = $derived(basePresetMap[document.preset_id] ?? null)
</script>

{#if template}
  <LectioThemeSurface {preset}>
    ...
    {#each document.sections as section}
      {@const TemplateRender = template.render}
      <TemplateRender {section} />
    {/each}
  </LectioThemeSurface>
{/if}
```

**What is needed from Lectio before this works:**

```
1. LectioThemeSurface exported from src/lib/index.ts
2. theme.css with preset variable blocks created
3. package.json exports ./theme pointing at theme.css
4. npm run package rebuilds dist/
5. npm run sync in textbook agent updates node_modules
```

Once those Lectio changes are done, `LectioDocumentView` works
as-is with no changes needed in the textbook agent.

**Acceptance check:**
```bash
# In the textbook agent
npm run dev
# Navigate to /textbook/{completed_generation_id}
# Verify: sections render with correct colours (navy for blue-classroom)
# Verify: not a flat unstyled layout
```

---

### 3. `section_started` event handling in the textbook page

**Status:** The pipeline emits `section_started` (with title and
position) before each section generates. The frontend does not
handle it. This is the event that should show a skeleton or
loading state per section so the teacher sees progress.

**Current state in `/textbook/[id]/+page.svelte`:**

```typescript
// section_started is not listened for at all
// plannedSections is set from section_ready.total_sections
// There is no per-section loading state
```

**What to add:**

```typescript
// New state
let pendingSections = $state<Array<{id: string, title: string, position: number}>>([])

// New handler
source.addEventListener('section_started', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as SectionStartedEvent
    pendingSections = [...pendingSections, {
        id:       payload.section_id,
        title:    payload.title,
        position: payload.position,
    }]
})

// Update section_ready to remove from pending when section arrives
source.addEventListener('section_ready', (event) => {
    const payload = JSON.parse((event as MessageEvent).data) as SectionReadyEvent
    plannedSections = payload.total_sections
    pendingSections = pendingSections.filter(s => s.id !== payload.section_id)
    try {
        upsertSection(parseIncomingSection(payload.section))
    } catch (e) {
        console.error('[Lectio] Section validation failed:', e)
    }
})
```

**In the template, render pending sections as skeletons:**

```svelte
{#if document}
  <LectioDocumentView {document} />

  <!-- Sections in-flight but not yet ready -->
  {#each pendingSections as pending (pending.id)}
    <div class="section-skeleton" aria-busy="true">
      <p class="skeleton-title">{pending.title}</p>
      <div class="skeleton-body"></div>
    </div>
  {/each}
{/if}
```

This gives the teacher a meaningful loading state per section
rather than the current "Sections ready: N / M" counter.

---

## What the Previous Proposals Got Wrong

| Proposal claim | Reality |
|---|---|
| Need to build `/generate` route | Already `/textbook/[id]` + `/dashboard` |
| Need `LectioTemplateRenderer` component | Already `LectioDocumentView` |
| `preset_id` missing from SSE | Already in `PipelineStartEvent` |
| Need Supabase JSONB tables | Already file repo (`file_document_repo`) |
| Need to build generation form | Already `ProfileForm` in dashboard |
| Need to build history list | Already in dashboard page |
| Need to build reopen flow | Already works via `/textbook/[id]` |
| Need `TemplateRuntimeSurface` with `preset_id` string | `LectioThemeSurface` takes preset object |

---

## The Actual Build Order

```
1. Complete Lectio runtime surface work (separate task)
   - Create theme.css with preset variable blocks
   - Export LectioThemeSurface from index.ts
   - npm run package && npm run sync

2. Verify LectioDocumentView renders correctly
   - Navigate to any completed /textbook/{id}
   - Sections should be styled (not flat)
   - This requires step 1 to be done first

3. Add src/lib/parse-section.ts (new file)
   - npm install zod
   - Write the Zod schema as above

4. Update section_ready handler in /textbook/[id]/+page.svelte
   - Import parseIncomingSection
   - Wrap upsertSection call with try/catch

5. Add section_started handler + skeleton UI
   - Add pendingSections state
   - Add section_started listener
   - Render skeletons for pending sections

6. End-to-end verify
   - Start a new generation from dashboard
   - Verify skeletons appear as sections start
   - Verify sections render fully styled as they arrive
   - Verify completed generation reopens correctly
   - Verify a manually corrupted section_ready event
     is caught by Zod and logged, not crashing the page
```

---

## Complete Validation Layer Picture

```
Layer 1  Lectio startup           template-validation.ts
         Catches broken template contracts at app start

Layer 2  Pipeline content node    PydanticAI output_type=SectionContent
         Validates every LLM output inline before it enters state

Layer 3  Pipeline section assembler  lectio_contracts.py
         Validates contract compliance + capacity limits

Layer 4  Frontend SSE boundary    parse-section.ts (Zod)      ← ADD THIS
         Validates structure before upsertSection or database

Layer 5  File document repo       JSON serialisation
         Pydantic model_dump validates before write
```

---

## Nothing Else Needs to Change

The pipeline is complete. The backend routes are complete.
Auth is wired. History works. The enhance flow works.
The document model is correct. The SSE transport is correct.

Three additions close the remaining gaps:
- Zod at the SSE boundary
- Lectio theme surface wired (depends on Lectio work)
- section_started skeleton UI

Everything else the previous proposals described is already built.

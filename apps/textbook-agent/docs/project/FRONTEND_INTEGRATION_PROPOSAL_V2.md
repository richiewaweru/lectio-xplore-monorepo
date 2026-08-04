# Frontend Integration Proposal — v2
**Covers:** Layer 4 Zod · SvelteKit generate route · JSON persistence
**Updated for:** TemplateRuntimeSurface · theme.css · preset_id in SSE stream
**Replaces:** FRONTEND_INTEGRATION_PROPOSAL.md

---

## What Changed Since v1 and Why

v1 had the right structure. Three things changed with the
Lectio runtime surface work:

**1. `LectioTemplateRenderer` is deleted.**
We wrote this as a local component in the textbook agent.
`TemplateRuntimeSurface` from Lectio replaces it entirely.
It does the same job — maps `template_id` to layout, renders
`section` — but also applies the correct `data-lectio-preset`
attribute so theming works. The local component cannot do that.

**2. `preset_id` must flow through the SSE stream.**
`TemplateRuntimeSurface` needs `preset_id` to apply the correct
visual theme. The pipeline already knows `preset_id` — it is in
the generation request. It just was not included in the SSE events.
One field added to `pipeline_start`. Everything downstream uses it.

**3. The CSS import changes.**
v1 said `import 'lectio/styles'`. It is now `import 'lectio/theme'`
pointing at `theme.css` — the new file that includes preset variable
blocks, the `@source` directives for Tailwind, and all Lectio
utility classes. One import in the root layout. Nothing else.

Everything else in v1 is unchanged — the flow, the state machine,
the persistence schema, the Zod validation, the build order.

---

## The Flow — Updated

```
Teacher submits generate form (topic, template_id, preset_id...)
  ↓
POST /generate → Python pipeline → SSE stream
  ↓
pipeline_start event → frontend stores pipeline_id + preset_id
  ↓
section_ready events (one per section as it completes)
  → Zod parses section JSON at boundary        ← Layer 4, unchanged
  → section saved to DB with preset_id         ← Persistence, +preset_id
  → TemplateRuntimeSurface renders it          ← NEW — not LectioTemplateRenderer
    with data-lectio-preset={preset_id}
  ↓
Teacher sees sections arrive fully styled, one by one
  ↓
Teacher reopens tomorrow → DB returns sections + preset_id
  → TemplateRuntimeSurface renders from stored JSON
    same preset_id, identical visual output
```

---

## Part 1 — Layer 4 Zod Validation

**No change from v1.** `src/lib/parse-section.ts` is identical.
The Zod schema validates required fields, passes optional fields
through. `preset_id` is not in `SectionContent` — it is a rendering
concern, not a content concern — so it does not appear here.

```typescript
// src/lib/parse-section.ts — unchanged from v1
import { z } from 'zod'
import type { SectionContent } from 'lectio'

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
      `Invalid section from pipeline at '${first.path.join('.')}': ${first.message}`
    )
  }
  return result.data as SectionContent
}
```

---

## Part 2 — Pipeline Change: add `preset_id` to SSE

**One line added in the Python pipeline.**
`preset_id` is already in the generation request. It just needs
to be included in the `pipeline_start` event so the frontend
has it before sections start arriving.

```python
# src/server/api/generate.py — updated pipeline_start event

yield _event("pipeline_start", {
    "pipeline_id":   str(uuid.uuid4()),
    "section_count": request.section_count,
    "template_id":   request.template_id,
    "preset_id":     request.preset_id,      # ← ADDED
    "started_at":    datetime.utcnow().isoformat(),
})
```

No other pipeline changes. Nodes, state, graph, contracts — all
untouched. The pipeline produces `SectionContent` JSON. It does
not know or care how it is rendered.

---

## Part 3 — Root Layout: theme import

One import in the root layout. This is the only CSS the textbook
agent needs from Lectio. It provides CSS variables, preset overrides,
Tailwind `@source` directives, and all utility classes.

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  import 'lectio/theme'   ← single import, everything works
  import '../app.css'     ← textbook agent's own styles
</script>

<slot />
```

The textbook agent's `app.css` no longer needs to define any
Lectio variables — they all come from `lectio/theme`.

---

## Part 4 — Generate Page: updated

### What changes from v1

- `LectioTemplateRenderer` is removed entirely
- `TemplateRuntimeSurface` is imported from `lectio`
- `preset_id` is stored from the `pipeline_start` event
- `TemplateRuntimeSurface` receives `{section}`, `{template_id}`,
  `{preset_id}` — three props, fully themed rendering

### `src/lib/api/generate.ts` — unchanged from v1

The `streamGeneration` generator is identical. It still calls
`parseIncomingSection` on every `section_ready` event.

### `src/routes/generate/+page.svelte` — updated

```svelte
<script lang="ts">
  import { streamGeneration } from '$lib/api/generate'
  import { TemplateRuntimeSurface } from 'lectio'   ← replaces LectioTemplateRenderer
  import type { SectionContent } from 'lectio'

  type PageState = 'idle' | 'generating' | 'complete' | 'error'
  let state          = $state<PageState>('idle')
  let sections       = $state<SectionContent[]>([])
  let generating_ids = $state<string[]>([])
  let error          = $state<string | null>(null)
  let pipeline_id    = $state<string | null>(null)

  // Form values
  let topic         = $state('')
  let subject       = $state('Mathematics')
  let grade_band    = $state<'primary' | 'secondary' | 'advanced'>('secondary')
  let template_id   = $state('guided-concept-path')
  let preset_id     = $state('blue-classroom')   ← used by form AND renderer
  let learner_fit   = $state('general')
  let section_count = $state(4)

  async function generate() {
    state    = 'generating'
    sections = []
    error    = null

    try {
      for await (const event of streamGeneration({
        topic, subject, grade_band, template_id,
        preset_id, learner_fit, section_count,
      }, import.meta.env.VITE_PIPELINE_API_URL)) {

        if (event.type === 'pipeline_start') {
          pipeline_id = event.pipeline_id as string
          // preset_id already set from form — confirm it matches
          // (defensive: use the pipeline's confirmed value)
          preset_id = (event.preset_id as string) ?? preset_id
        }

        if (event.type === 'section_generating') {
          generating_ids = [...generating_ids, event.section_id as string]
        }

        if (event.type === 'section_ready') {
          const section = event.section as SectionContent
          sections      = [...sections, section]
          generating_ids = generating_ids.filter(
            id => id !== section.section_id
          )
          await saveSection(pipeline_id!, section)
        }

        if (event.type === 'complete') {
          state = 'complete'
        }

        if (event.type === 'error') {
          error = event.message as string
          state = 'error'
        }
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error'
      state = 'error'
    }
  }

  async function saveSection(pid: string, section: SectionContent) {
    await fetch('/api/textbook/sections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pipeline_id: pid,
        preset_id,          ← ADDED — stored alongside section
        section,
      }),
    })
  }
</script>

{#if state === 'idle'}
  <!-- form -->
  <button onclick={generate}>Generate</button>
{/if}

{#if state === 'generating' || state === 'complete'}
  {#each sections as section (section.section_id)}

    <!-- TemplateRuntimeSurface replaces LectioTemplateRenderer -->
    <!-- It handles layout lookup, preset scoping, and rendering -->
    <TemplateRuntimeSurface
      {section}
      template_id={template_id}
      preset_id={preset_id}
    />

  {/each}

  {#each generating_ids as sid}
    <SectionSkeleton section_id={sid} />
  {/each}
{/if}

{#if state === 'error'}
  <ErrorPanel message={error} onRetry={() => state = 'idle'} />
{/if}
```

---

## Part 5 — JSON Persistence: updated

### Database schema

One addition: `preset_id` on `generation_sections`.
When reopening, the frontend needs to know which preset
to pass to `TemplateRuntimeSurface`. Storing it alongside
the section JSON means the reopen flow is self-contained —
no need to also fetch the run to get the preset.

```sql
CREATE TABLE generation_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id   TEXT NOT NULL UNIQUE,
  template_id   TEXT NOT NULL,
  preset_id     TEXT NOT NULL,          ← already in v1, unchanged
  topic         TEXT NOT NULL,
  subject       TEXT NOT NULL,
  grade_band    TEXT NOT NULL,
  learner_fit   TEXT NOT NULL,
  section_count INTEGER NOT NULL,
  status        TEXT NOT NULL DEFAULT 'generating',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at  TIMESTAMPTZ,
  user_id       UUID REFERENCES auth.users(id)
);

CREATE TABLE generation_sections (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id       UUID NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
  pipeline_id  TEXT NOT NULL,
  section_id   TEXT NOT NULL,
  position     INTEGER NOT NULL,
  section_json JSONB NOT NULL,
  preset_id    TEXT NOT NULL,           ← ADDED — needed for reopen rendering
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(pipeline_id, section_id)
);
```

### `POST /api/textbook/sections` — updated

```typescript
// src/routes/api/textbook/sections/+server.ts

export const POST: RequestHandler = async ({ request, locals }) => {
  const session = locals.session
  if (!session) throw error(401, 'Unauthorised')

  const { pipeline_id, preset_id, section } = await request.json()

  if (!pipeline_id || !preset_id || !section?.section_id) {
    throw error(400, 'pipeline_id, preset_id, and section required')
  }

  const { error: dbError } = await supabase
    .from('generation_sections')
    .upsert({
      pipeline_id,
      section_id:   section.section_id,
      position:     parseInt(section.section_id.replace('s-', '')),
      section_json: section,
      preset_id,                        ← ADDED
    }, { onConflict: 'pipeline_id,section_id' })

  if (dbError) throw error(500, dbError.message)
  return json({ ok: true })
}
```

### `GET /api/textbook/runs/[id]` — unchanged from v1

Returns `section_json` per section. Now also returns `preset_id`
from the row automatically since it is a column.

### Reopen flow — updated

The load function returns `sections` with `preset_id` per section.
The page sets state to `complete` immediately and renders using
`TemplateRuntimeSurface` with each section's stored `preset_id`:

```typescript
// src/routes/generate/+page.ts — updated return shape
export const load: PageLoad = async ({ url, fetch }) => {
  const runId = url.searchParams.get('run')
  if (!runId) return {}

  const response = await fetch(`/api/textbook/runs/${runId}`)
  if (!response.ok) return {}

  const { run, sections } = await response.json()
  // sections now includes preset_id per section
  return { run, sections, preset_id: run.preset_id }
}
```

```svelte
<!-- In +page.svelte — reopen renders identically to generate -->
{#each data.sections as section (section.section_id)}
  <TemplateRuntimeSurface
    {section}
    template_id={data.run.template_id}
    preset_id={data.preset_id}
  />
{/each}
```

The teacher sees exactly the same visual output as when the
textbook was first generated. Same preset, same template,
same sections. The rendering is deterministic from stored JSON.

---

## Validation Layers — Unchanged

```
Layer 1 — Lectio startup        template-validation.ts
Layer 2 — Content generator     PydanticAI inline
Layer 3 — Section assembler     lectio_contracts.py
Layer 4 — Frontend SSE boundary parse-section.ts (Zod)
Layer 5 — Database              Postgres JSONB
```

---

## Build Order — Updated

```
1.  npm install zod              (in textbook agent frontend)

2.  Write src/lib/parse-section.ts
    Unchanged from v1.

3.  Add import 'lectio/theme' to +layout.svelte
    Diagnostic: run dev server, verify Lectio components
    render with correct colours.

4.  Write src/lib/api/generate.ts
    Unchanged from v1.

5.  Add preset_id to pipeline_start event in generate.py
    One line change in the Python server.

6.  Write database migration
    Add preset_id column to generation_sections.
    Run in Supabase.

7.  Write API routes
    sections/+server.ts — store preset_id alongside section
    runs/[id]/+server.ts — return preset_id with sections

8.  Write +page.svelte
    Import TemplateRuntimeSurface from 'lectio'.
    No LectioTemplateRenderer — it does not exist.
    Render sections with {section}, {template_id}, {preset_id}.

9.  Write +page.ts load function
    Return sections + preset_id for reopen rendering.

10. Manual end-to-end check
    Generate → sections arrive styled → DB row saved
    Reload with ?run=<id> → identical styled output
    Change preset in form → different visual output
```

---

## What Is Deleted From v1

```
src/lib/components/LectioTemplateRenderer.svelte   ← DELETE
```

This was a workaround for the lack of `TemplateRuntimeSurface`.
Now that the surface exists in Lectio, the local component has
no purpose and should not be created.

---

## Environment Variables — Unchanged

```bash
# textbook agent frontend
VITE_PIPELINE_API_URL=http://localhost:8000

# textbook agent backend
ANTHROPIC_API_KEY=...
LECTIO_CONTRACTS_DIR=../lectio/agents/contracts
```

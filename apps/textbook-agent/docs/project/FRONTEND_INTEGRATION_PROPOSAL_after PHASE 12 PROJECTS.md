# Frontend Integration Proposal
**Covers:** Layer 4 Zod validation · SvelteKit generate route · JSON persistence
**Depends on:** Pipeline phases 1–12 complete · Lectio packaged as library

---

## The Three Things and How They Connect

These are not three independent features. They are one flow:

```
Teacher submits generate form
  ↓
POST /generate → Python pipeline → SSE stream
  ↓
SvelteKit route reads stream
  → Zod parses each section_ready event        ← Layer 4
  → Section stored to database                 ← Persistence
  → Section passed to Lectio template layout   ← Rendering
  ↓
Teacher sees sections arrive and render in real time
  ↓
Teacher returns tomorrow → sections loaded from DB, not regenerated
```

Build them in this order. Zod first because it is a dependency
of the route. Route second because persistence depends on knowing
what a valid section looks like arriving from the stream. DB third
because it stores what the route produces.

---

## Part 1 — Layer 4 Zod Validation

**File:** `src/lib/parse-section.ts` (in the textbook agent frontend)

**What it does:** Single guard at the SSE boundary. Every
`section_ready` event passes through this before touching any
component or database. If the pipeline sends malformed JSON,
this catches it with a precise error message.

**What it does not do:** Validate prose quality, enforce capacity
limits, or duplicate what Pydantic already checked in the pipeline.
Structure only. The minimal schema that confirms the data is
renderable.

```typescript
// src/lib/parse-section.ts

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
// passthrough() allows optional fields (definition, diagram,
// worked_example etc.) without declaring all of them here.
// Required fields are checked. Optional fields are trusted
// if present — the pipeline already validated them.

export type ParsedSection = z.infer<typeof SectionContentSchema>

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

**Dependency:** `zod` must be in the textbook agent frontend's
`package.json`. Add if not present: `npm install zod`

---

## Part 2 — SvelteKit Generate Route

**Files:**
```
src/routes/generate/
  +page.svelte          ← the generate form + live rendering
  +page.ts              ← load function (fetches existing if pipeline_id in URL)
src/lib/api/generate.ts ← typed wrapper around the pipeline API
```

### The page state machine

The generate page has four states a teacher moves through:

```
IDLE         → teacher has filled the form, not yet submitted
GENERATING   → stream is live, sections arriving one by one
COMPLETE     → all sections assembled, QC done
ERROR        → pipeline returned an error event
```

Each state renders differently. `GENERATING` shows sections as they
arrive with a loading state for sections not yet complete. `COMPLETE`
shows all sections fully rendered with export options. `ERROR` shows
which stage failed and offers retry.

### `src/lib/api/generate.ts`

```typescript
// Typed wrapper around the pipeline SSE endpoint.
// The route uses this — never fetches directly.

import { parseIncomingSection } from '$lib/parse-section'
import type { SectionContent } from 'lectio'

export interface GenerateRequest {
  topic:         string
  subject:       string
  grade_band:    'primary' | 'secondary' | 'advanced'
  template_id:   string
  preset_id:     string
  learner_fit:   string
  section_count: number
}

export interface PipelineEvent {
  type: 'pipeline_start' | 'section_generating' | 'section_ready'
       | 'qc_complete' | 'complete' | 'error'
  [key: string]: unknown
}

export async function* streamGeneration(
  request: GenerateRequest,
  apiBase: string,
): AsyncGenerator<PipelineEvent> {
  const response = await fetch(`${apiBase}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Pipeline API error: ${response.status}`)
  }

  const reader  = response.body!.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6)) as PipelineEvent

        // Validate sections at the boundary before yielding
        if (event.type === 'section_ready' && event.section) {
          event.section = parseIncomingSection(event.section)
        }

        yield event
      } catch (e) {
        console.error('[generate] Failed to parse SSE event:', e)
      }
    }
  }
}
```

### `src/routes/generate/+page.svelte` (structure)

```svelte
<script lang="ts">
  import { streamGeneration } from '$lib/api/generate'
  import { getTemplateById } from 'lectio'
  import type { SectionContent } from 'lectio'

  // State
  type PageState = 'idle' | 'generating' | 'complete' | 'error'
  let state     = $state<PageState>('idle')
  let sections  = $state<SectionContent[]>([])
  let generating_ids = $state<string[]>([])  // sections in-flight
  let error     = $state<string | null>(null)
  let pipeline_id = $state<string | null>(null)

  // Form values
  let topic         = $state('')
  let subject       = $state('Mathematics')
  let grade_band    = $state<'primary' | 'secondary' | 'advanced'>('secondary')
  let template_id   = $state('guided-concept-path')
  let preset_id     = $state('blue-classroom')
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
        }

        if (event.type === 'section_generating') {
          generating_ids = [...generating_ids, event.section_id as string]
        }

        if (event.type === 'section_ready') {
          const section = event.section as SectionContent
          sections      = [...sections, section]
          generating_ids = generating_ids.filter(id => id !== section.section_id)
          // Persist immediately when section arrives
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
      body: JSON.stringify({ pipeline_id: pid, section }),
    })
  }
</script>

<!-- Form (shown in idle state) -->
{#if state === 'idle'}
  <!-- template selector, topic input, grade band, etc. -->
  <button onclick={generate}>Generate</button>
{/if}

<!-- Live rendering (shown in generating + complete states) -->
{#if state === 'generating' || state === 'complete'}
  {#each sections as section (section.section_id)}
    <!-- Render via the Lectio template layout for this template -->
    <LectioTemplateRenderer {section} template_id={template_id} />
  {/each}

  {#each generating_ids as sid}
    <!-- Skeleton placeholder for sections not yet arrived -->
    <SectionSkeleton section_id={sid} />
  {/each}
{/if}

{#if state === 'error'}
  <ErrorPanel message={error} onRetry={() => state = 'idle'} />
{/if}
```

### `LectioTemplateRenderer`

A thin wrapper that maps `template_id` to the correct Lectio
template layout component:

```svelte
<!-- src/lib/components/LectioTemplateRenderer.svelte -->
<script lang="ts">
  import { templateRegistry } from 'lectio'
  import type { SectionContent } from 'lectio'

  let { section, template_id }: {
    section:     SectionContent
    template_id: string
  } = $props()

  const template = templateRegistry.find(t => t.contract.id === template_id)
</script>

{#if template}
  <svelte:component this={template.render} {section} />
{:else}
  <p>Unknown template: {template_id}</p>
{/if}
```

---

## Part 3 — JSON Persistence

### What to store

One row per section per pipeline run. The complete `SectionContent`
JSON is the stored artifact. On reload, fetch the rows for a
`pipeline_id` and render them directly — no regeneration.

### Database schema

```sql
-- Migrations file
CREATE TABLE generation_runs (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id  TEXT NOT NULL UNIQUE,
  template_id  TEXT NOT NULL,
  preset_id    TEXT NOT NULL,
  topic        TEXT NOT NULL,
  subject      TEXT NOT NULL,
  grade_band   TEXT NOT NULL,
  learner_fit  TEXT NOT NULL,
  section_count INTEGER NOT NULL,
  status       TEXT NOT NULL DEFAULT 'generating',
  -- status: 'generating' | 'complete' | 'error'
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  user_id      UUID REFERENCES auth.users(id)
);

CREATE TABLE generation_sections (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id       UUID NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
  pipeline_id  TEXT NOT NULL,
  section_id   TEXT NOT NULL,   -- s-01, s-02 etc.
  position     INTEGER NOT NULL,
  section_json JSONB NOT NULL,  -- the full SectionContent object
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(pipeline_id, section_id)
);

CREATE INDEX idx_sections_pipeline_id ON generation_sections(pipeline_id);
CREATE INDEX idx_runs_user_id ON generation_runs(user_id);
```

**Why `JSONB` not `TEXT`:** Supabase (or Postgres) can query
into the JSON — filter by `section_json->>'template_id'`,
index on `section_json->>'section_id'`. Also ensures the stored
value is valid JSON at the DB level.

### SvelteKit API routes

```
src/routes/api/textbook/
  sections/
    +server.ts     ← POST (save section), GET (list sections for a run)
  runs/
    +server.ts     ← POST (create run), GET (list runs for user)
  runs/[id]/
    +server.ts     ← GET (fetch full run with sections for reopen)
```

**`POST /api/textbook/sections`** — called by the generate page
as each `section_ready` event arrives:

```typescript
// src/routes/api/textbook/sections/+server.ts

import { json, error } from '@sveltejs/kit'
import type { RequestHandler } from './$types'
import { supabase } from '$lib/server/supabase'

export const POST: RequestHandler = async ({ request, locals }) => {
  const session = locals.session
  if (!session) throw error(401, 'Unauthorised')

  const { pipeline_id, section } = await request.json()

  if (!pipeline_id || !section?.section_id) {
    throw error(400, 'pipeline_id and section required')
  }

  const { error: dbError } = await supabase
    .from('generation_sections')
    .upsert({
      pipeline_id,
      section_id:   section.section_id,
      position:     parseInt(section.section_id.replace('s-', '')),
      section_json: section,
    }, {
      onConflict: 'pipeline_id,section_id',
    })

  if (dbError) throw error(500, dbError.message)

  return json({ ok: true })
}
```

**`GET /api/textbook/runs/[id]`** — called by the load function
when a teacher reopens a previously generated textbook:

```typescript
// src/routes/api/textbook/runs/[id]/+server.ts

import { json, error } from '@sveltejs/kit'
import type { RequestHandler } from './$types'
import { supabase } from '$lib/server/supabase'

export const GET: RequestHandler = async ({ params, locals }) => {
  const session = locals.session
  if (!session) throw error(401, 'Unauthorised')

  const { data: run } = await supabase
    .from('generation_runs')
    .select('*, generation_sections(section_json, position)')
    .eq('id', params.id)
    .eq('user_id', session.user.id)
    .single()

  if (!run) throw error(404, 'Run not found')

  return json({
    run,
    sections: run.generation_sections
      .sort((a: any, b: any) => a.position - b.position)
      .map((s: any) => s.section_json),
  })
}
```

### Reopen flow

When a teacher navigates to `/generate?run=<id>`, the load
function fetches the stored sections and passes them to the page.
The page renders in `complete` state immediately — no generation,
no stream, no waiting:

```typescript
// src/routes/generate/+page.ts

import type { PageLoad } from './$types'

export const load: PageLoad = async ({ url, fetch }) => {
  const runId = url.searchParams.get('run')
  if (!runId) return {}

  const response = await fetch(`/api/textbook/runs/${runId}`)
  if (!response.ok) return {}

  const { run, sections } = await response.json()
  return { run, sections }
}
```

The page receives `data.sections` and sets `state = 'complete'`
immediately, rendering the stored sections via `LectioTemplateRenderer`.

---

## Validation Across the Three Parts

```
Layer 1 — Lectio startup           (TypeScript, template-validation.ts)
  Runs when Lectio app starts. Catches broken template contracts.

Layer 2 — Content generator        (Python, PydanticAI)
  Validates SectionContent inline after each LLM call.

Layer 3 — Section assembler        (Python, custom)
  Validates contract compliance and capacity limits.

Layer 4 — Frontend SSE boundary    (TypeScript, Zod)  ← Part 1
  parse-section.ts validates structure before rendering or saving.

Layer 5 (implicit) — Database      (Postgres JSONB)
  Rejects invalid JSON at storage level.
```

---

## Build Order

```
1. install zod in frontend project
   npm install zod

2. Write src/lib/parse-section.ts
   Diagnostic: import and call parseIncomingSection({}) — verify it
   throws with a clear message about missing section_id

3. Write src/lib/api/generate.ts
   Diagnostic: import streamGeneration — verify it compiles
   Do not call it yet — no API server running locally

4. Write database migration
   Run migration in Supabase dashboard or via Supabase CLI
   Verify tables exist and JSONB constraint rejects plain text

5. Write API routes (sections POST, runs GET)
   Diagnostic: curl POST with a sample section JSON
   Verify row appears in Supabase table

6. Write LectioTemplateRenderer component
   Diagnostic: render with a hardcoded SectionContent from
   Lectio's dummy-content.ts — verify it renders correctly

7. Write +page.svelte generate route
   Diagnostic: submit form → verify stream arrives → verify
   section renders → verify row saved in DB

8. Write +page.ts load function for reopen
   Diagnostic: navigate to /generate?run=<id> → verify sections
   render from DB without triggering a new generation
```

---

## Environment Variables Needed

```bash
# In textbook agent frontend .env
VITE_PIPELINE_API_URL=http://localhost:8000
```

```bash
# In textbook agent backend .env (already set from pipeline phases)
ANTHROPIC_API_KEY=...
LECTIO_CONTRACTS_DIR=../lectio/agents/contracts
```

---

## What This Unlocks

When this proposal is implemented, the product is real:

- A teacher fills in a form and sees a textbook being written
  section by section in real time
- The textbook is saved automatically as it arrives
- The teacher can close the browser and reopen the textbook tomorrow
- The rendered output uses the same Lectio components the gallery
  showcases — consistent, validated, deterministic

Everything after this — export to PDF, sharing, student profiles,
adaptive regeneration — is built on top of this foundation.

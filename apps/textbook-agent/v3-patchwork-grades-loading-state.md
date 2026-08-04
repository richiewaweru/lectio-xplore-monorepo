# v3 Patchwork — US Grade System + Planning Loading State

## Fix 1 — US grade system only

### File: `frontend/src/lib/components/studio/V3InputSurface.svelte`

Replace the `YEAR_GROUPS` constant with US grades only:

```javascript
const GRADE_LEVELS = [
    'Kindergarten',
    'Grade 1',
    'Grade 2',
    'Grade 3',
    'Grade 4',
    'Grade 5',
    'Grade 6',
    'Grade 7',
    'Grade 8',
    'Grade 9',
    'Grade 10',
    'Grade 11',
    'Grade 12',
]
```

Rename `year_group` state variable to `grade_level` if cleaner,
or keep as `year_group` for backend compatibility — just change the
display options. The backend field name `year_group` stays unchanged.

Update the select to iterate `GRADE_LEVELS`:

```svelte
<select bind:value={year_group} aria-label="Grade level">
    <option value="">Choose…</option>
    {#each GRADE_LEVELS as grade}
        <option value={grade}>{grade}</option>
    {/each}
</select>
```

Update the label text from "Year group" to "Grade level".

---

## Fix 2 — Planning loading state

### New file: `frontend/src/lib/components/studio/V3PlanningState.svelte`

Shown when `v3Studio.stage === 'planning'`. Displays the teacher's
own inputs back to them so the wait feels personal, not generic.
Animated pulse keeps the UI alive without fake progress claims.

```svelte
<script lang="ts">
    import type { V3InputForm } from '$lib/types/v3';

    interface Props {
        form: V3InputForm | null;
    }

    let { form }: Props = $props();

    const LESSON_MODE_LABELS: Record<string, string> = {
        first_exposure: 'First exposure',
        consolidation:  'Consolidation',
        repair:         'Repair',
        retrieval:      'Retrieval practice',
        transfer:       'Transfer',
    };

    const LEVEL_LABELS: Record<string, string> = {
        below_average:  'Below grade level',
        average:        'At grade level',
        above_average:  'Above grade level',
        mixed:          'Mixed ability',
    };

    const SUPPORT_LABELS: Record<string, string> = {
        eal:       'EAL support',
        high_load: 'ADHD / dyslexia',
        advanced:  'Advanced learners',
    };

    const messages = [
        'Thinking about your class…',
        'Planning the teaching sequence…',
        'Selecting the right components…',
        'Designing your practice questions…',
        'Almost there…',
    ]

    let messageIndex = $state(0);

    $effect(() => {
        const interval = setInterval(() => {
            messageIndex = (messageIndex + 1) % messages.length;
        }, 8000);
        return () => clearInterval(interval);
    });
</script>

<div class="mx-auto max-w-xl space-y-8 px-4 py-16 text-center">

    <!-- Animated pulse ring -->
    <div class="flex justify-center">
        <div class="relative h-16 w-16">
            <div class="absolute inset-0 animate-ping rounded-full bg-primary/20"></div>
            <div class="absolute inset-2 rounded-full bg-primary/40"></div>
            <div class="absolute inset-4 rounded-full bg-primary"></div>
        </div>
    </div>

    <!-- Rotating message -->
    <div class="space-y-1">
        <p class="text-lg font-medium transition-all duration-500">
            {messages[messageIndex]}
        </p>
        <p class="text-sm text-muted-foreground">
            Building your lesson plan with Opus
        </p>
    </div>

    <!-- Teacher's own inputs reflected back -->
    {#if form}
        <div class="mx-auto max-w-sm rounded-xl border border-border/60
                    bg-muted/30 px-6 py-4 text-left space-y-2 text-sm">

            <div class="flex justify-between">
                <span class="text-muted-foreground">Grade</span>
                <span class="font-medium">{form.year_group}</span>
            </div>

            <div class="flex justify-between">
                <span class="text-muted-foreground">Subject</span>
                <span class="font-medium">{form.subject}</span>
            </div>

            <div class="flex justify-between">
                <span class="text-muted-foreground">Duration</span>
                <span class="font-medium">{form.duration_minutes} min</span>
            </div>

            {#if form.lesson_mode}
                <div class="flex justify-between">
                    <span class="text-muted-foreground">Lesson type</span>
                    <span class="font-medium">
                        {LESSON_MODE_LABELS[form.lesson_mode] ?? form.lesson_mode}
                    </span>
                </div>
            {/if}

            {#if form.learner_level}
                <div class="flex justify-between">
                    <span class="text-muted-foreground">Learner level</span>
                    <span class="font-medium">
                        {LEVEL_LABELS[form.learner_level] ?? form.learner_level}
                    </span>
                </div>
            {/if}

            {#if form.support_needs && form.support_needs.length > 0}
                <div class="flex justify-between">
                    <span class="text-muted-foreground">Support</span>
                    <span class="font-medium">
                        {form.support_needs.map(s => SUPPORT_LABELS[s] ?? s).join(', ')}
                    </span>
                </div>
            {/if}

            {#if form.free_text}
                <div class="border-t border-border/40 pt-2 mt-2">
                    <p class="text-muted-foreground text-xs mb-1">Topic</p>
                    <p class="text-sm leading-snug line-clamp-2">{form.free_text}</p>
                </div>
            {/if}

        </div>
    {/if}

</div>
```

### Wire into `frontend/src/routes/studio/+page.svelte`

Import the component and show it during the planning stage:

```svelte
import V3PlanningState from '$lib/components/studio/V3PlanningState.svelte';

<!-- In the stage conditional: -->
{:else if v3Studio.stage === 'planning'}
    <V3PlanningState form={v3Studio.form} />
```

Replace any existing bare spinner or empty div for the planning state.

---

## Verification

```
□ Grade level dropdown shows Kindergarten through Grade 12 only
□ No Year 1–12 options in the dropdown
□ Label reads "Grade level" not "Year group"
□ While stage === 'planning', V3PlanningState is visible
□ Animated pulse ring is visible
□ Message rotates every 8 seconds
□ Teacher's grade, subject, duration, lesson type, level, support shown
□ Topic (free_text) shown truncated to 2 lines
□ Component unmounts cleanly when stage changes to 'reviewing'
```

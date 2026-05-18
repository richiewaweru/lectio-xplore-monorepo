<script lang="ts">
	import { narrowTopic } from '$lib/api/v3';
	import type { V3InputForm } from '$lib/types/v3';

	interface Props {
		onSubmit: (form: V3InputForm) => void;
	}

	let { onSubmit }: Props = $props();

	// --- Step 1 state ---
	let grade_level = $state('');
	let subject = $state('');
	let duration_minutes = $state(50);

	// --- Step 2 state ---
	let topic = $state('');
	let subtopics = $state<string[]>([]);
	let subtopic_candidates = $state<Array<{ id: string; title: string; description: string }>>([]);
	let prior_knowledge = $state('');
	let resolving_topic = $state(false);

	// --- Step 3 state ---
	let lesson_mode = $state<V3InputForm['lesson_mode']>('first_exposure');
	let lesson_mode_other = $state('');
	let intended_outcome = $state<V3InputForm['intended_outcome']>('understand');
	let intended_outcome_other = $state('');

	// --- Step 4 state ---
	let learner_level = $state<V3InputForm['learner_level']>('on_grade');
	let reading_level = $state<V3InputForm['reading_level']>('on_grade');
	let language_support = $state<V3InputForm['language_support']>('none');
	let prior_knowledge_level = $state<V3InputForm['prior_knowledge_level']>('new_topic');
	let support_needs = $state<string[]>([]);
	let support_other = $state('');
	let learning_preferences = $state<Array<V3InputForm['learning_preferences'][number]>>([]);

	// --- Step 5 state ---
	let free_text = $state('');

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
		'Grade 12'
	];

	const SUBJECTS = [
		'Mathematics',
		'English Language Arts',
		'Science',
		'Biology',
		'Chemistry',
		'Physics',
		'History',
		'Geography',
		'Economics',
		'Computer Science',
		'Art',
		'Music',
		'Physical Education',
		'Other'
	];

	const DURATIONS = [
		15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 75, 90
	].map((v) => ({ label: `${v} min`, value: v }));

	const LESSON_MODES: Array<{ value: V3InputForm['lesson_mode']; label: string }> = [
		{ value: 'first_exposure', label: 'First time teaching this' },
		{ value: 'consolidation', label: 'They know it — need more practice' },
		{ value: 'repair', label: 'Something went wrong — fix it' },
		{ value: 'retrieval', label: 'Quick recall from earlier' },
		{ value: 'transfer', label: 'Apply it in a new context' },
		{ value: 'other', label: 'Other (describe below)' }
	];

	const OUTCOMES: Array<{ value: V3InputForm['intended_outcome']; label: string }> = [
		{ value: 'understand', label: 'Understand the concept' },
		{ value: 'practise', label: 'Practise and apply' },
		{ value: 'review', label: 'Review and consolidate' },
		{ value: 'assess', label: 'Check understanding' },
		{ value: 'other', label: 'Other (describe below)' }
	];

	const LEVELS: Array<{ value: V3InputForm['learner_level']; label: string }> = [
		{ value: 'below_grade', label: 'Below grade level' },
		{ value: 'on_grade', label: 'At grade level' },
		{ value: 'above_grade', label: 'Above grade level' },
		{ value: 'mixed', label: 'Mixed ability' }
	];

	const READING_LEVELS: Array<{ value: V3InputForm['reading_level']; label: string }> = [
		{ value: 'below_grade', label: 'Below grade reading level' },
		{ value: 'on_grade', label: 'At grade reading level' },
		{ value: 'above_grade', label: 'Above grade reading level' },
		{ value: 'mixed', label: 'Mixed' }
	];

	const LANGUAGE_OPTIONS: Array<{ value: V3InputForm['language_support']; label: string }> = [
		{ value: 'none', label: 'English only / no ELL needs' },
		{ value: 'some_ell', label: 'Some ELL learners' },
		{ value: 'many_ell', label: 'Mostly ELL learners' }
	];

	const PRIOR_KNOWLEDGE_OPTIONS: Array<{ value: V3InputForm['prior_knowledge_level']; label: string }> =
		[
			{ value: 'new_topic', label: 'Brand new — no prior exposure' },
			{ value: 'some_background', label: 'Some background knowledge' },
			{ value: 'reviewing', label: 'Reviewing something taught before' }
		];

	const SUPPORT_OPTIONS: Array<{ value: string; label: string }> = [
		{ value: 'visuals', label: 'Visual supports' },
		{ value: 'step_by_step', label: 'Step-by-step scaffolding' },
		{ value: 'vocabulary_support', label: 'Vocabulary support' },
		{ value: 'worked_examples', label: 'Worked examples' },
		{ value: 'simpler_reading', label: 'Simplified reading level' },
		{ value: 'challenge', label: 'Challenge questions' }
	];

	const LEARNING_PREFERENCES: Array<{ value: V3InputForm['learning_preferences'][number]; label: string }> =
		[
			{ value: 'visual', label: 'Visual' },
			{ value: 'step_by_step', label: 'Step-by-step' },
			{ value: 'discussion', label: 'Discussion' },
			{ value: 'hands_on', label: 'Hands-on' },
			{ value: 'challenge', label: 'Challenge' }
		];

	function toggleSubtopic(title: string) {
		const already = subtopics.includes(title);
		if (already) {
			subtopics = subtopics.filter((s) => s !== title);
		} else if (subtopics.length < 3) {
			subtopics = [...subtopics, title];
		}
	}

	function toggleSupport(val: string) {
		support_needs = support_needs.includes(val)
			? support_needs.filter((s) => s !== val)
			: [...support_needs, val];
	}

	function togglePreference(val: V3InputForm['learning_preferences'][number]) {
		learning_preferences = learning_preferences.includes(val)
			? learning_preferences.filter((p) => p !== val)
			: [...learning_preferences, val];
	}

	function addSupportOther() {
		const cleaned = support_other.trim();
		if (!cleaned) return;
		if (!support_needs.includes(cleaned)) support_needs = [...support_needs, cleaned];
		support_other = '';
	}

	async function resolveTopic() {
		const cleaned = topic.trim();
		if (!cleaned || !grade_level || !subject) return;
		resolving_topic = true;
		try {
			const candidates = await narrowTopic({
				topic: cleaned,
				grade_level,
				subject
			});
			subtopic_candidates = candidates;
			subtopics = [];
		} catch {
			const parts = cleaned
				.split(/[,;:()/-]+/)
				.map((part) => part.trim())
				.filter((part) => part.length > 2)
				.slice(0, 3);
			subtopic_candidates = (parts.length > 0 ? parts : [cleaned]).map((title, index) => ({
				id: 'local-' + String(index + 1),
				title,
				description: 'Use this focus for the generated lesson.'
			}));
			subtopics = [];
		} finally {
			resolving_topic = false;
		}
	}

	const canSubmit = $derived(grade_level !== '' && subject !== '' && topic.trim().length > 2);

	function handleSubmit(e: Event) {
		e.preventDefault();
		if (!canSubmit) return;
		onSubmit({
			grade_level,
			subject,
			duration_minutes: Number(duration_minutes),
			topic: topic.trim(),
			subtopics,
			prior_knowledge: prior_knowledge.trim(),
			lesson_mode,
			lesson_mode_other: lesson_mode_other.trim(),
			intended_outcome,
			intended_outcome_other: intended_outcome_other.trim(),
			learner_level,
			reading_level,
			language_support,
			prior_knowledge_level,
			support_needs,
			learning_preferences,
			free_text: free_text.trim()
		});
	}
</script>

<div class="mx-auto max-w-xl space-y-6 px-4 py-10">
	<header class="space-y-2 text-center">
		<h1 class="text-3xl font-semibold tracking-tight">What do you want to teach?</h1>
		<p class="text-muted-foreground">Answer a few quick questions — we’ll build the lesson plan.</p>
	</header>

	<form class="space-y-10" onsubmit={handleSubmit}>
		<!-- STEP 1 — BASICS -->
		<section class="space-y-4">
			<h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">The basics</h2>
			<div class="grid gap-3 sm:grid-cols-3">
			<label class="grid gap-1 text-sm font-medium">
				<span>Grade level</span>
				<select
					class="rounded-md border border-input bg-background px-3 py-2"
					bind:value={grade_level}
					aria-label="Grade level"
				>
					<option value="">Choose…</option>
					{#each GRADE_LEVELS as grade}
						<option value={grade}>{grade}</option>
					{/each}
				</select>
			</label>
			<label class="grid gap-1 text-sm font-medium">
				<span>Subject</span>
				<select
					class="rounded-md border border-input bg-background px-3 py-2"
					bind:value={subject}
					aria-label="Subject"
				>
					<option value="">Choose…</option>
					{#each SUBJECTS as s}
						<option value={s}>{s}</option>
					{/each}
				</select>
			</label>
			<label class="grid gap-1 text-sm font-medium">
				<span>Duration</span>
				<select
					class="rounded-md border border-input bg-background px-3 py-2"
					bind:value={duration_minutes}
					aria-label="Duration"
				>
					{#each DURATIONS as d}
						<option value={d.value}>{d.label}</option>
					{/each}
				</select>
			</label>
			</div>
		</section>

		<!-- STEP 2 — CONCEPT -->
		<section class="space-y-4">
			<h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">The concept</h2>

			<label class="grid gap-1 text-sm font-medium">
				<span>Topic</span>
				<div class="flex gap-2">
					<input
						class="flex-1 rounded-md border border-input bg-background px-3 py-2"
						bind:value={topic}
						placeholder="e.g. Photosynthesis"
						onblur={resolveTopic}
					/>
					<button
						type="button"
						class="rounded-md border px-3 py-2 text-sm"
						disabled={resolving_topic || !topic.trim() || !grade_level || !subject}
						onclick={resolveTopic}
					>
						{resolving_topic ? '…' : 'Narrow'}
					</button>
				</div>
			</label>

			{#if subtopic_candidates.length > 0}
				<div class="space-y-2">
					<p class="text-sm text-muted-foreground">Pick up to 3 subtopics for this lesson</p>
					<div class="flex flex-wrap gap-2">
						{#each subtopic_candidates as candidate}
							{@const selected = subtopics.includes(candidate.title)}
							<button
								type="button"
								class={`rounded-full border px-3 py-1 text-sm ${
									selected
										? 'bg-primary text-primary-foreground border-primary'
										: 'bg-background border-input'
								}`}
								onclick={() => toggleSubtopic(candidate.title)}
								title={candidate.description}
							>
								{candidate.title}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<label class="grid gap-1 text-sm font-medium">
				<span>
					What have they already covered?
					<span class="text-muted-foreground">(optional)</span>
				</span>
				<input
					class="rounded-md border border-input bg-background px-3 py-2"
					bind:value={prior_knowledge}
					placeholder="e.g. Cell structure, plant parts"
				/>
			</label>
		</section>

		<!-- STEP 3 — LESSON SHAPE -->
		<section class="space-y-4">
			<h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Lesson shape</h2>

			<label class="grid gap-1 text-sm font-medium">
				<span>What is this lesson for?</span>
				<select bind:value={lesson_mode} class="rounded-md border border-input bg-background px-3 py-2">
					{#each LESSON_MODES as m}
						<option value={m.value}>{m.label}</option>
					{/each}
				</select>
			</label>

			{#if lesson_mode === 'other'}
				<input
					class="rounded-md border border-input bg-background px-3 py-2 w-full"
					bind:value={lesson_mode_other}
					placeholder="Describe the lesson mode…"
				/>
			{/if}

			<label class="grid gap-1 text-sm font-medium">
				<span>What should learners leave able to do?</span>
				<select
					bind:value={intended_outcome}
					class="rounded-md border border-input bg-background px-3 py-2"
				>
					{#each OUTCOMES as o}
						<option value={o.value}>{o.label}</option>
					{/each}
				</select>
			</label>

			{#if intended_outcome === 'other'}
				<input
					class="rounded-md border border-input bg-background px-3 py-2 w-full"
					bind:value={intended_outcome_other}
					placeholder="Describe the intended outcome…"
				/>
			{/if}
		</section>

		<!-- STEP 4 — CLASS PROFILE -->
		<section class="space-y-4">
			<h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Your class</h2>

			<div class="grid gap-3 sm:grid-cols-2">
				<label class="grid gap-1 text-sm font-medium">
					<span>Overall level</span>
					<select bind:value={learner_level} class="rounded-md border border-input bg-background px-3 py-2">
						{#each LEVELS as l}
							<option value={l.value}>{l.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Reading level</span>
					<select bind:value={reading_level} class="rounded-md border border-input bg-background px-3 py-2">
						{#each READING_LEVELS as r}
							<option value={r.value}>{r.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Language support</span>
					<select
						bind:value={language_support}
						class="rounded-md border border-input bg-background px-3 py-2"
					>
						{#each LANGUAGE_OPTIONS as l}
							<option value={l.value}>{l.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Prior knowledge</span>
					<select
						bind:value={prior_knowledge_level}
						class="rounded-md border border-input bg-background px-3 py-2"
					>
						{#each PRIOR_KNOWLEDGE_OPTIONS as p}
							<option value={p.value}>{p.label}</option>
						{/each}
					</select>
				</label>
			</div>

			<div class="space-y-2">
				<p class="text-sm font-medium">Support needs</p>
				<div class="flex flex-wrap gap-3">
					{#each SUPPORT_OPTIONS as s}
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={support_needs.includes(s.value)}
								onchange={() => toggleSupport(s.value)}
							/>
							{s.label}
						</label>
					{/each}
				</div>

				<div class="flex gap-2">
					<input
						class="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
						bind:value={support_other}
						placeholder="Other support need…"
						onkeydown={(e) => e.key === 'Enter' && addSupportOther()}
					/>
					<button
						type="button"
						class="rounded-md border px-3 py-2 text-sm"
						onclick={addSupportOther}
						disabled={!support_other.trim()}
					>
						Add
					</button>
				</div>
			</div>

			<div class="space-y-2">
				<p class="text-sm font-medium">
					Learning preferences
					<span class="text-muted-foreground">(optional)</span>
				</p>
				<div class="flex flex-wrap gap-3">
					{#each LEARNING_PREFERENCES as pref}
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								checked={learning_preferences.includes(pref.value)}
								onchange={() => togglePreference(pref.value)}
							/>
							{pref.label}
						</label>
					{/each}
				</div>
			</div>
		</section>

		<!-- STEP 5 — OPTIONAL INTENT -->
		<section class="space-y-2">
			<h2 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
				Anything else? <span class="text-muted-foreground font-normal">(optional)</span>
			</h2>
			<textarea
				class="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
				bind:value={free_text}
				placeholder="Any specific angles, examples, or constraints to include…"
			></textarea>
		</section>

		<button
			type="submit"
			disabled={!canSubmit}
			class="w-full rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
		>
			Build my lesson plan
		</button>
	</form>
</div>

<script lang="ts">
	import { narrowTopic } from '$lib/api/v3';
	import type { V3InputForm } from '$lib/types/v3';

	interface Props {
		onSubmit: (form: V3InputForm) => void;
	}

	let { onSubmit }: Props = $props();

	let grade_level = $state('');
	let subject = $state('');
	let duration_minutes = $state(50);
	let resource_type = $state<V3InputForm['resource_type']>('lesson');

	let topic = $state('');
	let subtopics = $state<string[]>([]);
	let subtopic_candidates = $state<Array<{ id: string; title: string; description: string }>>([]);
	let prior_knowledge = $state('');
	let outcome = $state('');
	let struggle = $state('');
	let resolving_topic = $state(false);
	let narrowNotice = $state<string | null>(null);
	let activeNarrowRequest = 0;

	let learner_level = $state<V3InputForm['learner_level']>('on_grade');
	let reading_level = $state<V3InputForm['reading_level']>('on_grade');
	let language_support = $state<V3InputForm['language_support']>('none');
	let prior_knowledge_level = $state<V3InputForm['prior_knowledge_level']>('new_topic');
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

	const DURATIONS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 75, 90].map((value) => ({
		label: `${value} min`,
		value
	}));

	const RESOURCE_TYPES: Array<{
		value: V3InputForm['resource_type'];
		label: string;
		description: string;
	}> = [
		{
			value: 'lesson',
			label: 'Lesson',
			description: 'Full explanation and guided practice.'
		},
		{
			value: 'mini_booklet',
			label: 'Mini booklet',
			description: 'Compact guided learning students can work through.'
		},
		{
			value: 'worksheet',
			label: 'Worksheet',
			description: 'Practice once the concept has already been taught.'
		},
		{
			value: 'quiz',
			label: 'Quiz',
			description: 'Formal assessment with scored questions.'
		},
		{
			value: 'exit_ticket',
			label: 'Exit ticket',
			description: 'Short end-of-lesson understanding check.'
		},
		{
			value: 'practice_set',
			label: 'Practice set',
			description: 'Repetition and fluency with minimal explanation.'
		},
		{
			value: 'quick_explainer',
			label: 'Quick explainer',
			description: 'Focused concept explainer or reference card.'
		}
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
		{ value: 'none', label: 'No additional language support' },
		{ value: 'some_ell', label: 'Some ELL learners' },
		{ value: 'many_ell', label: 'Many ELL learners' }
	];

	const PRIOR_KNOWLEDGE_OPTIONS: Array<{ value: V3InputForm['prior_knowledge_level']; label: string }> =
		[
			{ value: 'new_topic', label: 'Brand new topic' },
			{ value: 'some_background', label: 'Some background knowledge' },
			{ value: 'reviewing', label: 'Reviewing something taught before' }
		];

	function toggleSubtopic(title: string) {
		const already = subtopics.includes(title);
		if (already) {
			subtopics = subtopics.filter((item) => item !== title);
		} else if (subtopics.length < 3) {
			subtopics = [...subtopics, title];
		}
	}

	async function resolveTopic() {
		const cleaned = topic.trim();
		if (!cleaned || !grade_level || !subject || resolving_topic) return;
		const requestId = ++activeNarrowRequest;
		resolving_topic = true;
		narrowNotice = null;
		try {
			const candidates = await narrowTopic({
				topic: cleaned,
				grade_level,
				subject
			});
			if (requestId !== activeNarrowRequest) return;
			subtopic_candidates = candidates;
			subtopics = [];
			if (candidates.length === 0) {
				narrowNotice = 'No narrower suggestions came back for this topic. You can still continue with the topic as entered.';
			}
		} catch {
			if (requestId !== activeNarrowRequest) return;
			const parts = cleaned
				.split(/[,;:()/-]+/)
				.map((part) => part.trim())
				.filter((part) => part.length > 2)
				.slice(0, 3);
			subtopic_candidates = (parts.length > 0 ? parts : [cleaned]).map((title, index) => ({
				id: `local-${index + 1}`,
				title,
				description: 'Use this focus for the generated resource.'
			}));
			subtopics = [];
			narrowNotice =
				'Topic narrowing could not reach the live service, so local fallback suggestions are shown instead.';
		} finally {
			if (requestId === activeNarrowRequest) {
				resolving_topic = false;
			}
		}
	}

	const canSubmit = $derived(
		grade_level !== '' && subject !== '' && topic.trim().length > 2 && outcome.trim().length > 2
	);

	function handleSubmit(event: Event) {
		event.preventDefault();
		if (!canSubmit) return;
		onSubmit({
			grade_level,
			subject,
			duration_minutes: Number(duration_minutes),
			resource_type,
			topic: topic.trim(),
			subtopics,
			prior_knowledge: prior_knowledge.trim(),
			outcome: outcome.trim(),
			struggle: struggle.trim(),
			learner_level,
			reading_level,
			language_support,
			prior_knowledge_level,
			free_text: free_text.trim()
		});
	}
</script>

<div class="mx-auto max-w-4xl space-y-8 px-4 py-10">
	<header class="space-y-3 text-center">
		<p class="text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">Lectio v4 Studio</p>
		<h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">Start with intent, not format.</h1>
		<p class="mx-auto max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
			Pick the resource you want, describe what learners should achieve, and tell us where they may
			get stuck. We will infer the best lesson mode from there.
		</p>
	</header>

	<form class="space-y-8" onsubmit={handleSubmit}>
		<section class="rounded-3xl border border-border/60 bg-card p-5 shadow-sm space-y-4">
			<h2 class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Class setup</h2>
			<div class="grid gap-3 sm:grid-cols-3">
				<label class="grid gap-1 text-sm font-medium">
					<span>Grade level</span>
					<select
						class="rounded-xl border border-input bg-background px-3 py-2"
						bind:value={grade_level}
						aria-label="Grade level"
					>
						<option value="">Choose...</option>
						{#each GRADE_LEVELS as grade}
							<option value={grade}>{grade}</option>
						{/each}
					</select>
				</label>
				<label class="grid gap-1 text-sm font-medium">
					<span>Subject</span>
					<select
						class="rounded-xl border border-input bg-background px-3 py-2"
						bind:value={subject}
						aria-label="Subject"
					>
						<option value="">Choose...</option>
						{#each SUBJECTS as item}
							<option value={item}>{item}</option>
						{/each}
					</select>
				</label>
				<label class="grid gap-1 text-sm font-medium">
					<span>Duration</span>
					<select
						class="rounded-xl border border-input bg-background px-3 py-2"
						bind:value={duration_minutes}
						aria-label="Duration"
					>
						{#each DURATIONS as duration}
							<option value={duration.value}>{duration.label}</option>
						{/each}
					</select>
				</label>
			</div>
		</section>

		<section class="rounded-3xl border border-border/60 bg-card p-5 shadow-sm space-y-4">
			<div class="space-y-1">
				<p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 1</p>
				<h2 class="text-xl font-semibold tracking-tight">Choose the resource type</h2>
			</div>
			<div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
				{#each RESOURCE_TYPES as option}
					<button
						type="button"
						class={`rounded-2xl border p-4 text-left transition-colors ${
							resource_type === option.value
								? 'border-primary bg-primary/10'
								: 'border-border/60 bg-background hover:border-primary/40'
						}`}
						onclick={() => (resource_type = option.value)}
					>
						<p class="text-sm font-semibold">{option.label}</p>
						<p class="mt-1 text-sm leading-5 text-muted-foreground">{option.description}</p>
					</button>
				{/each}
			</div>
		</section>

		<section class="rounded-3xl border border-border/60 bg-card p-5 shadow-sm space-y-4">
			<div class="space-y-1">
				<p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 2</p>
				<h2 class="text-xl font-semibold tracking-tight">Define the learning intent</h2>
			</div>
			<label class="grid gap-1 text-sm font-medium">
				<span>Topic</span>
				<div class="flex gap-2">
					<input
						class="flex-1 rounded-xl border border-input bg-background px-3 py-2"
						bind:value={topic}
						placeholder="e.g. Equivalent fractions"
					/>
					<button
						type="button"
						class="rounded-xl border border-input px-3 py-2 text-sm"
						disabled={resolving_topic || !topic.trim() || !grade_level || !subject}
						onclick={resolveTopic}
					>
						{resolving_topic ? 'Narrowing...' : 'Narrow'}
					</button>
				</div>
			</label>

			{#if narrowNotice}
				<p class="text-sm text-muted-foreground" role="status">{narrowNotice}</p>
			{/if}

			{#if subtopic_candidates.length > 0}
				<div class="space-y-2">
					<p class="text-sm text-muted-foreground">Pick up to 3 focus areas</p>
					<div class="flex flex-wrap gap-2">
						{#each subtopic_candidates as candidate}
							{@const selected = subtopics.includes(candidate.title)}
							<button
								type="button"
								class={`rounded-full border px-3 py-1 text-sm ${
									selected
										? 'border-primary bg-primary text-primary-foreground'
										: 'border-input bg-background'
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

			<div class="grid gap-3 sm:grid-cols-2">
				<label class="grid gap-1 text-sm font-medium">
					<span>Desired outcome</span>
					<textarea
						class="min-h-[110px] rounded-xl border border-input bg-background px-3 py-2 text-sm"
						bind:value={outcome}
						placeholder="By the end, students should be able to..."
					></textarea>
				</label>
				<label class="grid gap-1 text-sm font-medium">
					<span>Likely struggle</span>
					<textarea
						class="min-h-[110px] rounded-xl border border-input bg-background px-3 py-2 text-sm"
						bind:value={struggle}
						placeholder="Where are they most likely to get stuck?"
					></textarea>
				</label>
			</div>

			<label class="grid gap-1 text-sm font-medium">
				<span>
					What have they already covered?
					<span class="font-normal text-muted-foreground">(optional)</span>
				</span>
				<input
					class="rounded-xl border border-input bg-background px-3 py-2"
					bind:value={prior_knowledge}
					placeholder="e.g. Unit fractions, equal sharing"
				/>
			</label>
		</section>

		<section class="rounded-3xl border border-border/60 bg-card p-5 shadow-sm space-y-4">
			<div class="space-y-1">
				<p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 3</p>
				<h2 class="text-xl font-semibold tracking-tight">Tune for this class</h2>
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<label class="grid gap-1 text-sm font-medium">
					<span>Overall level</span>
					<select bind:value={learner_level} class="rounded-xl border border-input bg-background px-3 py-2">
						{#each LEVELS as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Reading level</span>
					<select bind:value={reading_level} class="rounded-xl border border-input bg-background px-3 py-2">
						{#each READING_LEVELS as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Language support</span>
					<select bind:value={language_support} class="rounded-xl border border-input bg-background px-3 py-2">
						{#each LANGUAGE_OPTIONS as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>

				<label class="grid gap-1 text-sm font-medium">
					<span>Prior knowledge level</span>
					<select bind:value={prior_knowledge_level} class="rounded-xl border border-input bg-background px-3 py-2">
						{#each PRIOR_KNOWLEDGE_OPTIONS as option}
							<option value={option.value}>{option.label}</option>
						{/each}
					</select>
				</label>
			</div>

			<label class="grid gap-1 text-sm font-medium">
				<span>
					Anything else to keep in mind?
					<span class="font-normal text-muted-foreground">(optional)</span>
				</span>
				<textarea
					class="min-h-[90px] rounded-xl border border-input bg-background px-3 py-2 text-sm"
					bind:value={free_text}
					placeholder="Specific examples, constraints, tone, or anything else worth knowing..."
				></textarea>
			</label>
		</section>

		<button
			type="submit"
			disabled={!canSubmit}
			class="w-full rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
		>
			Build the skeleton
		</button>
	</form>
</div>

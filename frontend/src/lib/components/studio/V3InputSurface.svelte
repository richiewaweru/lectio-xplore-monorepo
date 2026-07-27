<script lang="ts">
	import { onMount } from 'svelte';
	import { getProfile } from '$lib/api/profile';
	import { narrowTopic, proposeIntent } from '$lib/api/v3';
	import type { V3InputForm } from '$lib/types/v3';

	interface Props {
		onSubmit: (form: V3InputForm, classLabel: string | null) => void;
	}

	let { onSubmit }: Props = $props();

	let grade_level = $state('');
	let subject = $state('');
	let class_label = $state('');
	let learner_level = $state<V3InputForm['learner_level']>('on_grade');
	let reading_level = $state<V3InputForm['reading_level']>('on_grade');
	let language_support = $state<V3InputForm['language_support']>('none');
	let duration_minutes = $state(50);
	let resource_type = $state<V3InputForm['resource_type']>('lesson');
	let prior_knowledge_level = $state<V3InputForm['prior_knowledge_level']>('new_topic');
	let topic = $state('');
	let subtopics = $state<string[]>([]);
	let subtopic_candidates = $state<Array<{ id: string; title: string; description: string }>>([]);
	let topic_state = $state<'editing' | 'narrowing' | 'candidates' | 'confirmed'>('editing');
	let confirmedTopic = $state<string | null>(null);
	let outcome = $state('');
	let struggle = $state('');
	let prior_knowledge = $state('');
	let free_text = $state('');
	let proposing_intent = $state(false);
	let narrowNotice = $state<string | null>(null);
	let drafts_stale = $state(false);
	let drafts_rendered = $state(false);
	let generatedDrafts = $state<{ outcome: string; struggle: string; prior_knowledge: string } | null>(null);
	let activeNarrowRequest = 0;
	let activeProposeRequest = 0;
	let narrowTimer: ReturnType<typeof setTimeout> | null = null;
	const resolving_topic = $derived(topic_state === 'narrowing');

	const GRADE_LEVELS = ['Kindergarten', ...Array.from({ length: 12 }, (_, index) => `Grade ${index + 1}`)];
	const SUBJECTS = ['Mathematics', 'English Language Arts', 'Science', 'Biology', 'Chemistry', 'Physics', 'History', 'Geography', 'Economics', 'Computer Science', 'Art', 'Music', 'Physical Education', 'Other'];
	const DURATIONS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 75, 90].map((value) => ({ label: `${value} min`, value }));
	const RESOURCE_TYPES: Array<{ value: V3InputForm['resource_type']; label: string; description: string }> = [
		{ value: 'lesson', label: 'Lesson', description: 'Full explanation and guided practice.' },
		{ value: 'mini_booklet', label: 'Mini booklet', description: 'Compact guided learning students can work through.' },
		{ value: 'worksheet', label: 'Worksheet', description: 'Practice once the concept has already been taught.' },
		{ value: 'quiz', label: 'Quiz', description: 'Formal assessment with scored questions.' },
		{ value: 'exit_ticket', label: 'Exit ticket', description: 'Short end-of-lesson understanding check.' },
		{ value: 'practice_set', label: 'Practice set', description: 'Repetition and fluency with minimal explanation.' },
		{ value: 'quick_explainer', label: 'Quick explainer', description: 'Focused concept explainer or reference card.' }
	];
	const LEVELS: Array<{ value: V3InputForm['learner_level']; label: string }> = [
		{ value: 'below_grade', label: 'Below grade level' }, { value: 'on_grade', label: 'At grade level' }, { value: 'above_grade', label: 'Above grade level' }, { value: 'mixed', label: 'Mixed ability' }
	];
	const READING_LEVELS: Array<{ value: V3InputForm['reading_level']; label: string }> = [
		{ value: 'below_grade', label: 'Below grade reading level' }, { value: 'on_grade', label: 'At grade reading level' }, { value: 'above_grade', label: 'Above grade reading level' }, { value: 'mixed', label: 'Mixed' }
	];
	const LANGUAGE_OPTIONS: Array<{ value: V3InputForm['language_support']; label: string }> = [
		{ value: 'none', label: 'No additional language support' }, { value: 'some_ell', label: 'Some ELL learners' }, { value: 'many_ell', label: 'Many ELL learners' }
	];
	const PRIOR_KNOWLEDGE_OPTIONS: Array<{ value: V3InputForm['prior_knowledge_level']; label: string }> = [
		{ value: 'new_topic', label: 'Brand new topic' }, { value: 'some_background', label: 'Some background knowledge' }, { value: 'reviewing', label: 'Reviewing something taught before' }
	];

	function markDraftsStale(): void {
		if (drafts_rendered) drafts_stale = true;
	}

	function hasEditedDrafts(): boolean {
		return generatedDrafts !== null && (outcome !== generatedDrafts.outcome || struggle !== generatedDrafts.struggle || prior_knowledge !== generatedDrafts.prior_knowledge);
	}

	async function resolveTopic(): Promise<void> {
		const cleaned = topic.trim();
		if (!cleaned || cleaned.length <= 2 || !grade_level || !subject) return;
		const requestId = ++activeNarrowRequest;
		topic_state = 'narrowing';
		narrowNotice = null;
		try {
			const candidates = await narrowTopic({ topic: cleaned, grade_level, subject });
			if (requestId !== activeNarrowRequest) return;
			subtopic_candidates = candidates;
			subtopics = [];
			topic_state = 'candidates';
			if (candidates.length === 0) narrowNotice = 'No narrower suggestions came back. You can continue with the topic as entered.';
		} catch {
			if (requestId !== activeNarrowRequest) return;
			const parts = cleaned.split(/[,;:()/-]+/).map((part) => part.trim()).filter((part) => part.length > 2).slice(0, 4);
			subtopic_candidates = (parts.length > 0 ? parts : [cleaned]).map((title, index) => ({ id: `local-${index + 1}`, title, description: 'Students focus on this teachable slice, using the generated resource.' }));
			subtopics = [];
			topic_state = 'candidates';
			narrowNotice = 'Topic narrowing could not reach the live service, so local fallback suggestions are shown instead.';
		}
	}

	function scheduleTopicNarrow(): void {
		markDraftsStale();
		if (narrowTimer) clearTimeout(narrowTimer);
		narrowTimer = null;

		const cleaned = topic.trim();
		if (cleaned === confirmedTopic) return;

		if (topic_state === 'narrowing') ++activeNarrowRequest;
		if (proposing_intent) {
			++activeProposeRequest;
			proposing_intent = false;
		}
		topic_state = 'editing';
		subtopic_candidates = [];
		subtopics = [];
		narrowNotice = null;

		if (cleaned.length <= 2) return;
		if (!grade_level || !subject) {
			narrowNotice = 'Pick a grade and subject first.';
			return;
		}
		narrowTimer = setTimeout(() => { void resolveTopic(); }, 600);
	}

	async function draftIntent(force = false): Promise<void> {
		const confirmed = confirmedTopic ?? topic.trim();
		if (!grade_level || !subject || confirmed.length <= 2 || (!force && drafts_rendered)) return;
		const requestId = ++activeProposeRequest;
		proposing_intent = true;
		try {
			const drafts = await proposeIntent({ grade_level, subject, resource_type, duration_minutes: Number(duration_minutes), learner_level, reading_level, language_support, prior_knowledge_level, topic: confirmed, subtopics });
			if (requestId !== activeProposeRequest) return;
			outcome = drafts.outcome_draft;
			struggle = drafts.struggle_draft;
			prior_knowledge = drafts.prior_knowledge_draft;
			generatedDrafts = { outcome, struggle, prior_knowledge };
			drafts_rendered = true;
			drafts_stale = false;
		} catch {
			if (requestId !== activeProposeRequest) return;
			if (!drafts_rendered) {
				outcome = '';
				struggle = '';
				prior_knowledge = '';
			}
		} finally {
			if (requestId === activeProposeRequest) proposing_intent = false;
		}
	}

	function confirmTopic(useSuggestions = true): void {
		if (!grade_level || !subject || topic.trim().length <= 2) return;
		if (!useSuggestions) subtopics = [];
		confirmedTopic = topic.trim();
		topic_state = 'confirmed';
		void draftIntent();
	}

	function toggleSubtopic(title: string): void {
		const already = subtopics.includes(title);
		if (already) subtopics = subtopics.filter((item) => item !== title);
		else if (subtopics.length < 4) subtopics = [...subtopics, title];
		else return;
	}

	function refreshDrafts(): void {
		if (hasEditedDrafts() && !confirm('Replace your edited intent drafts with fresh drafts for this class?')) return;
		void draftIntent(true);
	}

	const canSubmit = $derived(grade_level !== '' && subject !== '' && topic.trim().length > 2 && outcome.trim().length > 2);

	onMount(async () => {
		try {
			const profile = await getProfile();
			const candidate = profile.default_audience_description?.trim() ?? '';
			if (candidate.length > 0 && candidate.length < 40) class_label = candidate;
		} catch {
			// Class is optional; profile-loading failures must not block Studio.
		}
	});

	function handleSubmit(event: Event): void {
		event.preventDefault();
		if (!canSubmit) return;
		onSubmit(
			{ grade_level, subject, duration_minutes: Number(duration_minutes), resource_type, topic: topic.trim(), subtopics, prior_knowledge: prior_knowledge.trim(), outcome: outcome.trim(), struggle: struggle.trim(), learner_level, reading_level, language_support, prior_knowledge_level, free_text: free_text.trim() },
			class_label.trim() || null
		);
	}
</script>

<div class="mx-auto max-w-4xl space-y-8 px-4 py-10">
	<header class="space-y-3 text-center">
		<p class="text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">Lectio v4 Studio</p>
		<h1 class="text-3xl font-semibold tracking-tight sm:text-4xl">Start with your class, then refine the intent.</h1>
		<p class="mx-auto max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">Give us the class and lesson shape first. We will propose editable lesson intent for you.</p>
	</header>

	<form class="space-y-8" onsubmit={handleSubmit}>
		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
			<div class="space-y-1"><p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 1 / Class shape</p><h2 class="text-xl font-semibold tracking-tight">Who is this lesson for?</h2></div>
			<div class="grid gap-3 sm:grid-cols-2">
				<label class="grid gap-1 text-sm font-medium"><span>Grade level</span><select class="rounded-xl border border-input bg-background px-3 py-2" bind:value={grade_level} aria-label="Grade level" onchange={markDraftsStale}><option value="">Choose...</option>{#each GRADE_LEVELS as grade}<option value={grade}>{grade}</option>{/each}</select></label>
				<label class="grid gap-1 text-sm font-medium"><span>Subject</span><select class="rounded-xl border border-input bg-background px-3 py-2" bind:value={subject} aria-label="Subject" onchange={markDraftsStale}><option value="">Choose...</option>{#each SUBJECTS as item}<option value={item}>{item}</option>{/each}</select></label>
				<label class="grid gap-1 text-sm font-medium sm:col-span-2"><span>Class <span class="font-normal text-muted-foreground">(optional)</span></span><input class="rounded-xl border border-input bg-background px-3 py-2" bind:value={class_label} aria-label="Class" placeholder="Year 7 Science" /></label>
				<label class="grid gap-1 text-sm font-medium"><span>Overall level</span><select bind:value={learner_level} class="rounded-xl border border-input bg-background px-3 py-2" onchange={markDraftsStale}>{#each LEVELS as option}<option value={option.value}>{option.label}</option>{/each}</select></label>
				<label class="grid gap-1 text-sm font-medium"><span>Reading level</span><select bind:value={reading_level} class="rounded-xl border border-input bg-background px-3 py-2" onchange={markDraftsStale}>{#each READING_LEVELS as option}<option value={option.value}>{option.label}</option>{/each}</select></label>
				<label class="grid gap-1 text-sm font-medium sm:col-span-2"><span>Language support</span><select bind:value={language_support} class="rounded-xl border border-input bg-background px-3 py-2" onchange={markDraftsStale}>{#each LANGUAGE_OPTIONS as option}<option value={option.value}>{option.label}</option>{/each}</select></label>
			</div>
		</section>

		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
			<div class="space-y-1"><p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 2 / Lesson shape</p><h2 class="text-xl font-semibold tracking-tight">What are you making?</h2></div>
			<div class="grid gap-3 sm:grid-cols-2"><label class="grid gap-1 text-sm font-medium"><span>Duration</span><select class="rounded-xl border border-input bg-background px-3 py-2" bind:value={duration_minutes} aria-label="Duration">{#each DURATIONS as duration}<option value={duration.value}>{duration.label}</option>{/each}</select></label><label class="grid gap-1 text-sm font-medium"><span>Prior knowledge level</span><select bind:value={prior_knowledge_level} class="rounded-xl border border-input bg-background px-3 py-2" onchange={markDraftsStale}>{#each PRIOR_KNOWLEDGE_OPTIONS as option}<option value={option.value}>{option.label}</option>{/each}</select></label></div>
			<div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{#each RESOURCE_TYPES as option}<button type="button" class={`rounded-2xl border p-4 text-left transition-colors ${resource_type === option.value ? 'border-primary bg-primary/10' : 'border-border/60 bg-background hover:border-primary/40'}`} onclick={() => { resource_type = option.value; markDraftsStale(); }}><p class="text-sm font-semibold">{option.label}</p><p class="mt-1 text-sm leading-5 text-muted-foreground">{option.description}</p></button>{/each}</div>
		</section>

		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
			<div class="space-y-1"><p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 3 / Topic</p><h2 class="text-xl font-semibold tracking-tight">Choose a teachable focus</h2></div>
			<label class="grid gap-1 text-sm font-medium"><span>Topic</span><input class="rounded-xl border border-input bg-background px-3 py-2" bind:value={topic} oninput={scheduleTopicNarrow} aria-label="Topic" placeholder="e.g. Equivalent fractions" /></label>
			{#if resolving_topic}<p class="text-sm text-muted-foreground" role="status">Finding focused options…</p>{/if}
			{#if narrowNotice}<p class="text-sm text-muted-foreground" role="status">{narrowNotice}</p>{/if}
			{#if topic_state === 'candidates'}<div class="space-y-3">{#if subtopic_candidates.length > 0}<p class="text-sm text-muted-foreground">Pick up to 4 focus areas</p><div class="grid gap-2 sm:grid-cols-2">{#each subtopic_candidates as candidate}{@const selected = subtopics.includes(candidate.title)}<button type="button" disabled={!selected && subtopics.length >= 4} class={`rounded-2xl border px-3 py-3 text-left text-sm disabled:cursor-not-allowed disabled:opacity-45 ${selected ? 'border-primary bg-primary/10' : 'border-input bg-background'}`} onclick={() => toggleSubtopic(candidate.title)}><p class="font-semibold">{candidate.title}</p><p class="mt-1 text-muted-foreground">{candidate.description}</p></button>{/each}</div>{/if}<div class="flex flex-wrap items-center gap-3"><button type="button" class="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground" onclick={() => confirmTopic(true)}>Use this topic →</button><button type="button" class="text-sm font-medium text-primary underline-offset-4 hover:underline" onclick={() => confirmTopic(false)}>Skip suggestions — use my topic as-is</button></div></div>{/if}
		</section>

		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm">
			<div class="flex items-start justify-between gap-4"><div class="space-y-1"><p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 4 / Intent</p><h2 class="text-xl font-semibold tracking-tight">Review the lesson intent</h2></div>{#if drafts_stale}<button type="button" class="rounded-full border border-amber-500/50 bg-amber-100 px-3 py-1 text-sm font-medium text-amber-950" onclick={refreshDrafts}>Class changed — refresh drafts?</button>{/if}</div>
			{#if proposing_intent}<div class="grid gap-3 sm:grid-cols-2" aria-label="Drafting lesson intent"><div class="h-28 animate-pulse rounded-xl bg-muted"></div><div class="h-28 animate-pulse rounded-xl bg-muted"></div><div class="h-24 animate-pulse rounded-xl bg-muted sm:col-span-2"></div></div>{:else}<div class="grid gap-3 sm:grid-cols-2"><label class="grid gap-1 text-sm font-medium"><span>Desired outcome</span><textarea class="min-h-[110px] rounded-xl border border-input bg-background px-3 py-2 text-sm" bind:value={outcome} aria-label="Desired outcome" placeholder="By the end, students should be able to..."></textarea></label><label class="grid gap-1 text-sm font-medium"><span>Likely struggle</span><textarea class="min-h-[110px] rounded-xl border border-input bg-background px-3 py-2 text-sm" bind:value={struggle} aria-label="Likely struggle" placeholder="Where are they most likely to get stuck?"></textarea></label><label class="grid gap-1 text-sm font-medium sm:col-span-2"><span>What have they already covered? <span class="font-normal text-muted-foreground">(optional)</span></span><textarea class="min-h-[90px] rounded-xl border border-input bg-background px-3 py-2 text-sm" bind:value={prior_knowledge} aria-label="What have they already covered?" placeholder="e.g. Unit fractions, equal sharing"></textarea></label></div>{/if}
		</section>

		<section class="space-y-4 rounded-3xl border border-border/60 bg-card p-5 shadow-sm"><div class="space-y-1"><p class="text-sm font-semibold uppercase tracking-[0.22em] text-muted-foreground">Step 5 / Anything else</p><h2 class="text-xl font-semibold tracking-tight">Add any final context</h2></div><label class="grid gap-1 text-sm font-medium"><span>Anything else to keep in mind? <span class="font-normal text-muted-foreground">(optional)</span></span><textarea class="min-h-[90px] rounded-xl border border-input bg-background px-3 py-2 text-sm" bind:value={free_text} placeholder="Specific examples, constraints, tone, or anything else worth knowing..."></textarea></label></section>

		<button type="submit" disabled={!canSubmit} class="w-full rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50">Build the skeleton</button>
	</form>
</div>

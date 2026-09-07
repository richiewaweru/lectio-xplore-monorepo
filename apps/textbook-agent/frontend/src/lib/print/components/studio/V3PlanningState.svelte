<script lang="ts">
	import type { V3InputForm, V3SignalSummary } from '$lib/types/v3';

	interface Props {
		form: V3InputForm | null;
		signals?: V3SignalSummary | null;
		planningLabel?: string;
		messages?: string[];
	}

	let {
		form,
		signals = null,
		planningLabel = 'Filling the lesson from the approved skeleton',
		messages = [
			'Mapping your intent to the live resource spec...',
			'Sequencing sections and question flow...',
			'Expanding section briefs one at a time...',
			'Checking continuity and booklet readiness...'
		]
	}: Props = $props();

	const RESOURCE_LABELS: Record<V3InputForm['resource_type'], string> = {
		lesson: 'Lesson',
		mini_booklet: 'Mini booklet',
		worksheet: 'Worksheet',
		quiz: 'Quiz',
		exit_ticket: 'Exit ticket',
		practice_set: 'Practice set',
		quick_explainer: 'Quick explainer'
	};

	const MODE_LABELS: Record<V3SignalSummary['inferred_lesson_mode'], string> = {
		first_exposure: 'First exposure',
		consolidation: 'Consolidation',
		repair: 'Repair',
		retrieval: 'Retrieval',
		transfer: 'Transfer'
	};

	const LEVEL_LABELS: Record<V3InputForm['learner_level'], string> = {
		below_grade: 'Below grade level',
		on_grade: 'At grade level',
		above_grade: 'Above grade level',
		mixed: 'Mixed ability'
	};

	let messageIndex = $state(0);

	$effect(() => {
		const interval = setInterval(() => {
			messageIndex = (messageIndex + 1) % messages.length;
		}, 7000);
		return () => clearInterval(interval);
	});
</script>

<div class="mx-auto max-w-3xl space-y-8 px-4 py-16 text-center">
	<div class="flex justify-center">
		<div class="relative h-16 w-16">
			<div class="absolute inset-0 animate-ping rounded-full bg-primary/15"></div>
			<div class="absolute inset-2 rounded-full bg-primary/35"></div>
			<div class="absolute inset-4 rounded-full bg-primary"></div>
		</div>
	</div>

	<div class="space-y-1">
		<p class="text-lg font-medium transition-all duration-500">{messages[messageIndex]}</p>
		<p class="text-sm text-muted-foreground">{planningLabel}</p>
	</div>

	{#if form}
		<div class="mx-auto max-w-2xl rounded-3xl border border-border/60 bg-card p-6 text-left shadow-sm">
			<div class="flex flex-wrap items-center gap-2">
				<span class="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
					{RESOURCE_LABELS[form.resource_type]}
				</span>
				{#if signals?.inferred_lesson_mode}
					<span
						class={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
							signals.lesson_mode_confidence === 'low'
								? 'bg-amber-100 text-amber-900'
								: 'bg-emerald-100 text-emerald-900'
						}`}
					>
						{MODE_LABELS[signals.inferred_lesson_mode]} mode
						{signals.lesson_mode_confidence === 'low'
							? ' - low confidence'
							: ` - ${signals.lesson_mode_confidence} confidence`}
					</span>
				{/if}
			</div>

			<div class="mt-4 grid gap-3 sm:grid-cols-2">
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Grade</p>
					<p class="font-medium">{form.grade_level}</p>
				</div>
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Subject</p>
					<p class="font-medium">{form.subject}</p>
				</div>
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Duration</p>
					<p class="font-medium">{form.duration_minutes} min</p>
				</div>
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Learner level</p>
					<p class="font-medium">{LEVEL_LABELS[form.learner_level]}</p>
				</div>
			</div>

			<div class="mt-5 space-y-3 border-t border-border/50 pt-4">
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Topic</p>
					<p class="font-medium">{form.topic}</p>
					{#if form.subtopics.length > 0}
						<p class="mt-1 text-sm text-muted-foreground">Focus: {form.subtopics.join(', ')}</p>
					{/if}
				</div>
				<div>
					<p class="text-xs uppercase tracking-wide text-muted-foreground">Outcome</p>
					<p>{form.outcome}</p>
				</div>
				{#if form.struggle}
					<div>
						<p class="text-xs uppercase tracking-wide text-muted-foreground">Likely struggle</p>
						<p>{form.struggle}</p>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

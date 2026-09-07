<script lang="ts">
	import type { V3SignalSummary } from '$lib/types/v3';

	interface Props {
		signals: V3SignalSummary;
		onConfirm: () => void;
		onCorrect: () => void;
	}

	let { signals, onConfirm, onCorrect }: Props = $props();

	const MODE_LABELS: Record<V3SignalSummary['inferred_lesson_mode'], string> = {
		first_exposure: 'First exposure',
		consolidation: 'Consolidation',
		repair: 'Repair',
		retrieval: 'Retrieval',
		transfer: 'Transfer'
	};
</script>

<div class="mx-auto max-w-xl space-y-6 px-4 py-10">
	<h2 class="text-2xl font-semibold">Here is what we inferred</h2>
	<p class="text-muted-foreground">You can continue or go back and sharpen the brief.</p>

	<dl class="space-y-4 rounded-xl border border-border/60 bg-card p-5 shadow-sm">
		<div class="grid gap-1">
			<dt class="text-xs font-semibold uppercase text-muted-foreground">Topic</dt>
			<dd>{signals.topic}</dd>
		</div>
		{#if signals.subtopic}
			<div class="grid gap-1">
				<dt class="text-xs font-semibold uppercase text-muted-foreground">Focus</dt>
				<dd>{signals.subtopic}</dd>
			</div>
		{/if}
		<div class="grid gap-1">
			<dt class="text-xs font-semibold uppercase text-muted-foreground">Goal</dt>
			<dd>{signals.teacher_goal}</dd>
		</div>
		<div class="grid gap-1">
			<dt class="text-xs font-semibold uppercase text-muted-foreground">Inferred mode</dt>
			<dd>{MODE_LABELS[signals.inferred_lesson_mode]} ({signals.lesson_mode_confidence})</dd>
		</div>
		{#if signals.learner_needs.length}
			<div class="grid gap-1">
				<dt class="text-xs font-semibold uppercase text-muted-foreground">Learner needs</dt>
				<dd>{signals.learner_needs.join(', ')}</dd>
			</div>
		{/if}
	</dl>
	<div class="flex flex-col gap-3 sm:flex-row">
		<button
			type="button"
			class="flex-1 rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
			onclick={onConfirm}
		>
			Continue
		</button>
		<button type="button" class="flex-1 rounded-md border border-input px-4 py-3 text-sm font-semibold" onclick={onCorrect}>
			Go back
		</button>
	</div>
</div>

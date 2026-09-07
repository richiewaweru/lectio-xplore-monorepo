<script lang="ts">
	import type { BlueprintPreviewDTO } from '$lib/types/v3';

	interface Props {
		blueprint: BlueprintPreviewDTO;
		onApprove: () => void;
		onAdjust: (instruction: string) => void;
		onCancel?: () => void;
		contextLabel?: string;
		approveLabel?: string;
		cancelLabel?: string;
		parentTitle?: string | null;
		/** Plain-language summary of the one thing this lesson teaches. Falls back to the register summary. */
		objective?: string | null;
		/** Plain-language misconceptions to watch for. Omitted entirely when empty. */
		watchFor?: string[];
	}

	let {
		blueprint,
		onApprove,
		onAdjust,
		onCancel,
		contextLabel = 'Lesson plan',
		approveLabel = 'Make the lesson',
		cancelLabel = 'Back',
		parentTitle = null,
		objective = null,
		watchFor = []
	}: Props = $props();

	let adjustText = $state('');
	let showAdjust = $state(false);

	const difficultyLabel: Record<string, string> = {
		warm: 'Warm',
		medium: 'Medium',
		cold: 'Cold',
		transfer: 'Transfer'
	};
</script>

<div class="mx-auto max-w-3xl space-y-8 px-4 py-10">
	<header class="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 pb-6">
		<div>
			<p class="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{contextLabel}</p>
			<h2 class="mt-1 text-3xl font-semibold">{blueprint.title}</h2>
			{#if parentTitle}
				<p class="mt-1 text-xs text-muted-foreground">Based on: {parentTitle}</p>
			{/if}
			<p class="mt-2 text-sm font-medium text-foreground">
				The one thing this lesson teaches: {objective ?? blueprint.register_summary}
			</p>
		</div>
		<span class="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize">
			{blueprint.resource_type.replace(/_/g, ' ')}
		</span>
	</header>

	{#if watchFor.length}
		<section class="rounded-xl border border-border/60 bg-muted/30 p-4">
			<h3 class="text-sm font-semibold">Watch for</h3>
			<ul class="mt-2 list-inside list-disc text-sm text-muted-foreground">
				{#each watchFor as line}
					<li>{line}</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if blueprint.anchor}
		<section class="space-y-3">
			<h3 class="text-lg font-semibold">Anchor</h3>
			<div class="rounded-xl border border-border/60 bg-card p-4">
				<p class="font-semibold">{blueprint.anchor.label}</p>
				<dl class="mt-3 grid gap-2 text-sm">
					{#each Object.entries(blueprint.anchor.facts) as [key, val]}
						<div>
							<dt class="text-muted-foreground">{key.replace(/_/g, ' ')}</dt>
							<dd>{val}</dd>
						</div>
					{/each}
					{#if blueprint.anchor.correct_result}
						<div>
							<dt class="text-muted-foreground">Correct answer</dt>
							<dd>{blueprint.anchor.correct_result}</dd>
						</div>
					{/if}
				</dl>
				<p class="mt-3 text-xs text-muted-foreground">
					Reuse: {blueprint.anchor.reuse_scope.replace(/_/g, ' ')}
				</p>
			</div>
		</section>
	{/if}

	<section class="space-y-3">
		<h3 class="text-lg font-semibold">Lesson sections</h3>
		<ol class="space-y-4">
			{#each blueprint.section_plan as section}
				<li class="rounded-xl border border-border/60 bg-card p-4">
					<div class="flex flex-wrap items-baseline justify-between gap-2">
						<p class="font-semibold">{section.title}</p>
						<span class="text-xs text-muted-foreground">
							{section.components.map((c) => c.teacher_label).join(' · ')}
						</span>
					</div>
					<p class="mt-2 text-sm text-muted-foreground">
						{(section.learning_intents?.length
							? section.learning_intents
							: section.learning_intent
								? [section.learning_intent]
								: []
						).join(' · ') || section.title}
					</p>
				</li>
			{/each}
		</ol>
	</section>

	{#if blueprint.question_plan.length}
		<section class="space-y-3">
			<h3 class="text-lg font-semibold">Practice questions</h3>
			<div class="overflow-x-auto rounded-xl border border-border/60">
				<table class="w-full text-left text-sm">
					<thead class="bg-muted/50 text-xs uppercase text-muted-foreground">
						<tr>
							<th class="px-3 py-2">Item</th>
							<th class="px-3 py-2">Difficulty</th>
							<th class="px-3 py-2">Diagram</th>
						</tr>
					</thead>
					<tbody>
						{#each blueprint.question_plan as q, i}
							<tr class="border-t border-border/40">
								<td class="px-3 py-2">Q{i + 1}</td>
								<td class="px-3 py-2 capitalize">{difficultyLabel[q.difficulty] ?? q.difficulty}</td>
								<td class="px-3 py-2">{q.diagram_required ? 'Yes' : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}

	<div class="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
		<button
			type="button"
			class="flex-1 rounded-md bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
			onclick={onApprove}
		>
			{approveLabel}
		</button>
		{#if onCancel}
			<button
				type="button"
				class="flex-1 rounded-md border border-input px-4 py-3 text-sm font-semibold"
				onclick={onCancel}
			>
				{cancelLabel}
			</button>
		{/if}
		<button
			type="button"
			class="flex-1 rounded-md border border-input px-4 py-3 text-sm font-semibold"
			onclick={() => (showAdjust = !showAdjust)}
		>
			something off? type it
		</button>
	</div>

	{#if showAdjust}
		<div class="space-y-3 rounded-xl border border-border/60 bg-muted/20 p-4">
			<textarea
				class="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
				bind:value={adjustText}
				placeholder="What's off?"
			></textarea>
			<button
				type="button"
				class="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
				disabled={adjustText.trim().length === 0}
				onclick={() => {
					onAdjust(adjustText.trim());
					adjustText = '';
					showAdjust = false;
				}}
			>
				Update
			</button>
		</div>
	{/if}
</div>

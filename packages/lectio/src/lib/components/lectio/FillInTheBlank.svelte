<script lang="ts">
	import type { FillInBlankContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { usePrintMode } from '$lib/utils/printContext';
	import {
		evaluateFillBlank,
		fillBlankContentToInteractionContract
	} from '$lib/learn/interaction-contract';

	let { content }: { content: FillInBlankContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
	const contract = $derived(fillBlankContentToInteractionContract(content));

	const blankCount = $derived(content.segments.filter((s) => s.is_blank).length);
	let blanks = $state<string[]>([]);
	let submitted = $state(false);

	$effect(() => {
		if (blanks.length !== blankCount) {
			blanks = Array.from({ length: blankCount }, (_, i) => blanks[i] ?? '');
		}
	});

	const evaluation = $derived(
		submitted
			? evaluateFillBlank(
					{ answers: contract.config.answers as string[] },
					{ blanks },
					contract.feedback
				)
			: null
	);

	function blankIndexForSegment(segmentIndex: number): number {
		let n = 0;
		for (let i = 0; i < segmentIndex; i++) {
			if (content.segments[i]?.is_blank) n += 1;
		}
		return n;
	}

	function setBlank(index: number, value: string) {
		if (submitted) return;
		const next = [...blanks];
		next[index] = value;
		blanks = next;
	}

	function reset() {
		blanks = Array.from({ length: blankCount }, () => '');
		submitted = false;
	}
</script>

{#if printMode}
	<div class="fill-blank-print" data-print-container="atomic">
		{#if content.instruction}
			<p class="fill-blank-print-instruction">{content.instruction}</p>
		{/if}
		<div class="fill-blank-print-passage">
			{#each content.segments as segment}
				{#if segment.is_blank}
					<span class="fill-blank-print-blank">________________</span>
				{:else}
					{segment.text}
				{/if}
			{/each}
		</div>
		{#if content.word_bank?.length}
			<div class="fill-blank-print-word-bank">
				<p class="fill-blank-print-word-bank-label"><strong>Word Bank:</strong></p>
				<div class="fill-blank-print-words">
					{#each content.word_bank as word}
						<span class="fill-blank-print-word">{word}</span>
					{/each}
				</div>
			</div>
		{/if}
	</div>
{:else}
	<Card class="border-border/60 rh-pad-card" data-testid="fill-blank-interaction">
		{#if content.instruction}
			<p class="text-sm font-medium leading-relaxed">{content.instruction}</p>
		{/if}

		<div class="mt-3 text-sm leading-loose" aria-label={contract.accessibility.aria_label}>
			{#each content.segments as segment, segmentIndex}
				{#if segment.is_blank}
					{@const bi = blankIndexForSegment(segmentIndex)}
					<input
						class="mx-0.5 inline-block min-w-[5rem] border-b-2 border-dashed border-primary/40 bg-transparent px-1 text-center outline-none"
						type="text"
						aria-label={`Blank ${bi + 1}`}
						value={blanks[bi] ?? ''}
						disabled={submitted}
						oninput={(e) => setBlank(bi, (e.currentTarget as HTMLInputElement).value)}
						onkeydown={(e) => {
							if (e.key === 'Enter' && !submitted) {
								e.preventDefault();
								submitted = true;
							}
						}}
					/>
				{:else}
					{segment.text}
				{/if}
			{/each}
		</div>

		{#if content.word_bank?.length}
			<div class="mt-4 rounded-lg bg-muted/40 p-3">
				<p class="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
					Word bank
				</p>
				<div class="mt-2 flex flex-wrap gap-2">
					{#each content.word_bank as word}
						<Badge variant="outline">{word}</Badge>
					{/each}
				</div>
			</div>
		{/if}

		<div class="mt-4 flex flex-wrap gap-2">
			<button
				type="button"
				class="rounded-lg border border-emerald-700 bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
				disabled={submitted || blanks.every((b) => !b.trim())}
				onclick={() => (submitted = true)}
			>
				Check
			</button>
			{#if submitted}
				<button
					type="button"
					class="rounded-lg border border-border px-3 py-2 text-sm"
					onclick={reset}
				>
					Try again
				</button>
			{/if}
		</div>

		{#if evaluation}
			<p class="mt-3 text-sm" data-outcome={evaluation.outcome} role="status">
				{evaluation.feedback}
			</p>
		{/if}
	</Card>
{/if}

<style>
	.fill-blank-print {
		page-break-inside: avoid;
		margin: 1rem 0;
	}

	.fill-blank-print-instruction {
		font-weight: 500;
		margin-bottom: 0.75rem;
	}

	.fill-blank-print-passage {
		line-height: 2;
		margin-bottom: 1.5rem;
	}

	.fill-blank-print-blank {
		display: inline-block;
		min-width: 4rem;
		border-bottom: 1px solid #000;
		margin: 0 0.25rem;
	}

	.fill-blank-print-word-bank {
		padding: var(--rh-pad-card-tight);
		border: 2px solid #e5e7eb;
		background: #f9fafb;
	}

	.fill-blank-print-word-bank-label {
		margin-bottom: 0.75rem;
	}

	.fill-blank-print-words {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.fill-blank-print-word {
		padding: 0.25rem 0.75rem;
		border: 1px solid #d1d5db;
		border-radius: 0.25rem;
	}
</style>

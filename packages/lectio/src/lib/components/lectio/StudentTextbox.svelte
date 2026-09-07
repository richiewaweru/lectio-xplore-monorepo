<script lang="ts">
	import type { StudentTextboxContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';
	import RuledLines from '$lib/print/RuledLines.svelte';

	let { content }: { content: StudentTextboxContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
	const lines = $derived(content.lines ?? 4);
</script>

{#if printMode}
	<div class="textbox-print student-textbox" data-print-container="atomic">
		<RuledLines {lines} label={content.prompt} />
		<p class="student-textbox__label">Response Area</p>
	</div>
{:else}
<Card class="border-border/60 rh-pad-card">
	{#if content.label}
		<p class="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
			{content.label}
		</p>
	{/if}
	<p class="mt-1 text-sm leading-relaxed">{content.prompt}</p>
	<div
		class="mt-3 rounded-lg border border-dashed border-border/80 bg-white/50 p-3"
		style="min-height: {lines * 1.75}rem"
	>
		<p class="text-xs text-muted-foreground/50 italic">Write your answer here...</p>
	</div>
</Card>
{/if}

<style>
	.textbox-print {
		page-break-inside: avoid;
		margin: 1rem 0;
	}

	:global(.textbox-print .ruled-lines) {
		border: 1.5px solid #ccc;
		border-radius: 2px;
		min-height: 80px;
		padding: 8px 12px 4px;
		background: repeating-linear-gradient(
			to bottom,
			transparent,
			transparent 27px,
			#ddd 27px,
			#ddd 28px
		);
	}

	.student-textbox__label {
		font-size: 0.8em;
		font-style: italic;
		color: #999;
		text-align: right;
		margin-top: 0.25rem;
	}
</style>

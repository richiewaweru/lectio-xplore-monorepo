<script lang="ts">
	import type { InsightStripContent } from '$lib/schema/types';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let { content }: { content: InsightStripContent } = $props();
</script>

<section class="insight-strip" data-print-container="table" data-print-color-reset="true">
	{#each content.cells as cell}
		<div
			class="insight-strip__cell {cell.highlight
				? 'border-violet-200 bg-violet-50 text-violet-950'
				: 'border-border/70 bg-white/82 text-foreground'}"
		>
			<p class="insight-strip__label">{cell.label}</p>
			<p class="insight-strip__value">{@html renderInlineMarkdown(cell.value)}</p>
			{#if cell.note}
				<p class="insight-strip__note">{@html renderInlineMarkdown(cell.note)}</p>
			{/if}
		</div>
	{/each}
</section>

<style>
	.insight-strip {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
		gap: 1rem;
	}

	.insight-strip__cell {
		border-top: 3px solid var(--accent, hsl(var(--primary)));
		padding: 0.6rem 0.4rem;
		border-radius: 2px;
	}

	.insight-strip__value {
		font-weight: 700;
		font-size: 1em;
		margin-bottom: 0.2rem;
		line-height: 1.3;
	}

	.insight-strip__label {
		font-size: 0.8em;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
		text-transform: uppercase;
		letter-spacing: 0.06em;
		margin-bottom: 0.25rem;
	}

	.insight-strip__note {
		font-size: 0.8em;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
		line-height: 1.4;
		margin-top: 0.2rem;
	}

	@media print {
		.insight-strip {
			page-break-inside: avoid;
		}

		.insight-strip__cell {
			border-top: 2px solid #333;
		}
	}
</style>

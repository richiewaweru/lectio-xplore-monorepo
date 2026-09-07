<script lang="ts">
	import type { KeyFactContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import RichText from './RichText.svelte';
	import MathFormula from './MathFormula.svelte';

	let { content }: { content: KeyFactContent } = $props();
</script>

{#if content.formula}
	<div class="key-fact key-fact--equation" data-print-container="atomic">
		{#if content.fact}
			<div class="key-fact__fact">
				<RichText text={content.fact} />
			</div>
		{/if}
		<div class="key-fact__formula">
			<MathFormula formula={content.formula} displayMode />
		</div>
		{#if content.context}
			<div class="key-fact__context">
				<RichText text={content.context} />
			</div>
		{/if}
		{#if content.source}
			<p class="key-fact__source">Source: {content.source}</p>
		{/if}
	</div>
{:else}
	<Card class="border-primary/15 bg-primary/4 rh-pad-card key-fact" data-print-container="atomic">
		<p class="text-2xl font-semibold leading-tight font-serif text-foreground">
			<RichText text={content.fact} />
		</p>
		{#if content.context}
			<p class="mt-2 text-sm leading-relaxed text-muted-foreground">
				<RichText text={content.context} />
			</p>
		{/if}
		{#if content.source}
			<p class="mt-1 text-xs text-muted-foreground/70">
				Source: {content.source}
			</p>
		{/if}
	</Card>
{/if}

<style>
	.key-fact--equation {
		text-align: center;
		padding: 1.5rem 2rem;
		border: 1.5px solid var(--border, hsl(var(--border)));
		border-radius: 4px;
		background: var(--muted, hsl(var(--muted) / 0.35));
	}

	.key-fact--equation .key-fact__formula {
		font-size: 1.5em;
		margin-bottom: 0.75rem;
	}

	.key-fact--equation .key-fact__fact {
		font-size: 0.85em;
		font-weight: 600;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
		margin-bottom: 0.25rem;
	}

	.key-fact--equation .key-fact__context {
		font-size: 0.85em;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
	}

	.key-fact__source {
		margin-top: 0.5rem;
		font-size: 0.75rem;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
	}

	@media print {
		.key-fact--equation {
			background: none;
			border: 2px solid #333;
			padding: 1.25rem 1.5rem;
		}
	}
</style>

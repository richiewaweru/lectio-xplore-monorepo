<script lang="ts">
	import type { DefinitionContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { ChevronRight } from 'lucide-svelte';
	import MathFormula from './MathFormula.svelte';
	import { renderInlineMarkdown, looksLikeLatex } from '$lib/utils/markdown';

	let { content }: { content: DefinitionContent } = $props();
	let showFormal = $state(false);
</script>

<Card class="border-l-4 border-l-fuchsia-500 bg-fuchsia-50/65" data-lectio-block="definition" data-print-container="atomic">
	<div class="rh-gap-component rh-pad-card">
		<div class="space-y-2">
			<p class="eyebrow text-fuchsia-600">Define</p>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.term}</h3>
		</div>

		<div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
			<p class="text-base leading-7 text-foreground/85">
				{@html renderInlineMarkdown(showFormal ? content.formal : content.plain)}
			</p>

			{#if content.symbol}
				<div class="rh-radius-card border border-fuchsia-200 bg-white/88 px-4 py-3 text-center text-3xl font-semibold text-fuchsia-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
					{content.symbol}
				</div>
			{/if}
		</div>

		<Button
			variant="ghost"
			size="sm"
			onclick={() => (showFormal = !showFormal)}
			class="w-fit px-0 text-fuchsia-700 hover:bg-transparent hover:text-fuchsia-800"
			data-print-role="definition-toggle"
		>
			{showFormal ? 'Show plain language' : 'Show formal definition'}
			<ChevronRight class="h-4 w-4 transition-transform {showFormal ? 'rotate-90' : ''}" />
		</Button>

		{#if content.etymology}
			<p class="text-sm italic text-muted-foreground">Etymology: {content.etymology}</p>
		{/if}

		{#if content.notation}
			<div class="rh-radius-card border border-fuchsia-200 bg-white/85 p-4" data-block-part="notation">
				<p class="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-fuchsia-700/80">
					Notation
				</p>
				{#if looksLikeLatex(content.notation)}
					<MathFormula formula={content.notation} displayMode class="text-lg text-primary" />
				{:else}
					<p class="text-base leading-7 text-primary">
						{@html renderInlineMarkdown(content.notation)}
					</p>
				{/if}
			</div>
		{/if}

		{#if content.examples?.length}
			<div class="space-y-2">
				<p class="text-xs font-semibold uppercase tracking-[0.18em] text-fuchsia-700/80">
					Usage examples
				</p>
				<ul class="space-y-1">
					{#each content.examples as example}
						<li class="text-sm italic text-muted-foreground">
							"{example.replace(/^"|"$/g, '')}"
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if content.related_terms?.length}
			<div class="flex flex-wrap gap-2" data-print-role="definition-related-terms">
				{#each content.related_terms as term}
					<Badge
						variant="outline"
						class="border-fuchsia-200 bg-white/80 text-fuchsia-700"
						data-print-role="definition-related-term-pill"
					>
						{term}
					</Badge>
				{/each}
			</div>
		{/if}
	</div>
</Card>

<style>
	@media print {
		:global([data-lectio-block='definition']) {
			border: 1.5px solid #ccc;
			border-left: 4px solid #333;
			padding: 0.75rem 1rem;
			page-break-inside: avoid;
		}

		:global([data-lectio-block='definition'] h3) {
			font-weight: 700;
			margin-bottom: 0.25rem;
		}

		:global([data-lectio-block='definition'] [data-print-role='definition-toggle']) {
			display: none !important;
		}
	}
</style>

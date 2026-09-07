<script lang="ts">
	import type { DefinitionFamilyContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import {
		Accordion,
		AccordionItem,
		AccordionTrigger,
		AccordionContent
	} from '$lib/components/ui/accordion';
	import DefinitionCard from './DefinitionCard.svelte';
	import { usePrintMode } from '$lib/utils/printContext';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let { content }: { content: DefinitionFamilyContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
	const isHorizontal = $derived(content.definitions.length <= 4);
</script>

<div class="definition-family {isHorizontal ? 'definition-family--horizontal' : ''}">
<Card
	class="overflow-hidden border-fuchsia-200 bg-[linear-gradient(180deg,rgba(253,244,255,0.9),rgba(255,255,255,0.92))] shadow-[0_20px_48px_rgba(192,38,211,0.1)]"
>
	<div class="rh-gap-component rh-pad-card">
		<div class="space-y-2">
			<p class="eyebrow text-fuchsia-600">Definition family</p>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.family_title}</h3>
			{#if content.family_intro}
				<p class="text-sm leading-6 text-muted-foreground">{content.family_intro}</p>
			{/if}
		</div>

		{#if isHorizontal}
			<div class="definition-family__grid">
				{#each content.definitions as definition}
					<div class="definition-family__card">
						<p class="definition-family__term">{definition.term}</p>
						<p class="definition-family__definition">
							{@html renderInlineMarkdown(definition.plain)}
						</p>
						{#if definition.symbol}
							<p class="definition-family__symbol">{definition.symbol}</p>
						{/if}
					</div>
				{/each}
			</div>
		{:else if printMode}
			<div
				class="definition-family-print-list rh-gap-component-tight space-y-3"
				data-print-container="itemized"
			>
				{#each content.definitions as definition}
					<div
						class="definition-family-print-item overflow-hidden rh-radius-card border border-fuchsia-200/70 bg-white/84 shadow-[0_14px_36px_rgba(15,23,42,0.08)]"
						data-print-item="definition"
					>
						<div class="rh-radius-card bg-[linear-gradient(180deg,rgba(253,244,255,0.72),rgba(255,255,255,0.95))] p-1">
							<DefinitionCard content={definition} />
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<Accordion type="single" class="rh-gap-component-tight">
				{#each content.definitions as definition, index}
					<AccordionItem
						value={`definition-${index}`}
						class="overflow-hidden rh-radius-card border border-fuchsia-200/70 bg-white/84 shadow-[0_14px_36px_rgba(15,23,42,0.08)]"
					>
						<AccordionTrigger class="px-5">
							<div class="flex flex-col items-start gap-1 text-left">
								<span class="font-semibold text-foreground/92">{definition.term}</span>
								{#if definition.symbol}
									<span class="text-sm text-fuchsia-700/78">{definition.symbol}</span>
								{/if}
							</div>
						</AccordionTrigger>
						<AccordionContent>
							<div class="rh-radius-card bg-[linear-gradient(180deg,rgba(253,244,255,0.72),rgba(255,255,255,0.95))] p-1">
								<DefinitionCard content={definition} />
							</div>
						</AccordionContent>
					</AccordionItem>
				{/each}
			</Accordion>
		{/if}
	</div>
</Card>
</div>

<style>
	.definition-family--horizontal .definition-family__grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 1rem;
	}

	.definition-family--horizontal .definition-family__card {
		border-top: 3px solid var(--accent, hsl(var(--primary)));
		padding: 0.75rem 0.5rem;
	}

	.definition-family--horizontal .definition-family__term {
		font-weight: 700;
		font-size: 0.9em;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		margin-bottom: 0.35rem;
	}

	.definition-family--horizontal .definition-family__definition {
		font-size: 0.85em;
		line-height: 1.45;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
	}

	.definition-family--horizontal .definition-family__symbol {
		margin-top: 0.25rem;
		font-size: 0.8em;
		color: hsl(var(--primary) / 0.75);
	}

	@media print {
		.definition-family--horizontal .definition-family__grid {
			page-break-inside: avoid;
			gap: 0.75rem;
		}

		.definition-family--horizontal .definition-family__card {
			border-top: 2px solid #333;
		}

		.definition-family-print-list {
			display: grid;
			gap: var(--rh-gap-component-tight, 0.75rem);
		}
	}
</style>

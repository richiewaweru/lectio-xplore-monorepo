<script lang="ts">
	import type { PitfallContent } from '$lib/schema/types';
	import { Alert, AlertTitle, AlertDescription } from '$lib/components/ui/alert';
	import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '$lib/components/ui/collapsible';
	import { TriangleAlert } from 'lucide-svelte';
	import { renderInlineMarkdown } from '$lib/utils/markdown';
	import { usePrintMode } from '$lib/utils/printContext';

	let { content }: { content: PitfallContent } = $props();

	const displayExamples = $derived(content.examples ?? (content.example ? [content.example] : []));
	const isMinor = $derived(content.severity === 'minor');
	const headerLabel = $derived(content.label ?? 'Common Misconception');

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
</script>

<div class="pitfall-alert-root" data-lectio-block="pitfall" data-print-container="atomic">
	{#if printMode}
		<div class="pitfall-alert">
			<div class="pitfall-alert__header">{headerLabel}</div>
			<p class="pitfall-alert__misconception">
				{@html renderInlineMarkdown(content.misconception)}
			</p>
			<p class="pitfall-alert__correction">
				{@html renderInlineMarkdown(content.correction)}
			</p>
			{#if content.why}
				<p class="pitfall-alert__why">
					Why students think this: {@html renderInlineMarkdown(content.why)}
				</p>
			{/if}
			{#if displayExamples.length > 0}
				<div class="pitfall-alert__examples">
					{#each displayExamples as example}
						<div class="pitfall-alert__example">
							{@html renderInlineMarkdown(example)}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<Alert class={isMinor ? 'border-amber-200 bg-amber-50/60' : 'border-orange-200 bg-orange-50/80'}>
			<TriangleAlert class="h-4 w-4 {isMinor ? 'text-amber-500' : 'text-orange-600'}" />
			<AlertTitle class="{isMinor ? 'text-amber-700' : 'text-orange-700'} text-sm font-semibold">
				{headerLabel} — {@html renderInlineMarkdown(content.misconception)}
			</AlertTitle>

			{#if content.why}
				<p class="mt-1 text-xs italic text-orange-600/80">
					Why students think this: {@html renderInlineMarkdown(content.why)}
				</p>
			{/if}

			<AlertDescription class="mt-1 text-sm leading-relaxed">
				{@html renderInlineMarkdown(content.correction)}
			</AlertDescription>

			{#if displayExamples.length > 0}
				<Collapsible class="mt-2">
					<CollapsibleTrigger
						class="inline-flex h-6 items-center justify-center rounded-xl px-2 text-xs font-medium text-orange-600 transition-colors hover:bg-accent hover:text-orange-700"
						data-print-role="pitfall-nav-link"
					>
						{displayExamples.length === 1 ? 'See example' : `See examples (${displayExamples.length})`} ->
					</CollapsibleTrigger>
					<CollapsibleContent>
						<div class="mt-2 space-y-2">
							{#each displayExamples as example}
								<div class="rounded-xl bg-white/70 p-2 text-xs italic text-muted-foreground">
									{@html renderInlineMarkdown(example)}
								</div>
							{/each}
						</div>
					</CollapsibleContent>
				</Collapsible>
			{/if}
		</Alert>
	{/if}
</div>

<style>
	@media print {
		.pitfall-alert-root {
			page-break-inside: avoid;
			margin: 1rem 0;
		}

		.pitfall-alert {
			border: 2px solid #b91c1c;
			border-radius: 2px;
			padding: 1rem 1.25rem;
			page-break-inside: avoid;
		}

		.pitfall-alert__header {
			display: flex;
			align-items: center;
			gap: 0.4rem;
			font-weight: 700;
			font-size: 0.85em;
			letter-spacing: 0.04em;
			text-transform: uppercase;
			color: #b91c1c;
			margin-bottom: 0.5rem;
		}

		.pitfall-alert__header::before {
			content: '⚠';
			font-size: 1.1em;
		}

		.pitfall-alert__misconception {
			font-weight: 600;
			margin-bottom: 0.35rem;
		}

		.pitfall-alert__correction {
			font-size: 0.95em;
			line-height: 1.5;
		}

		.pitfall-alert__why {
			margin-top: 0.35rem;
			font-size: 0.85em;
			font-style: italic;
		}

		.pitfall-alert__examples {
			margin-top: 0.5rem;
		}

		.pitfall-alert__example {
			font-size: 0.85em;
			font-style: italic;
			margin-top: 0.25rem;
		}
	}
</style>

<script lang="ts">
	import type { WhatNextContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { renderInlineMarkdown } from '$lib/utils/markdown';
	import { usePrintMode } from '$lib/utils/printContext';

	let { content }: { content: WhatNextContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
</script>

{#if printMode}
	<div class="what-next-bridge" data-lectio-block="what-next" data-print-container="prose">
		<div>
			<p class="what-next-bridge__label">Next lesson</p>
			<p class="what-next-bridge__topic">{content.next}</p>
			{#if content.body}
				<p class="what-next-bridge__body">{@html renderInlineMarkdown(content.body)}</p>
			{/if}
		</div>
		<span class="what-next-bridge__arrow" aria-hidden="true">→</span>
	</div>
{:else}
	<Card class="border-l-4 border-l-amber-400 bg-amber-50/65 rh-pad-card" data-lectio-block="what-next" data-print-container="prose">
		<div class="rh-gap-component-tight">
			<p class="eyebrow text-amber-600" data-print-role="what-next-label">What next</p>
			<p class="text-sm leading-7 text-foreground/80">{@html renderInlineMarkdown(content.body)}</p>
			{#if content.prerequisites?.length}
				<p class="text-xs text-muted-foreground">
					<span class="font-semibold">Prerequisites:</span>
					{content.prerequisites.join(' | ')}
				</p>
			{/if}
			<p class="text-sm font-semibold font-serif text-amber-700" data-print-role="what-next-link">
				{content.next} ->
			</p>
		</div>
	</Card>
{/if}

<style>
	@media print {
		.what-next-bridge {
			border: 1.5px solid #ccc;
			border-radius: 2px;
			padding: 1rem 1.25rem;
			display: flex;
			justify-content: space-between;
			align-items: center;
			page-break-inside: avoid;
			margin-top: 2rem;
		}

		.what-next-bridge__label {
			font-size: 0.75em;
			font-weight: 600;
			letter-spacing: 0.06em;
			text-transform: uppercase;
			color: #999;
			margin-bottom: 0.15rem;
		}

		.what-next-bridge__topic {
			font-size: 1.1em;
			font-weight: 600;
		}

		.what-next-bridge__body {
			margin-top: 0.35rem;
			font-size: 0.85em;
		}

		.what-next-bridge__arrow {
			font-size: 1.5em;
			color: #333;
		}
	}
</style>

<script lang="ts">
	import type { ExplanationContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { renderBlockMarkdown } from '$lib/utils/markdown';
	import { usePrintMode } from '$lib/utils/printContext';
	import { BookOpen, Lightbulb, Info, TriangleAlert, GraduationCap } from 'lucide-svelte';

	const calloutConfig = {
		remember: {
			label: 'Remember',
			className: 'border-blue-200 bg-blue-50/75 text-blue-800',
			icon: BookOpen
		},
		insight: {
			label: 'Key insight',
			className: 'border-violet-200 bg-violet-50/75 text-violet-800',
			icon: Lightbulb
		},
		sidenote: {
			label: 'Side note',
			className: 'border-gray-200 bg-gray-50/75 text-gray-700',
			icon: Info
		},
		warning: {
			label: 'Warning',
			className: 'border-amber-200 bg-amber-50/75 text-amber-800',
			icon: TriangleAlert
		},
		'exam-tip': {
			label: 'Exam tip',
			className: 'border-emerald-200 bg-emerald-50/75 text-emerald-800',
			icon: GraduationCap
		}
	};

	let { content }: { content: ExplanationContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
	const wordCount = $derived(content.body.split(/\s+/).filter(Boolean).length);
	const isLong = $derived(wordCount > 200);
	const firstCallout = $derived(content.callouts?.[0]);

	function renderBody(body: string, phrases: string[]): string {
		let result = renderBlockMarkdown(body);
		for (const phrase of phrases ?? []) {
			const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
			result = result.replace(
				new RegExp(escaped, 'gi'),
				(match) => `<mark class="lectio-emphasis">${match}</mark>`
			);
		}
		return result;
	}
</script>

<div
	class="explanation {isLong ? 'explanation--long' : ''}"
	data-lectio-block="explanation"
	data-print-container="prose"
>
<Card class="border-primary/10 bg-white/88 rh-pad-card">
	<div class="rh-gap-component">
		<div class="space-y-2">
			<p class="eyebrow text-blue-600">Explanation</p>
			{#if printMode && firstCallout}
				{@const cfg = calloutConfig[firstCallout.type]}
				<aside class="explanation__aside">
					<div class="explanation__aside-label">{cfg.label}</div>
					{firstCallout.text}
				</aside>
			{/if}
			<div class="explanation__body text-base leading-7 text-foreground/84 prose prose-sm max-w-none">
				{@html renderBody(content.body, content.emphasis ?? [])}
			</div>
		</div>

		{#if content.callouts?.length}
			<div class="rh-gap-component-tight explanation__callouts">
				{#each content.callouts as callout, index}
					{#if !printMode || index > 0}
						{@const cfg = calloutConfig[callout.type]}
						<div
							class="flex rh-gap-cluster rounded-xl border p-3 text-sm leading-6 {cfg.className}"
							data-print-role="explanation-callout"
							data-callout-type={callout.type}
						>
							<cfg.icon class="mt-0.5 h-4 w-4 shrink-0" data-print-role="callout-icon" />
							<div>
								<span class="font-semibold">{cfg.label}:</span>
								{callout.text}
							</div>
						</div>
					{/if}
				{/each}
			</div>
		{/if}
	</div>
</Card>
</div>

<style>
	@media print {
		.explanation--long .explanation__body {
			column-count: 2;
			column-gap: 1.5rem;
			orphans: 3;
			widows: 3;
		}

		.explanation__aside {
			float: right;
			width: 35%;
			max-width: 200px;
			margin: 0 0 1rem 1rem;
			padding: 0.75rem;
			border: 1.5px solid var(--rh-print-border, #ccc);
			border-left: 3px solid var(--rh-print-accent, #1e3a5f);
			font-size: 0.85em;
			font-style: italic;
			color: var(--rh-print-text-muted, #374151);
		}

		.explanation__aside-label {
			font-style: normal;
			font-weight: 600;
			font-size: 0.75em;
			letter-spacing: 0.05em;
			text-transform: uppercase;
			margin-bottom: 0.25rem;
			color: var(--rh-print-accent, #1e3a5f);
		}
	}
</style>

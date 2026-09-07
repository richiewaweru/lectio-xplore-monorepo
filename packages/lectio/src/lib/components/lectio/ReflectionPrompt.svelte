<script lang="ts">
	import type { ReflectionContent } from '$lib/schema/types';
	import { Card } from '$lib/components/ui/card';
	import { Brain } from 'lucide-svelte';
	import { usePrintMode } from '$lib/utils/printContext';
	import RuledLines from '$lib/print/RuledLines.svelte';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let { content }: { content: ReflectionContent } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	const typeLabels: Record<string, string> = {
		open: 'Reflect',
		'pair-share': 'Pair and share',
		'sentence-stem': 'Complete the thought',
		timed: 'Timed reflection',
		connect: 'Make a connection',
		predict: 'Predict',
		transfer: 'Transfer'
	};
</script>

{#if printMode}
	<div class="reflection-print" data-print-container="atomic">
		<p class="reflection-print-prompt">{@html renderInlineMarkdown(content.prompt)}</p>
		{#if content.type === 'sentence-stem' && content.sentence_stem}
			<p class="reflection-print-stem">{content.sentence_stem} ________________</p>
		{/if}
		<RuledLines lines={content.space && content.space > 0 ? content.space : 4} />
	</div>
{:else}
<Card class="border-l-4 border-l-indigo-400 bg-indigo-50/50 rh-pad-card">
	<div class="flex rh-gap-cluster">
		<Brain class="mt-0.5 h-5 w-5 shrink-0 text-indigo-500" />
		<div class="flex-1 rh-gap-component-tight">
			<div class="space-y-2">
				<p class="eyebrow text-indigo-600">{typeLabels[content.type] ?? 'Reflect'}</p>
				<p class="text-sm leading-7 text-foreground">{@html renderInlineMarkdown(content.prompt)}</p>
			</div>

			{#if content.type === 'sentence-stem' && content.sentence_stem}
				<p class="rounded-xl bg-white/60 p-3 text-sm italic text-indigo-600/80">
					{content.sentence_stem}
				</p>
			{/if}

			{#if content.type === 'timed' && content.time_minutes}
				<p class="text-xs text-muted-foreground">
					Take {content.time_minutes} minute{content.time_minutes > 1 ? 's' : ''} to think about
					this.
				</p>
			{/if}

			{#if content.type === 'pair-share' && content.pair_instruction}
				<p class="text-xs font-medium italic text-indigo-600">{content.pair_instruction}</p>
			{/if}

			{#if content.space && content.space > 0}
				<div class="print-only mt-3 rh-gap-component-tight">
					{#each Array.from({ length: content.space }) as _}
						<div class="h-8 border-b border-indigo-200"></div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</Card>
{/if}

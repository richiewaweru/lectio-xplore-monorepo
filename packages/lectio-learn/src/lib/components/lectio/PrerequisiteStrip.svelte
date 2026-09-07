<script lang="ts">
	import type { PrerequisiteContent } from '$lib/schema/types';
	import { Popover, PopoverTrigger, PopoverContent } from '$lib/components/ui/popover';
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let { content }: { content: PrerequisiteContent } = $props();
</script>

<div class="rounded-[1.5rem] border border-teal-200 bg-teal-50/55 p-5" data-print-container="atomic">
	<div class="mb-3 space-y-2">
		<p class="eyebrow text-teal-600">{content.label ?? 'Before we begin'}</p>
		<p class="text-sm leading-6 text-muted-foreground">
			These ideas should already feel familiar before this section moves forward.
		</p>
	</div>

	<div class="flex flex-wrap gap-2">
		{#each content.items as item}
			{#if item.refresher}
				<Popover>
					<PopoverTrigger>
						<button
							class="inline-flex cursor-pointer items-center gap-1 rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-medium text-teal-700 transition-all duration-200 hover:border-teal-300 hover:bg-teal-100"
							aria-label={`Show refresher for ${item.concept}`}
						>
							{item.concept}
							<span class="text-teal-400">?</span>
						</button>
					</PopoverTrigger>
					<PopoverContent class="glass-panel w-64 rounded-[1.1rem] p-3 text-xs leading-relaxed text-muted-foreground">
						<div class="relative z-10">
							<div class="mb-1 font-semibold text-foreground">{item.concept}</div>
							{@html renderInlineMarkdown(item.refresher)}
						</div>
					</PopoverContent>
				</Popover>
			{:else}
				<span
					class="inline-flex items-center rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-medium text-teal-700"
				>
					{item.concept}
				</span>
			{/if}
		{/each}
	</div>
</div>

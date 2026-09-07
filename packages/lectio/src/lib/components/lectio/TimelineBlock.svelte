<script lang="ts">
	import type { TimelineContent } from '$lib/schema/types';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Card } from '$lib/components/ui/card';
	import { usePrintMode } from '$lib/utils/printContext';
	import VerticalList from '$lib/print/VerticalList.svelte';

	let {
		content,
		mode = 'timeline-scrubber'
	}: { content: TimelineContent; mode?: 'static' | 'timeline-scrubber' } = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	let activeIndex = $state(0);

	const activeEvent = $derived(content.events[activeIndex] ?? content.events[0]);
</script>

{#if printMode}
	<div class="timeline-print" data-print-container="itemized">
		<VerticalList events={content.events} title={content.title} />
		{#if content.closing_takeaway}
			<div class="timeline-print-takeaway">
				<strong>Key Takeaway:</strong> {content.closing_takeaway}
			</div>
		{/if}
	</div>
{:else}
<Card class="border-rose-200 bg-rose-50/45 rh-pad-card">
	<div class="space-y-5">
		<div class="space-y-2">
			<p class="eyebrow text-rose-700">Timeline</p>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.title}</h3>
			{#if content.intro}
				<p class="text-sm leading-6 text-muted-foreground">{content.intro}</p>
			{/if}
		</div>

		{#if mode === 'timeline-scrubber'}
			<div class="flex gap-2 overflow-x-auto pb-2">
				{#each content.events as event, index}
					<Button
						variant={index === activeIndex ? 'default' : 'outline'}
						class={`shrink-0 rounded-full ${
							index === activeIndex
								? 'bg-rose-600 text-white hover:bg-rose-700'
								: 'border-rose-200 text-rose-700 hover:bg-rose-50'
						}`}
						onclick={() => (activeIndex = index)}
					>
						{event.year}
					</Button>
				{/each}
			</div>
		{/if}

		{#if mode === 'timeline-scrubber'}
			{#if activeEvent}
				<div class="rh-radius-card border border-rose-300 bg-white/85 p-4 shadow-[0_12px_30px_rgba(244,63,94,0.12)]">
					<div class="flex flex-wrap items-center gap-2">
						<Badge variant="outline" class="border-rose-200 text-rose-700">
							{activeEvent.year}
						</Badge>
						{#if activeEvent.era}
							<Badge variant="outline" class="border-rose-200 text-rose-700">
								{activeEvent.era}
							</Badge>
						{/if}
					</div>
					<h4 class="mt-3 text-2xl font-semibold font-serif text-primary">{activeEvent.title}</h4>
					<p class="mt-2 text-base leading-7 text-foreground/84">{activeEvent.summary}</p>
					{#if activeEvent.impact}
						<p class="mt-3 text-sm leading-6 text-muted-foreground">
							<span class="font-semibold uppercase tracking-[0.16em] text-rose-700">
								Why it matters
							</span>
							{activeEvent.impact}
						</p>
					{/if}
					{#if activeEvent.tags?.length}
						<div class="mt-3 flex flex-wrap gap-2">
							{#each activeEvent.tags as tag}
								<Badge class="bg-rose-100 text-rose-800 hover:bg-rose-100">{tag}</Badge>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<div class="flex flex-wrap gap-2">
				<Button
					variant="outline"
					disabled={activeIndex === 0}
					onclick={() => (activeIndex = Math.max(activeIndex - 1, 0))}
				>
					Previous
				</Button>
				<Button
					variant="outline"
					disabled={activeIndex >= content.events.length - 1}
					onclick={() => (activeIndex = Math.min(activeIndex + 1, content.events.length - 1))}
				>
					Next
				</Button>
			</div>
		{:else}
			<div class="rh-gap-component">
				{#each content.events as event}
					<div class="rh-radius-card border border-rose-100 bg-white/85 p-4">
						<div class="flex flex-wrap items-center gap-2">
							<Badge variant="outline" class="border-rose-200 text-rose-700">
								{event.year}
							</Badge>
							{#if event.era}
								<Badge variant="outline" class="border-rose-200 text-rose-700">
									{event.era}
								</Badge>
							{/if}
						</div>
						<h4 class="mt-3 text-2xl font-semibold font-serif text-primary">{event.title}</h4>
						<p class="mt-2 text-base leading-7 text-foreground/84">{event.summary}</p>
						{#if event.impact}
							<p class="mt-3 text-sm leading-6 text-muted-foreground">
								<span class="font-semibold uppercase tracking-[0.16em] text-rose-700">
									Why it matters
								</span>
								{event.impact}
							</p>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		{#if content.closing_takeaway}
			<div class="rounded-[1.15rem] bg-rose-100/70 p-4 text-sm leading-6 text-rose-950">
				<span class="mr-2 font-semibold uppercase tracking-[0.18em] text-rose-700">
					Takeaway
				</span>
				{content.closing_takeaway}
			</div>
		{/if}
	</div>
</Card>
{/if}

<style>
	.timeline-print {
		margin: 1rem 0;
	}

	.timeline-print-takeaway {
		margin-top: 1.5rem;
		padding: var(--rh-pad-card);
		border-left: 3px solid #374151;
		font-size: 0.875rem;
	}
</style>

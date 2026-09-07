<script lang="ts">
	import type { DiagramSeriesContent } from '$lib/schema/types';
	import type { MediaReference } from '$lib/teacher/document';
	import { Card } from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { ChevronLeft, ChevronRight } from 'lucide-svelte';
	import { usePrintMode } from '$lib/utils/printContext';
	import { sanitizeSvg } from '$lib/utils/sanitize';

let {
	content,
	media = {}
}: {
	content: DiagramSeriesContent;
	media?: Record<string, MediaReference>;
} = $props();

const getPrintMode = usePrintMode();
const printMode = $derived(getPrintMode());

let current = $state(0);

const activeDiagram = $derived(content.diagrams[current] ?? content.diagrams[0]);

function hasSvg(diagram: DiagramSeriesContent['diagrams'][number] | undefined): boolean {
	return Boolean(diagram?.svg_content?.trim());
}

function imageUrl(diagram: DiagramSeriesContent['diagrams'][number] | undefined): string | undefined {
	const ref = diagram?.media_id ? media[diagram.media_id] : undefined;
	return ref?.type === 'image' && ref.url ? ref.url : diagram?.image_url;
}

function hasImage(diagram: DiagramSeriesContent['diagrams'][number] | undefined): boolean {
	return Boolean(imageUrl(diagram)?.trim());
}

$effect(() => {
	current = content.diagrams.length === 0 ? 0 : Math.min(current, content.diagrams.length - 1);
});

const progressPercent = $derived(
	!activeDiagram || content.diagrams.length <= 1
		? 100
		: ((current + 1) / content.diagrams.length) * 100
);
</script>

{#if printMode}
	<div class="diagram-series-print-root" data-print-container="itemized" data-print-has-media="true">
		<p class="diagram-series-print-title">{content.title}</p>
		<div class="diagram-series-print-grid" data-count={content.diagrams.length}>
			{#each content.diagrams as diagram, index}
				<figure class="diagram-series-print-item" data-print-item="series-frame">
					<figcaption class="diagram-series-print-label">
						{diagram.step_label}
					</figcaption>
					{#if hasImage(diagram)}
						<img
							src={imageUrl(diagram)}
							alt={diagram.caption}
							class="diagram-series-print-media"
						/>
					{:else if hasSvg(diagram)}
						<div class="diagram-series-print-svg">
							{@html sanitizeSvg(diagram.svg_content ?? '')}
						</div>
					{/if}
					<p class="diagram-series-print-caption">{diagram.caption}</p>
				</figure>
			{/each}
		</div>
	</div>
{:else}
<Card class="border-primary/10 bg-white/88 rh-pad-card">
	<div class="space-y-5">
		<div class="space-y-2">
			<p class="eyebrow">Series</p>
			<h3 class="text-2xl font-semibold font-serif text-primary">{content.title}</h3>
		</div>

		{#if activeDiagram}
			<div class="rh-gap-component-tight rounded-[1.2rem] border border-border/70 bg-white/78 p-4">
				<div class="flex items-center justify-between rh-gap-cluster text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
					<span>Step {current + 1} of {content.diagrams.length}</span>
					<span>{activeDiagram.step_label}</span>
				</div>

				<div
					class="grid gap-2"
					style="grid-template-columns: repeat({content.diagrams.length}, minmax(0, 1fr));"
				>
					{#each content.diagrams as diagram, index}
						<button
							type="button"
							onclick={() => (current = index)}
							class="group rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							aria-current={index === current ? 'step' : undefined}
							aria-label={`Go to ${diagram.step_label}`}
						>
							<span
								class="block h-2 rounded-full transition-all {index <= current
									? 'bg-primary'
									: 'bg-secondary group-hover:bg-secondary/80'}"
							></span>
						</button>
					{/each}
				</div>

				<div class="h-1.5 overflow-hidden rounded-full bg-secondary">
					<div
						class="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all"
						style="width: {progressPercent}%"
					></div>
				</div>

				<div class="flex flex-wrap items-center justify-between rh-gap-cluster">
					<Button
						size="sm"
						variant="outline"
						onclick={() => (current = Math.max(0, current - 1))}
						disabled={current === 0}
					>
						<ChevronLeft class="h-4 w-4" />
						Previous
					</Button>

					<div class="flex flex-wrap gap-2">
						{#each content.diagrams as diagram, index}
							<Button
								size="sm"
								variant={index === current ? 'default' : 'outline'}
								class="text-xs"
								onclick={() => (current = index)}
							>
								{diagram.step_label}
							</Button>
						{/each}
					</div>

					<Button
						size="sm"
						variant="outline"
						onclick={() => (current = Math.min(content.diagrams.length - 1, current + 1))}
						disabled={current === content.diagrams.length - 1}
					>
						Next
						<ChevronRight class="h-4 w-4" />
					</Button>
				</div>
			</div>

			{#if hasImage(activeDiagram)}
				<img
					src={imageUrl(activeDiagram)}
					alt={activeDiagram.caption}
					class="w-full overflow-hidden rh-radius-card border border-border/70 bg-white object-contain"
				/>
			{:else if hasSvg(activeDiagram)}
				<div class="overflow-x-auto rh-radius-card border border-border/70 bg-white [&_svg]:h-auto [&_svg]:min-w-0 [&_svg]:w-full">
					{@html sanitizeSvg(activeDiagram.svg_content ?? '')}
				</div>
			{/if}

			<p class="text-sm leading-6 text-muted-foreground">{activeDiagram.caption}</p>
		{/if}
	</div>
</Card>
{/if}

<style>
	.diagram-series-print-root {
		margin: 0.75rem 0;
	}

	.diagram-series-print-title {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}

	.diagram-series-print-grid {
		display: grid;
		gap: 0.75rem;
	}

	.diagram-series-print-grid[data-count="1"] {
		grid-template-columns: 1fr;
	}

	.diagram-series-print-grid[data-count="2"] {
		grid-template-columns: 1fr 1fr;
	}

	.diagram-series-print-grid[data-count="3"] {
		grid-template-columns: 1fr 1fr 1fr;
	}

	.diagram-series-print-grid[data-count="5"] {
		grid-template-columns: 1fr 1fr 1fr;
	}

	.diagram-series-print-grid[data-count="4"] {
		grid-template-columns: 1fr 1fr;
	}

	.diagram-series-print-item {
		page-break-inside: avoid;
		margin: 0;
	}

	.diagram-series-print-label {
		font-size: 0.8rem;
		font-weight: 600;
		margin-bottom: 0.4rem;
		margin-top: 0;
	}

	.diagram-series-print-media {
		display: block;
		width: 100%;
		height: auto;
		object-fit: contain;
		border-radius: 0.5rem;
		border: 1px solid rgba(148, 163, 184, 0.4);
		background: white;
	}

	.diagram-series-print-svg {
		overflow: visible;
		border-radius: 0.5rem;
		border: 1px solid rgba(148, 163, 184, 0.4);
		background: white;
		padding: 0.5rem;
	}

	.diagram-series-print-svg :global(svg) {
		display: block;
		width: 100%;
		height: auto;
	}

	.diagram-series-print-caption {
		font-size: 0.875rem;
		line-height: 1.5;
		color: hsl(var(--muted-foreground));
		margin: 0.45rem 0 0;
	}
</style>

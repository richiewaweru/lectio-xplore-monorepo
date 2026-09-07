<script lang="ts">
	import type { SimulationContent } from '$lib/schema/types';
	import { Badge } from '$lib/components/ui/badge';
	import { Card } from '$lib/components/ui/card';
	import { X, ZoomIn, ZoomOut } from 'lucide-svelte';
	import { usePrintMode } from '$lib/utils/printContext';
	import { sanitizeSvg } from '$lib/utils/sanitize';

	let { content }: { content: SimulationContent } = $props();

	let expanded = $state(false);

	const hasLiveContent = $derived(!!content.html_content);
	const typeLabel = $derived(content.spec.type.replace(/_/g, ' '));
	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	function toggleExpanded() {
		expanded = !expanded;
	}

	function closeExpanded() {
		expanded = false;
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			closeExpanded();
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && expanded) {
			closeExpanded();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if printMode}
	<!-- Print fallback -->
	{#if content.spec.print_translation === 'hide'}
		<div class="simulation-print-note" data-print-container="atomic">
			<p><strong>Interactive simulation:</strong> {content.spec.goal}</p>
			<p class="simulation-print-note-sub">Available in digital version</p>
		</div>
	{:else if (content.spec.print_translation === 'static_diagram' || content.spec.print_translation === 'static_midstate') && content.fallback_diagram}
		<div class="simulation-print-fallback" data-print-container="atomic" data-print-has-media="true">
			{#if content.spec.print_translation === 'static_midstate'}
				<p class="simulation-type-label">{typeLabel}</p>
			{/if}
			<div
				role="img"
				aria-label={content.fallback_diagram.alt_text}
				class="simulation-print-diagram"
			>
				{@html sanitizeSvg(content.fallback_diagram.svg_content)}
			</div>
			{#if content.fallback_diagram.caption}
				<p class="simulation-print-caption">{content.fallback_diagram.caption}</p>
			{/if}
		</div>
	{:else if content.explanation?.trim()}
		<div class="simulation-print-note" data-print-container="atomic">
			<p><strong>{typeLabel}.</strong> {content.explanation}</p>
			<p class="simulation-print-note-sub">Interactive simulation is available in the digital version.</p>
		</div>
	{:else}
		<div class="simulation-print-note" data-print-container="atomic">
			<p><strong>{typeLabel}:</strong> {content.spec.goal}</p>
			<p class="simulation-print-note-sub">See digital version for interactive experience</p>
		</div>
	{/if}
{:else}
<Card class="border-primary/10 bg-white/88 rh-pad-card">
	<div class="rh-gap-component">
		<div class="rh-gap-component-tight">
			<div class="flex flex-wrap items-center rh-gap-cluster">
				<p class="eyebrow">Simulation</p>
				<Badge variant="outline">{typeLabel}</Badge>
				{#if !hasLiveContent}
					<Badge variant="secondary">Scaffold</Badge>
				{/if}
			</div>
			<h3 class="text-2xl font-semibold font-serif text-primary">Manipulate and discover</h3>
		</div>

		{#if content.explanation}
			<p class="text-base leading-7 text-foreground/84">{content.explanation}</p>
		{/if}

		{#if hasLiveContent}
			<!-- Live simulation in sandboxed iframe -->
			<div class="relative">
				<div class="absolute right-2 top-2 z-10">
					<button
						type="button"
						class="flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1.5 text-xs font-medium text-primary shadow-sm border border-border/50 hover:bg-white transition-colors"
						onclick={toggleExpanded}
						aria-label="Expand simulation"
					>
						<ZoomIn size={14} />
						Expand
					</button>
				</div>
				<iframe
					srcdoc={content.html_content}
					sandbox="allow-scripts"
					title={content.spec.goal}
					class="w-full rh-radius-card border border-border/60 bg-white"
					style="height: {content.spec.dimensions.height}px;"
				></iframe>
			</div>
		{:else if content.fallback_diagram}
			<!-- Fallback diagram when no live content -->
			<div class="rh-gap-component-tight rh-radius-card border border-border/70 bg-background/75 p-4">
				<p class="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
					Fallback diagram
				</p>
				<div
					role="img"
					aria-label={content.fallback_diagram.alt_text}
					class="overflow-hidden rounded-[1rem] border border-border/70 bg-white [&_svg]:h-auto [&_svg]:w-full"
				>
					{@html sanitizeSvg(content.fallback_diagram.svg_content)}
				</div>
				<p class="text-sm leading-6 text-muted-foreground">
					{content.fallback_diagram.caption}
				</p>
			</div>
		{:else}
			<!-- Scaffold placeholder -->
			<div
				class="flex items-center justify-center rh-radius-card border border-dashed border-border/80 bg-secondary/35 rh-pad-card text-center text-sm leading-6 text-muted-foreground"
				style="min-height: {content.spec.dimensions.height}px;"
			>
				Interactive experience will mount here when the interaction pipeline is connected.
			</div>
		{/if}

		<!-- Metadata panel -->
		<div class="grid rh-gap-cluster rh-radius-card bg-white/82 p-4 text-sm leading-6 text-foreground/82 md:grid-cols-2">
			<div>
				<p class="font-semibold text-primary">Type</p>
				<p>{typeLabel}</p>
			</div>
			<div>
				<p class="font-semibold text-primary">Goal</p>
				<p>{content.spec.goal}</p>
			</div>
			<div>
				<p class="font-semibold text-primary">Dimensions</p>
				<p>{content.spec.dimensions.width} &times; {content.spec.dimensions.height}px</p>
			</div>
			<div>
				<p class="font-semibold text-primary">Print fallback</p>
				<p>{content.spec.print_translation}</p>
			</div>
		</div>
	</div>
</Card>
{/if}

<!-- Expanded overlay -->
{#if expanded && hasLiveContent && !printMode}
	<div
		class="fixed inset-0 z-50 grid place-items-center rh-pad-card bg-black/40 backdrop-blur-sm"
		role="presentation"
		onclick={handleBackdropClick}
	>
		<div class="relative w-full max-w-5xl rounded-[1.5rem] bg-white shadow-2xl overflow-hidden">
			<div class="flex items-center justify-between border-b border-border/40 px-5 py-3">
				<div class="flex items-center rh-gap-cluster">
					<p class="text-sm font-semibold text-primary">Simulation</p>
					<Badge variant="outline">{typeLabel}</Badge>
				</div>
				<div class="flex items-center gap-2">
					<button
						type="button"
						class="flex items-center gap-1.5 rounded-full bg-secondary/50 px-3 py-1.5 text-xs font-medium text-foreground/70 hover:bg-secondary transition-colors"
						onclick={closeExpanded}
						aria-label="Collapse simulation"
					>
						<ZoomOut size={14} />
						Collapse
					</button>
					<button
						type="button"
						class="flex items-center justify-center rounded-full bg-secondary/50 p-1.5 text-foreground/60 hover:bg-secondary transition-colors"
						onclick={closeExpanded}
						aria-label="Close"
					>
						<X size={16} />
					</button>
				</div>
			</div>
			<iframe
				srcdoc={content.html_content}
				sandbox="allow-scripts"
				title={content.spec.goal}
				class="w-full"
				style="height: min(80vh, 640px);"
			></iframe>
		</div>
	</div>
{/if}

<style>
	.simulation-print-fallback {
		page-break-inside: avoid;
		margin: 1rem 0;
	}

	.simulation-print-diagram {
		max-width: 80%;
		margin: 0 auto;
	}

	.simulation-print-diagram :global(svg) {
		display: block;
		width: 100%;
		height: auto;
	}

	.simulation-print-caption {
		text-align: center;
		font-size: 0.875rem;
		font-style: italic;
		margin-top: 0.5rem;
	}

	.simulation-type-label {
		font-size: var(--rh-eyebrow-size);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.16em;
		color: #6b7280;
		margin-bottom: 0.75rem;
	}

	.simulation-print-note {
		padding: var(--rh-pad-card);
		border: 1px solid #d1d5db;
		margin: 1rem 0;
		page-break-inside: avoid;
	}

	.simulation-print-note-sub {
		font-size: 0.875rem;
		color: #6b7280;
		margin-top: 0.5rem;
	}
</style>

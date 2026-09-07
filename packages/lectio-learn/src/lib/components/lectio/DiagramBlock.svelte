<script lang="ts">
	import type { DiagramContent } from '$lib/schema/types';
	import type { MediaReference } from '$lib/teacher/document';
	import { Card } from '$lib/components/ui/card';
	import { Popover, PopoverTrigger, PopoverContent } from '$lib/components/ui/popover';
	import {
		Dialog,
		DialogPortal,
		DialogTrigger,
		DialogContent,
		DialogTitle,
		DialogOverlay
	} from '$lib/components/ui/dialog';
	import { ZoomIn } from 'lucide-svelte';
	import { sanitizeSvg } from '$lib/utils/sanitize';
	import { usePrintMode } from '$lib/utils/printContext';
	import { renderInlineMarkdown, renderBlockMarkdown } from '$lib/utils/markdown';

	let {
		content,
		media = {}
	}: {
		content: DiagramContent;
		media?: Record<string, MediaReference>;
	} = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	type DiagramCallout = NonNullable<DiagramContent['callouts']>[number];
	const mediaRef = $derived(content.media_id ? media[content.media_id] : undefined);
	const imageUrl = $derived(mediaRef?.type === 'image' && mediaRef.url ? mediaRef.url : content.image_url);
	const hasImage = $derived(!!imageUrl);
	const hasSvg = $derived(!!content.svg_content);
	const showCallouts = $derived(!!(content.callouts?.length) && (hasSvg || hasImage));
	const widthClass = $derived(
		(
			{
				full: 'w-full max-w-full',
				half: 'w-full max-w-[50%]',
				third: 'w-full max-w-[33.333333%]'
			} as const
		)[content.width ?? 'full']
	);
	const hasSideBySide = $derived(Boolean(content.description?.trim()));
	const figureLabel = $derived(
		content.figure_ref ?? (content.figure_number != null ? `Figure ${content.figure_number}` : null)
	);

	function getMarkerPosition(callout: DiagramCallout) {
		const horizontalOffset = callout.x >= 72 ? -20 : callout.x <= 28 ? 20 : 0;
		const verticalOffset = callout.y >= 72 ? -20 : callout.y <= 28 ? 20 : -18;

		return {
			left: `calc(${callout.x}% ${horizontalOffset >= 0 ? '+' : '-'} ${Math.abs(horizontalOffset)}px)`,
			top: `calc(${callout.y}% ${verticalOffset >= 0 ? '+' : '-'} ${Math.abs(verticalOffset)}px)`
		};
	}
</script>

<div class="diagram-block-root" data-lectio-block="diagram" data-print-container="atomic" data-print-has-media="true">
<Card class="border-primary/10 bg-white/88 rh-pad-card">
	<div class="rh-gap-component">
		<div class="flex flex-wrap items-center rh-gap-cluster">
			<p class="eyebrow">Diagram</p>
			{#if figureLabel && !hasSideBySide}
				<span class="rounded-full border border-border/70 bg-secondary px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-foreground/75">
					{figureLabel}
				</span>
			{/if}
		</div>

		{#if hasSideBySide}
			<figure class="figure-pair">
				{#if hasImage}
					<img
						class="figure-pair__image"
						src={imageUrl}
						alt={content.alt_text}
						loading={printMode ? 'eager' : 'lazy'}
					/>
				{:else if hasSvg}
					<div
						class="figure-pair__image overflow-hidden rh-radius-card border border-border/70 bg-white [&_svg]:h-full [&_svg]:w-full [&_svg]:object-contain"
						role="img"
						aria-label={content.alt_text}
					>
						{@html sanitizeSvg(content.svg_content)}
					</div>
				{/if}
				<figcaption class="figure-pair__text">
					{#if figureLabel}
						<span class="diagram__figure-ref">{figureLabel}</span>
					{/if}
					{#if content.caption}
						<span class="diagram__caption lectio-diagram-caption">
							{@html renderInlineMarkdown(content.caption)}
						</span>
					{/if}
					<div class="diagram__description lectio-rich">
						{@html renderBlockMarkdown(content.description ?? '')}
					</div>
				</figcaption>
			</figure>
		{:else if hasImage}
			<figure class="lectio-diagram-figure {widthClass} mx-auto">
				<div
					class="relative overflow-hidden rh-radius-card border border-border/70 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.72)]"
					role="img"
					aria-label={content.alt_text}
				>
					<img
						src={imageUrl}
						alt={content.alt_text}
						class="lectio-diagram-image"
						loading={printMode ? 'eager' : 'lazy'}
					/>
					{#if showCallouts}
						{#each content.callouts as callout, index}
							{@const markerPosition = getMarkerPosition(callout)}
							<div
								class="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/90 bg-primary shadow-[0_3px_10px_rgba(15,23,42,0.18)] diagram-block-dot"
								style="left: {callout.x}%; top: {callout.y}%;"
								data-print-role="diagram-dot"
							></div>
							<Popover>
								<PopoverTrigger>
									{#snippet child({ props })}
										<button
											{...props}
											type="button"
											class="absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/85 bg-primary text-[11px] font-semibold text-primary-foreground shadow-[0_10px_24px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-[55%] hover:scale-[1.04] diagram-block-callout-btn"
											style="left: {markerPosition.left}; top: {markerPosition.top};"
											aria-label={callout.label}
											data-print-role="diagram-callout-trigger"
											onpointerdown={(event) => event.stopPropagation()}
											onclick={(event) => event.stopPropagation()}
										>
											{index + 1}
										</button>
									{/snippet}
								</PopoverTrigger>
								<PopoverContent class="glass-panel w-64 rounded-[1.1rem] p-3 text-sm leading-6 text-foreground/82">
									<div class="relative z-10 space-y-2">
										<div class="flex items-start rh-gap-cluster">
											<span
												class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground"
											>
												{index + 1}
											</span>
											<div>
												<p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary/70">
													Diagram point
												</p>
												<p class="text-sm font-semibold text-foreground">{callout.label}</p>
											</div>
										</div>
										<p class="text-sm leading-6 text-foreground/80">
											{callout.explanation}
										</p>
									</div>
								</PopoverContent>
							</Popover>
						{/each}
					{/if}
				</div>
				{#if figureLabel}
					<span class="diagram__figure-ref">{figureLabel}</span>
				{/if}
				{#if content.caption}
					<figcaption class="lectio-diagram-caption">
						{@html renderInlineMarkdown(content.caption)}
					</figcaption>
				{/if}
			</figure>
			{#if printMode && showCallouts && content.callouts}
				<ul class="diagram-print-callouts mt-2 list-none space-y-2 text-sm leading-6 text-foreground/85">
					{#each content.callouts as callout, index}
						<li>
							<strong>{index + 1}. {callout.label}</strong>
							<span class="text-foreground/80"> — {@html renderInlineMarkdown(callout.explanation)}</span>
						</li>
					{/each}
				</ul>
			{/if}
			{#if showCallouts && !printMode}
				<p class="text-xs leading-5 text-muted-foreground">
					Tap a numbered point to see the labeled detail for that part of the diagram.
				</p>
			{/if}
		{:else}
		<Dialog>
			<DialogTrigger>
				<div class="group relative cursor-pointer" role="img" aria-label={content.alt_text}>
					<div class="overflow-x-auto rh-radius-card border border-border/70 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.72)] [&_svg]:h-auto [&_svg]:min-w-0 [&_svg]:w-full">
						{#if hasImage}
							<img
								src={imageUrl}
								alt=""
								class="h-auto w-full"
								loading={printMode ? 'eager' : 'lazy'}
							/>
						{:else if hasSvg}
							{@html sanitizeSvg(content.svg_content)}
						{:else}
							<div class="flex min-h-48 items-center justify-center rh-pad-card text-sm text-muted-foreground">
								No image provided.
							</div>
						{/if}
					</div>

					{#if showCallouts}
						{#each content.callouts as callout, index}
							{@const markerPosition = getMarkerPosition(callout)}
							<div
								class="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/90 bg-primary shadow-[0_3px_10px_rgba(15,23,42,0.18)] diagram-block-dot"
								style="left: {callout.x}%; top: {callout.y}%;"
								data-print-role="diagram-dot"
							></div>
							<Popover>
								<PopoverTrigger>
									{#snippet child({ props })}
										<button
											{...props}
											type="button"
											class="absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/85 bg-primary text-[11px] font-semibold text-primary-foreground shadow-[0_10px_24px_rgba(15,23,42,0.18)] transition-transform hover:-translate-y-[55%] hover:scale-[1.04] diagram-block-callout-btn"
											style="left: {markerPosition.left}; top: {markerPosition.top};"
											aria-label={callout.label}
											data-print-role="diagram-callout-trigger"
											onpointerdown={(event) => event.stopPropagation()}
											onclick={(event) => event.stopPropagation()}
										>
											{index + 1}
										</button>
									{/snippet}
								</PopoverTrigger>
								<PopoverContent class="glass-panel w-64 rounded-[1.1rem] p-3 text-sm leading-6 text-foreground/82">
									<div class="relative z-10 space-y-2">
										<div class="flex items-start rh-gap-cluster">
											<span
												class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground"
											>
												{index + 1}
											</span>
											<div>
												<p class="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary/70">
													Diagram point
												</p>
												<p class="text-sm font-semibold text-foreground">{callout.label}</p>
											</div>
										</div>
										<p class="text-sm leading-6 text-foreground/80">
											{callout.explanation}
										</p>
									</div>
								</PopoverContent>
							</Popover>
						{/each}
					{/if}

					<div
						class="absolute right-3 top-3 rounded-full bg-white/82 p-1.5 opacity-0 shadow-sm backdrop-blur-sm transition-opacity group-hover:opacity-100 diagram-block-zoom"
						data-print-role="diagram-zoom-trigger"
					>
						<ZoomIn class="h-4 w-4 text-muted-foreground" />
					</div>
				</div>
			</DialogTrigger>

			<DialogPortal>
				<DialogOverlay class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" />
				<DialogContent
					class="glass-panel fixed left-1/2 top-1/2 z-50 max-h-[min(88vh,56rem)] w-[min(92vw,64rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rh-radius-outer rh-pad-card animate-scale-in sm:p-7"
				>
					<div class="relative z-10 rh-gap-component">
						<DialogTitle class="text-base font-semibold text-primary">
							{content.zoom_label ?? 'Diagram detail'}
						</DialogTitle>
						<div
							class="overflow-x-auto rh-radius-card border border-border/70 bg-white p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.72)] [&_svg]:h-auto [&_svg]:min-w-0 [&_svg]:w-full"
							role="img"
							aria-label={content.alt_text}
						>
							{#if hasImage}
								<img
									src={imageUrl}
									alt=""
									class="h-auto w-full"
									loading={printMode ? 'eager' : 'lazy'}
								/>
							{:else if hasSvg}
								{@html sanitizeSvg(content.svg_content)}
							{:else}
								<div class="flex min-h-64 items-center justify-center rh-pad-card text-sm text-muted-foreground">
									No image provided.
								</div>
							{/if}
						</div>
						<p class="text-sm leading-6 text-muted-foreground">
							{@html renderInlineMarkdown(content.caption)}
						</p>
					</div>
				</DialogContent>
			</DialogPortal>
		</Dialog>

		{#if printMode && showCallouts && content.callouts}
			<ul class="diagram-print-callouts mt-2 list-none space-y-2 text-sm leading-6 text-foreground/85">
				{#each content.callouts as callout, index}
					<li>
						<strong>{index + 1}. {callout.label}</strong>
						<span class="text-foreground/80"> — {@html renderInlineMarkdown(callout.explanation)}</span>
					</li>
				{/each}
			</ul>
		{/if}
		{#if showCallouts && !printMode}
			<p class="text-xs leading-5 text-muted-foreground">
				Tap a numbered point to see the labeled detail for that part of the diagram.
			</p>
		{/if}

		{#if figureLabel}
			<span class="diagram__figure-ref">{figureLabel}</span>
		{/if}
		<p class="text-sm leading-6 text-muted-foreground">
			{@html renderInlineMarkdown(content.caption)}
		</p>
		{/if}
	</div>
</Card>
</div>

<style>
	@media print {
		.diagram-block-root {
			page-break-inside: avoid;
		}

		/* Hide interactive affordances */
		.diagram-block-zoom,
		.diagram-block-callout-btn,
		.diagram-block-dot {
			display: none !important;
		}

		.diagram-block-root :global(svg) {
			display: block;
			width: 80%;
			height: auto;
			margin: 0 auto;
		}

		.diagram-block-root .overflow-hidden,
		.diagram-block-root .overflow-x-auto {
			overflow: visible !important;
		}

		.lectio-diagram-image {
			width: 100%;
			height: auto;
			object-fit: contain;
		}

		.lectio-diagram-caption {
			text-align: center;
		}
	}

	.lectio-diagram-figure {
		margin: 0;
	}

	.lectio-diagram-image {
		display: block;
		width: 100%;
		height: auto;
		border-radius: 1.25rem;
		border: 1px solid hsl(var(--border) / 0.7);
		background: white;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
		object-fit: contain;
	}

	.lectio-diagram-caption {
		margin-top: 0.5rem;
		font-size: 0.875rem;
		line-height: 1.625;
		color: hsl(var(--muted-foreground));
	}

	.diagram__figure-ref {
		font-weight: 700;
		font-size: 0.8em;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted-foreground, hsl(var(--muted-foreground)));
		display: block;
		margin-bottom: 0.25rem;
	}

	.diagram__description {
		font-size: 0.9em;
		line-height: 1.55;
		color: var(--foreground, hsl(var(--foreground)));
	}

	@media print {
		.diagram__figure-ref {
			color: #333;
		}
	}
</style>

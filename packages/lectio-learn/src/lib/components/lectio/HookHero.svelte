<script lang="ts">
	import type { HookHeroContent } from '$lib/schema/types';
	import { Badge } from '$lib/components/ui/badge';
	import { BarChart3, CircleHelp, Quote, Sparkles } from 'lucide-svelte';
	import { sanitizeSvg } from '$lib/utils/sanitize';
	import { renderInlineMarkdown } from '$lib/utils/markdown';
	import { usePrintMode } from '$lib/utils/printContext';

	let { content }: { content: HookHeroContent } = $props();

	let hideImage = $state(false);

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());
	const hasVisual = $derived(Boolean(content.svg_content || (content.image && !hideImage)));

	function getHookType(): HookHeroContent['type'] {
		return content.type ?? 'prose';
	}

	function showVisual(): boolean {
		return hasVisual;
	}
</script>

{#if printMode}
	<section
		class="hook-hero hook-hero--print"
		class:hook-hero--with-image={hasVisual}
		data-lectio-block="hook"
		data-print-container="atomic"
		data-print-color-reset="true"
	>
		{#if hasVisual}
			<div class="hook-hero__image-wrap">
				{#if content.svg_content}
					<div class="hook-hero__image hook-hero__svg">
						{@html sanitizeSvg(content.svg_content)}
					</div>
				{:else if content.image}
					<img
						class="hook-hero__image"
						src={content.image.url}
						alt={content.image.alt}
						onerror={() => {
							hideImage = true;
						}}
					/>
				{/if}
			</div>
		{/if}
		<div class="hook-hero__text">
			<h2 class="hook-hero__headline">{content.headline}</h2>
			<p class="hook-hero__body">{@html renderInlineMarkdown(content.body)}</p>
			<p class="hook-hero__anchor">Anchor: {content.anchor}</p>
		</div>
	</section>
{:else}
<section
	class="relative overflow-hidden rh-radius-outer bg-primary px-6 py-8 text-primary-foreground shadow-warm "
	data-lectio-block="hook"
	data-print-container="prose"
	data-print-color-reset="true"
>
	<div
		class="absolute right-4 top-3 text-[7rem] font-black leading-none text-white/5 sm:text-[9rem]"
		data-print-role="hook-watermark"
	>
		?
	</div>

	<div
		class={showVisual()
			? 'relative z-10 grid items-center gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(250px,300px)]'
			: 'relative z-10 rh-gap-component'}
	>
		<div class="rh-gap-component">
			<Badge class="w-fit bg-white/12 text-primary-foreground hover:bg-white/12" data-print-role="hook-pill">
				Curiosity hook
			</Badge>

			<div
				class="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.25em] text-primary-foreground/70"
				data-print-role="hook-state-label"
			>
				<Sparkles class="h-4 w-4" />
				Felt need
			</div>

			<h2 class="max-w-2xl text-3xl leading-tight font-serif sm:text-4xl">
				{content.headline}
			</h2>

			{#if getHookType() === 'quote'}
				<div class="rh-gap-component-tight rh-radius-card border border-white/12 bg-white/8 p-4">
					<div class="flex items-center gap-2 text-sm uppercase tracking-[0.2em] text-primary-foreground/68">
						<Quote class="h-4 w-4" />
						Quoted hook
					</div>
					<blockquote class="max-w-2xl text-lg leading-8 text-primary-foreground/90">
						"{content.body}"
					</blockquote>
					{#if content.quote_attribution}
						<p class="text-sm text-primary-foreground/70">{content.quote_attribution}</p>
					{/if}
				</div>
			{:else}
				<p class="max-w-2xl text-base leading-7 text-primary-foreground/82">
					{@html renderInlineMarkdown(content.body)}
				</p>
			{/if}

			{#if getHookType() === 'question' && content.question_options?.length}
				<div class="rh-radius-card border border-white/12 bg-white/8 p-4" data-print-role="hook-tension">
					<div class="mb-3 flex items-center gap-2 text-sm uppercase tracking-[0.2em] text-primary-foreground/68">
						<CircleHelp class="h-4 w-4" />
						Hold the tension
					</div>
					<div class="flex flex-wrap gap-2">
						{#each content.question_options as option}
							<span
								class="rounded-full border border-white/12 bg-white/10 px-3 py-1 text-sm text-primary-foreground/85"
							>
								{option}
							</span>
						{/each}
					</div>
				</div>
			{/if}

			{#if getHookType() === 'data-point' && content.data_point}
				<div class="grid rh-gap-cluster rh-radius-card border border-white/12 bg-white/8 p-4 sm:grid-cols-[auto_1fr] sm:items-center">
					<div class="flex items-center rh-gap-cluster text-primary-foreground">
						<BarChart3 class="h-5 w-5" />
						<span class="text-3xl font-serif">{content.data_point.value}</span>
					</div>
					<div class="space-y-1">
						<p class="text-sm font-semibold uppercase tracking-[0.18em] text-primary-foreground/70">
							{content.data_point.label}
						</p>
						{#if content.data_point.source}
							<p class="text-sm text-primary-foreground/68">
								Source: {content.data_point.source}
							</p>
						{/if}
					</div>
				</div>
			{/if}

			<p
				class="max-w-xl rounded-full border border-white/12 bg-white/8 px-4 py-2 text-sm text-primary-foreground/78"
				data-print-role="hook-anchor"
			>
				Anchor: {content.anchor}
			</p>
		</div>

		{#if showVisual()}
			<div class="glass-panel rounded-[1.5rem] p-3 text-primary">
				<div class="relative z-10">
					<div class="mb-3 flex items-center justify-between rh-gap-cluster">
						<p class="text-xs font-semibold uppercase tracking-[0.2em] text-primary/65">
							Visual intuition
						</p>
						<span class="rounded-full bg-primary/8 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary/72">
							Attached visual
						</span>
					</div>

					<div class="overflow-hidden rh-radius-card bg-white/70 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
						{#if content.svg_content}
							<div
								class="aspect-[5/4] max-h-[260px] w-full [&_svg]:h-full [&_svg]:w-full [&_svg]:object-contain"
							>
								{@html sanitizeSvg(content.svg_content)}
							</div>
						{:else if content.image}
							<img
								src={content.image.url}
								alt={content.image.alt}
								class="aspect-[5/4] max-h-[260px] w-full object-contain"
								onerror={() => {
									hideImage = true;
								}}
							/>
						{/if}
					</div>

					<p class="mt-3 text-sm leading-6 text-primary/72">
						A quick visual anchor that previews the idea before the formal explanation begins.
					</p>
				</div>
			</div>
		{/if}
	</div>
</section>
{/if}

<style>
	.hook-hero--with-image .hook-hero__image {
		width: 100%;
		max-height: 240px;
		object-fit: cover;
		border-radius: 4px;
		margin-bottom: 1rem;
	}

	.hook-hero--with-image .hook-hero__svg {
		display: block;
		overflow: hidden;
	}

	.hook-hero--with-image .hook-hero__svg :global(svg) {
		width: 100%;
		max-height: 240px;
		object-fit: contain;
	}

	@media print {
		.hook-hero--print {
			padding: 0;
			border-left: 3px solid #333;
			padding-left: 0.75rem;
		}

		.hook-hero--with-image .hook-hero__image {
			max-height: 180px;
			border-radius: 0;
			border: 1px solid #ccc;
			object-fit: contain;
		}

		.hook-hero__headline {
			font-size: 1.25rem;
			font-weight: 700;
			margin-bottom: 0.5rem;
		}

		.hook-hero__body {
			font-size: 0.9rem;
			line-height: 1.5;
			margin-bottom: 0.35rem;
		}

		.hook-hero__anchor {
			font-size: 0.8em;
			font-style: italic;
		}
	}
</style>

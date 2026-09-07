<script lang="ts">
	import type { DiagramCompareContent } from '$lib/schema/types';
	import type { MediaReference } from '$lib/teacher/document';
	import { Card } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { usePrintMode } from '$lib/utils/printContext';
	import SideBySide from '$lib/print/SideBySide.svelte';
	import { sanitizeSvg } from '$lib/utils/sanitize';

	let {
		content,
		media = {}
	}: {
		content: DiagramCompareContent;
		media?: Record<string, MediaReference>;
	} = $props();

	const getPrintMode = usePrintMode();
	const printMode = $derived(getPrintMode());

	let position = $state(0);
	const stagePosition = $derived(Math.min(100, Math.max(0, position)));

	const beforeDetails = $derived(content.before_details ?? []);
	const afterDetails = $derived(content.after_details ?? []);
	const beforeMediaRef = $derived(content.before_media_id ? media[content.before_media_id] : undefined);
	const afterMediaRef = $derived(content.after_media_id ? media[content.after_media_id] : undefined);
	const beforeImageUrl = $derived(
		beforeMediaRef?.type === 'image' && beforeMediaRef.url ? beforeMediaRef.url : content.before_image_url
	);
	const afterImageUrl = $derived(
		afterMediaRef?.type === 'image' && afterMediaRef.url ? afterMediaRef.url : content.after_image_url
	);
	const hasImagePair = $derived(
		Boolean(beforeImageUrl?.trim()) && Boolean(afterImageUrl?.trim())
	);
	const hasSvgPair = $derived(Boolean(content.before_svg?.trim()) && Boolean(content.after_svg?.trim()));
	const visibleAfterCount = $derived(
		afterDetails.length === 0 || stagePosition === 0
			? 0
			: Math.min(
					afterDetails.length,
					Math.max(1, Math.ceil((stagePosition / 100) * afterDetails.length))
				)
	);
	const beforeActive = $derived(stagePosition < 50);
	const afterActive = $derived(stagePosition > 0);
	const seamVisible = $derived(stagePosition > 0 && stagePosition < 100);
</script>

{#if printMode}
	<div class="diagram-compare-print" data-print-container="atomic" data-print-has-media="true">
		<SideBySide leftLabel={content.before_label} rightLabel={content.after_label}>
			{#snippet left()}
				{#if hasImagePair}
					<div class="diagram-compare-print-image">
						<img
							src={beforeImageUrl}
							alt={`${content.before_label} diagram`}
							loading="eager"
							decoding="async"
							class="compare-layer-image"
						/>
					</div>
				{:else if hasSvgPair}
					<div role="img" aria-label="{content.before_label} diagram" class="diagram-compare-print-svg">
						{@html sanitizeSvg(content.before_svg ?? '')}
					</div>
				{/if}
			{/snippet}
			{#snippet right()}
				{#if hasImagePair}
					<div class="diagram-compare-print-image">
						<img
							src={afterImageUrl}
							alt={`${content.after_label} diagram`}
							loading="eager"
							decoding="async"
							class="compare-layer-image"
						/>
					</div>
				{:else if hasSvgPair}
					<div role="img" aria-label="{content.after_label} diagram" class="diagram-compare-print-svg">
						{@html sanitizeSvg(content.after_svg ?? '')}
					</div>
				{/if}
			{/snippet}
		</SideBySide>
		{#if content.caption}
			<p class="diagram-compare-print-caption">{content.caption}</p>
		{/if}
	</div>
{:else}
	<Card class="border-primary/10 bg-white/88 rh-pad-card">
		<div class="space-y-5">
			<div class="space-y-2">
				<p class="eyebrow text-accent">Compare</p>
				<h3 class="text-2xl font-semibold font-serif text-primary">Before and after</h3>
			</div>

			<div class="rounded-2xl border bg-gradient-to-b from-white/98 to-secondary/40 p-4 sm:p-5">
				<div class="mb-3 flex items-center justify-between rh-gap-cluster">
					<Badge
						variant="outline"
						class={beforeActive
							? 'border-primary/20 bg-primary/5 text-primary'
							: 'border-border bg-white/80 text-foreground/70'}
					>
						{content.before_label}
					</Badge>
					<span class="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground/80">
						Reveal change
					</span>
					<Badge
						variant="outline"
						class={afterActive
							? 'border-amber-300 bg-amber-50 text-amber-900'
							: 'border-border bg-white/80 text-foreground/70'}
					>
						{content.after_label}
					</Badge>
				</div>

				<div
					class="compare-stage relative aspect-[4/3] overflow-hidden rounded-xl border bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]"
					role="img"
					aria-label={content.alt_text}
				>
					{#if hasImagePair}
						<div class="compare-layer compare-layer-after w-full">
							<img
								src={afterImageUrl}
								alt=""
								aria-hidden="true"
								loading="eager"
								decoding="async"
								class="compare-layer-image"
							/>
						</div>

						<div
							class="compare-layer compare-layer-before absolute inset-0"
							style="clip-path: inset(0 0 0 {stagePosition}%);"
						>
							<img
								src={beforeImageUrl}
								alt=""
								aria-hidden="true"
								loading="eager"
								decoding="async"
								class="compare-layer-image"
							/>
						</div>
					{:else if hasSvgPair}
						<div class="compare-layer compare-layer-after w-full">
							{@html sanitizeSvg(content.after_svg ?? '')}
						</div>

						<div
							class="compare-layer compare-layer-before absolute inset-0"
							style="clip-path: inset(0 0 0 {stagePosition}%);"
						>
							{@html sanitizeSvg(content.before_svg ?? '')}
						</div>
					{/if}

					{#if seamVisible}
						<div
							class="pointer-events-none absolute inset-y-2 w-10 -translate-x-1/2 bg-gradient-to-r from-white/0 via-white/85 to-white/0 blur-sm"
							style="left: {stagePosition}%;"
						></div>
						<div
							class="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-white/95 shadow-[0_0_0_1px_rgba(15,23,42,0.12)]"
							style="left: {stagePosition}%;"
						></div>
					{/if}
				</div>

				<div class="mt-4 rounded-xl border bg-white/80 p-4">
					<div class="flex items-center justify-between text-xs font-semibold uppercase tracking-widest text-muted-foreground">
						<span>Before focus</span>
						<span>{stagePosition}% revealed</span>
						<span>After focus</span>
					</div>
					<div class="mt-3 h-2 overflow-hidden rounded-full bg-muted">
						<div
							class="h-full rounded-full bg-gradient-to-r from-primary via-sky-500 to-amber-500 transition-all duration-100"
							style="width: {stagePosition}%"
						></div>
					</div>
					<input
						type="range"
						min="0"
						max="100"
						bind:value={position}
						class="compare-slider mt-3 w-full"
						aria-label="Reveal the after state"
					/>
					<p class="mt-2 text-sm leading-relaxed text-muted-foreground">
						Slide from the full {content.before_label.toLowerCase()} state toward the full
						{content.after_label.toLowerCase()} state.
					</p>
				</div>
			</div>

			{#if beforeDetails.length > 0 || afterDetails.length > 0}
				<div class="grid rh-gap-cluster lg:grid-cols-2">
					{#if beforeDetails.length > 0}
						<div
							class="rounded-xl border p-4 transition-all {beforeActive
								? 'border-primary/20 bg-primary/5 shadow-sm'
								: 'border-border bg-white/70 opacity-75'}"
						>
							<div class="mb-3 text-xs font-semibold uppercase tracking-widest text-primary/70">
								{content.before_label} details
							</div>
							<ul class="space-y-2 text-sm leading-relaxed text-foreground/80">
								{#each beforeDetails as detail}
									<li class="flex gap-2">
										<span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60"></span>
										<span>{detail}</span>
									</li>
								{/each}
							</ul>
						</div>
					{/if}

					{#if afterDetails.length > 0}
						<div
							class="rounded-xl border p-4 transition-all {afterActive
								? 'border-amber-300/70 bg-amber-50/70 shadow-sm'
								: 'border-border bg-white/70'}"
						>
							<div class="mb-3 text-xs font-semibold uppercase tracking-widest text-amber-800/70">
								{content.after_label} details
							</div>
							{#if visibleAfterCount > 0}
								<ul class="space-y-2 text-sm leading-relaxed text-foreground/80">
									{#each afterDetails.slice(0, visibleAfterCount) as detail}
										<li class="flex gap-2">
											<span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-600/70"></span>
											<span>{detail}</span>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="text-sm leading-relaxed text-muted-foreground">
									Move the slider to begin revealing what changes in the after state.
								</p>
							{/if}
						</div>
					{/if}
				</div>
			{/if}

			<p class="text-sm leading-6 text-muted-foreground">{content.caption}</p>
		</div>
	</Card>
{/if}

<style>
	.diagram-compare-print {
		page-break-inside: avoid;
		margin: 1rem 0;
	}

	.diagram-compare-print-svg :global(svg) {
		display: block;
		width: 100%;
		height: auto;
	}

	.diagram-compare-print-image {
		aspect-ratio: 4 / 3;
		overflow: hidden;
		border-radius: 1rem;
		border: 1px solid rgba(148, 163, 184, 0.4);
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
			radial-gradient(circle at top, rgba(255, 255, 255, 0.5), transparent 60%);
	}

	.diagram-compare-print-caption {
		text-align: center;
		font-size: 0.875rem;
		font-style: italic;
		margin-top: 1rem;
	}

	.compare-slider {
		-webkit-appearance: none;
		appearance: none;
		height: 6px;
		border-radius: 9999px;
		background: hsl(38 25% 93%);
		outline: none;
		cursor: pointer;
	}

	.compare-slider::-webkit-slider-thumb {
		-webkit-appearance: none;
		appearance: none;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: white;
		border: 2px solid hsl(213 37% 17%);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
		cursor: pointer;
	}

	.compare-slider::-moz-range-thumb {
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: white;
		border: 2px solid hsl(213 37% 17%);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
		cursor: pointer;
	}

	.compare-stage {
		isolation: isolate;
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
			radial-gradient(circle at top, rgba(255, 255, 255, 0.5), transparent 60%);
	}

	.compare-layer {
		height: 100%;
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
			linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.35));
	}

	.compare-layer :global(svg) {
		display: block;
		width: 100%;
		height: 100%;
	}

	.compare-layer-before {
		will-change: clip-path;
	}

	.compare-layer-image {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>

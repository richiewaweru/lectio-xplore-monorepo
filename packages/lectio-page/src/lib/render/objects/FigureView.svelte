<script lang="ts">
	import type { FigureContent } from '$lib/contract/document';
	import { sanitizeSvg } from '$lib/utils/sanitize';

	let {
		content,
		spanning = false
	}: {
		content: FigureContent;
		spanning?: boolean;
	} = $props();

	const span = $derived(spanning || content.width === 'span');
	const svg = $derived(content.asset?.svg ? sanitizeSvg(content.asset.svg) : '');
	const status = $derived(content.asset?.status ?? (svg || content.asset?.src ? 'ready' : 'pending'));
	const showPlaceholder = $derived(
		status === 'pending' || status === 'failed' || (!svg && !content.asset?.src)
	);
	const legend = $derived(
		status === 'failed'
			? `Figure unavailable — ${content.alt_text}`
			: `Figure pending — ${content.alt_text}`
	);
	const patternId = $derived(
		`lectio-hatch-${content.alt_text.length}-${content.alt_text.slice(0, 12).replace(/\W+/g, '')}`
	);
</script>

<figure class={['lectio-figure', span && 'lectio-figure--span']}>
	{#if showPlaceholder}
		<div class="lectio-figure-fallback" role="img" aria-label={legend}>
			<svg class="lectio-figure-hatch" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
				<defs>
					<pattern
						id={patternId}
						width="8"
						height="8"
						patternUnits="userSpaceOnUse"
						patternTransform="rotate(45)"
					>
						<line x1="0" y1="0" x2="0" y2="8" stroke="#777" stroke-width="0.75" />
					</pattern>
				</defs>
				<rect width="100%" height="100%" fill="url(#{patternId})" />
			</svg>
			<p class="lectio-figure-legend">{legend}</p>
		</div>
	{:else if svg}
		{@html svg}
	{:else if content.asset?.src}
		<img src={content.asset.src} alt={content.alt_text} />
	{/if}
	{#if content.caption}
		<figcaption class="lectio-caption">{content.caption}</figcaption>
	{/if}
</figure>

<style>
	/* Technical hairline + hatch — greyscale-legible; no solid colour fill. */
	.lectio-figure-fallback {
		position: relative;
		border: 0.5pt solid #777;
		min-height: 40mm;
		display: flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		overflow: hidden;
	}
	.lectio-figure-hatch {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
	}
	.lectio-figure-legend {
		position: relative;
		z-index: 1;
		margin: 0;
		padding: 4pt 8pt;
		max-width: 90%;
		text-align: center;
		font-size: 9pt;
		line-height: 1.3;
		color: #111;
		background: #fff;
	}
</style>

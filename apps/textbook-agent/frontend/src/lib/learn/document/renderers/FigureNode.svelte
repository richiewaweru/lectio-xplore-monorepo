<script lang="ts">
	import type { FigureNode } from '../types';
	import { resolveAssetUrl, type AssetRef } from '../resolve-asset';
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props {
		node: FigureNode;
		/** Optional asset map (id → url) when the document carries resolved media. */
		assets?: Record<string, AssetRef> | null;
		figureNumber?: number;
	}

	let { node, assets = null, figureNumber = undefined }: Props = $props();

	const src = $derived(resolveFigureAsset(node.asset_id, assets));
	const alt = $derived(node.alt || node.caption || 'Figure');
	let failedSrc = $state<string | null>(null);
	let lastSrc = $state<string | null>(null);
	$effect(() => {
		if (lastSrc !== src) {
			lastSrc = src;
			failedSrc = null;
		}
	});

	function resolveFigureAsset(assetId: string | null | undefined, assetMap: Record<string, AssetRef> | null): string | null {
		if (assetMap && assetId && !assetMap[assetId] && !/^(https?:\/\/|data:|blob:|\/)/i.test(assetId)) return null;
		return resolveAssetUrl(assetId, assetMap);
	}

	function handleImageError() {
		failedSrc = src;
	}
</script>

{#if node.status === 'unavailable' && !src}
	<figure class="learn-figure" data-testid="figure-unavailable">
		<div
			class="figure-unavailable"
			role="img"
			aria-label={`Figure couldn't be generated.${node.unavailable_reason ? ` ${node.unavailable_reason}` : ''} ${alt}`}
		>
			<span class="unavailable-title">Figure couldn't be generated</span>
			{#if node.unavailable_reason}<span class="unavailable-reason">{node.unavailable_reason}</span>{/if}
		</div>
		{#if node.caption}
			<figcaption>
				{#if figureNumber && !/^Figure\s+\d+\./i.test(node.caption)}Figure {figureNumber}.{' '}{/if}<InlineMarkup value={node.caption} />
			</figcaption>
		{/if}
	</figure>
{:else if src && failedSrc !== src}
	<figure class="learn-figure" data-testid="figure-node">
		<img class="figure-img" src={src} alt={alt} data-testid="figure-img" onerror={handleImageError} />
		{#if node.caption}
			<figcaption>
				{#if figureNumber && !/^Figure\s+\d+\./i.test(node.caption)}Figure {figureNumber}.{' '}{/if}<InlineMarkup value={node.caption} />
			</figcaption>
		{/if}
	</figure>
{/if}

<style>
	.learn-figure {
		margin: 0;
		display: grid;
		gap: 8px;
	}
	.figure-img {
		display: block;
		width: 100%;
		max-height: 420px;
		object-fit: contain;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--surface, #fff);
	}
	.figure-unavailable {
		display: grid;
		gap: 4px;
		place-content: center;
		justify-items: center;
		min-height: 160px;
		padding: 24px 16px;
		text-align: center;
		color: var(--muted, #5b6460);
		border: 2px dashed var(--rule, #b5bbb8);
		border-radius: 10px;
		background: repeating-linear-gradient(
			135deg,
			transparent 0 10px,
			color-mix(in srgb, var(--rule, #b5bbb8) 25%, transparent) 10px 11px
		);
	}
	.unavailable-title {
		font-size: 14px;
		font-weight: 600;
	}
	.unavailable-reason {
		font-size: 13px;
		line-height: 1.45;
	}
	figcaption {
		font-size: 13px;
		line-height: 1.45;
		color: var(--muted, #5b6460);
	}
</style>

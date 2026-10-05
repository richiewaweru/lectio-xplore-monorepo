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

	function resolveFigureAsset(assetId: string | null | undefined, assetMap: Record<string, AssetRef> | null): string | null {
		if (assetMap && assetId && !assetMap[assetId] && !/^(https?:\/\/|data:|blob:|\/)/i.test(assetId)) return null;
		return resolveAssetUrl(assetId, assetMap);
	}
</script>

{#if src}
	<figure class="learn-figure" data-testid="figure-node">
		<img class="figure-img" src={src} alt={alt} data-testid="figure-img" />
		{#if node.caption}
			<figcaption>
				{#if figureNumber && !/^Figure\s+\d+\./i.test(node.caption)}Figure {figureNumber}. {/if}<InlineMarkup value={node.caption} />
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
	figcaption {
		font-size: 13px;
		line-height: 1.45;
		color: var(--muted, #5b6460);
	}
</style>

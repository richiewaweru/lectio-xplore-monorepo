<script lang="ts">
	import type { FigureNode } from '../types';
	import { resolveAssetUrl, type AssetRef } from '../resolve-asset';

	interface Props {
		node: FigureNode;
		/** Optional asset map (id → url) when the document carries resolved media. */
		assets?: Record<string, AssetRef> | null;
	}

	let { node, assets = null }: Props = $props();

	const src = $derived(resolveAssetUrl(node.asset_id, assets));
	const alt = $derived(node.alt || node.caption || 'Figure');
</script>

<figure class="learn-figure" data-testid="figure-node" data-node-id={node.id}>
	{#if src}
		<img
			class="figure-img"
			src={src}
			alt={alt}
			data-asset-id={node.asset_id ?? undefined}
			data-testid="figure-img"
		/>
	{:else}
		<div class="asset-slot empty" role="img" aria-label={alt}>
			<span class="asset-label">{node.alt || 'No asset'}</span>
		</div>
	{/if}
	{#if node.caption}
		<figcaption>{node.caption}</figcaption>
	{/if}
</figure>

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
		background: var(--surface, #f7f7f5);
	}
	.asset-slot {
		display: grid;
		place-items: center;
		min-height: 120px;
		border: 1px solid var(--rule, #ccc);
		border-radius: 10px;
		background: var(--surface, #f7f7f5);
		color: var(--ink-3, #666);
		font: 500 12px 'IBM Plex Mono', monospace;
		letter-spacing: 0.04em;
	}
	.asset-slot.empty {
		border-style: dashed;
	}
	figcaption {
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink-2, #444);
	}
</style>

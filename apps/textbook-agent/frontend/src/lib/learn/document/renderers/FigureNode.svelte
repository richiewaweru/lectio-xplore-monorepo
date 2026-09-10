<script lang="ts">
	import type { FigureNode } from '../types';

	interface Props {
		node: FigureNode;
	}

	let { node }: Props = $props();
</script>

<figure class="learn-figure" data-testid="figure-node" data-node-id={node.id}>
	{#if node.asset_id}
		<div class="asset-slot" data-asset-id={node.asset_id} role="img" aria-label={node.alt || node.caption || 'Figure'}>
			<span class="asset-label">Figure · {node.asset_id}</span>
		</div>
	{:else}
		<div class="asset-slot empty" role="img" aria-label={node.alt || 'Figure placeholder'}>
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

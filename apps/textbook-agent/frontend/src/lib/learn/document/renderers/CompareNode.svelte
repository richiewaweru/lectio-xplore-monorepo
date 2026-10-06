<script lang="ts">
	import type { CompareNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';
	interface Props { node: CompareNode; }
	let { node }: Props = $props();
</script>

<div class="learn-compare" data-testid="compare-node">
	{#each node.items as item, index (index)}
		<article class="compare-card">
			{#if item.label}<p class="label"><InlineMarkup value={item.label} /></p>{/if}
			<h3><InlineMarkup value={item.title} /></h3>
			<p><InlineMarkup value={item.body} /></p>
		</article>
	{/each}
</div>

<style>
	.learn-compare { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
	.compare-card { min-width: 0; padding: 20px; border: 1px solid var(--rule, #ddd8cc); border-radius: 14px; background: var(--sand, #f3eee3); }
	.compare-card .label { margin: 0 0 8px; color: var(--muted, #5b6460); font-size: 14px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
	.compare-card h3 { margin: 0 0 8px; font: 700 21px/1.25 var(--font-serif, Fraunces, Georgia, serif); }
	.compare-card > p:last-child { margin: 0; font-size: 18px; line-height: 1.6; }
	@media (max-width: 600px) { .learn-compare { grid-template-columns: 1fr; } }
</style>

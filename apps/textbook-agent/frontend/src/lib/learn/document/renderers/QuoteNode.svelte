<script lang="ts">
	import type { QuoteNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';
	interface Props { node: QuoteNode; }
	let { node }: Props = $props();
</script>

<blockquote class="learn-quote" data-testid="quote-node">
	<p><InlineMarkup value={node.text} /></p>
	{#if node.attribution}<cite><InlineMarkup value={node.attribution} /></cite>{/if}
</blockquote>

<style>
	.learn-quote { margin: 0; padding: 22px 24px; border-left: 4px solid var(--rule-strong, #c9c3b5); border-radius: 0 14px 14px 0; background: var(--sand, #f3eee3); }
	.learn-quote p { margin: 0; font: 400 23px/1.4 var(--font-serif, Fraunces, Georgia, serif); }
	.learn-quote cite { display: block; margin-top: 12px; color: var(--muted, #5b6460); font-size: 14px; font-style: normal; font-weight: 700; }
</style>

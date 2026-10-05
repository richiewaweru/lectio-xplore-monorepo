<script lang="ts">
	import type { ParagraphNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props {
		node: ParagraphNode;
	}

	let { node }: Props = $props();
</script>

<div class="learn-paragraph" data-testid="paragraph-node">
	{#each node.text.split(/\n\s*\n/) as paragraph}
		<p><InlineMarkup value={paragraph} /></p>
	{/each}
</div>

<style>
	.learn-paragraph {
		display: grid;
		gap: 16px;
		margin: 0;
		font-size: 18px;
		line-height: 1.6;
		color: var(--ink, #1a1a1a);
	}
	.learn-paragraph p { margin: 0; text-wrap: pretty; hyphens: manual; }
</style>

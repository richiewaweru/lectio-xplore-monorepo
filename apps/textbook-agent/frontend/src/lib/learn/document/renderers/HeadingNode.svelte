<script lang="ts">
	import type { HeadingNode } from '../types';

	interface Props {
		node: HeadingNode;
	}

	let { node }: Props = $props();

	const level = $derived(Math.min(3, Math.max(1, node.level ?? 2)) as 1 | 2 | 3);
</script>

{#if level === 1}
	<h1 class="learn-heading" data-testid="heading-node" data-node-id={node.id} data-level="1">
		{node.text}
	</h1>
{:else if level === 2}
	<h2 class="learn-heading" data-testid="heading-node" data-node-id={node.id} data-level="2">
		{node.text}
	</h2>
{:else}
	<h3 class="learn-heading" data-testid="heading-node" data-node-id={node.id} data-level="3">
		{node.text}
	</h3>
{/if}

<style>
	.learn-heading {
		margin: 0;
		color: var(--ink, #1a1a1a);
		font-family: Fraunces, Georgia, serif;
		letter-spacing: -0.02em;
		line-height: 1.2;
	}
	.learn-heading[data-level='1'] {
		font-size: 28px;
		font-weight: 500;
	}
	.learn-heading[data-level='2'] {
		font-size: 22px;
		font-weight: 500;
	}
	.learn-heading[data-level='3'] {
		font-size: 17px;
		font-weight: 600;
	}
</style>

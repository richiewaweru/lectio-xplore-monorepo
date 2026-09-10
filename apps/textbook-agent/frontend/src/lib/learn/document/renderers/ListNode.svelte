<script lang="ts">
	import type { ListNode } from '../types';

	interface Props {
		node: ListNode;
	}

	let { node }: Props = $props();

	const ordered = $derived(node.ordered === true);
</script>

{#if ordered}
	<ol class="learn-list" data-testid="list-node" data-node-id={node.id} data-ordered="true">
		{#each node.items as item, i (i)}
			<li>{item}</li>
		{/each}
	</ol>
{:else}
	<ul class="learn-list" data-testid="list-node" data-node-id={node.id} data-ordered="false">
		{#each node.items as item, i (i)}
			<li>{item}</li>
		{/each}
	</ul>
{/if}

<style>
	.learn-list {
		margin: 0;
		padding-left: 1.35em;
		color: var(--ink, #1a1a1a);
		font-size: 15px;
		line-height: 1.6;
	}
	.learn-list li + li {
		margin-top: 4px;
	}
</style>

<script lang="ts">
	import type { ListNode } from '../types';
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props {
		node: ListNode;
	}

	let { node }: Props = $props();

	const ordered = $derived(node.ordered === true);
</script>

{#if ordered}
	<ol class="learn-list" data-testid="list-node" data-ordered="true">
		{#each node.items as item, i (i)}
			<li><InlineMarkup value={item} /></li>
		{/each}
	</ol>
{:else}
	<ul class="learn-list" data-testid="list-node" data-ordered="false">
		{#each node.items as item, i (i)}
			<li><InlineMarkup value={item} /></li>
		{/each}
	</ul>
{/if}

<style>
	.learn-list {
		margin: 0;
		padding-left: 1.35em;
		color: var(--ink, #1a1a1a);
		font-size: 18px;
		line-height: 1.6;
	}
	.learn-list[data-ordered='false'] { list-style: disc; }
	.learn-list li + li {
		margin-top: 14px;
	}
	.learn-list[data-ordered='true'] { list-style: none; counter-reset: learn-step; padding-left: 0; }
	.learn-list[data-ordered='true'] li { counter-increment: learn-step; display: grid; grid-template-columns: 30px 1fr; gap: 10px; align-items: start; }
	.learn-list[data-ordered='true'] li::before { content: counter(learn-step); display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--green, #1b5e40); color: white; font-size: 14px; font-weight: 700; line-height: 1; }
</style>

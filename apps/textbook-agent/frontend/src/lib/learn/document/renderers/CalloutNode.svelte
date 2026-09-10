<script lang="ts">
	import type { CalloutNode } from '../types';

	interface Props {
		node: CalloutNode;
	}

	let { node }: Props = $props();

	const tone = $derived(node.tone ?? 'note');
</script>

<aside
	class="learn-callout"
	data-testid="callout-node"
	data-node-id={node.id}
	data-tone={tone}
>
	{#if node.title}
		<p class="title">{node.title}</p>
	{:else}
		<p class="title tone-label">{tone}</p>
	{/if}
	<p class="body">{node.body}</p>
</aside>

<style>
	.learn-callout {
		margin: 0;
		padding: 12px 14px;
		border: 1px solid var(--rule, #ccc);
		border-left-width: 3px;
		border-radius: 10px;
		background: var(--surface, #f7f7f5);
		display: grid;
		gap: 6px;
	}
	.learn-callout[data-tone='warning'] {
		border-left-color: #b45309;
	}
	.learn-callout[data-tone='tip'] {
		border-left-color: #0f766e;
	}
	.learn-callout[data-tone='important'] {
		border-left-color: #9f1239;
	}
	.learn-callout[data-tone='note'] {
		border-left-color: var(--ink-3, #666);
	}
	.title {
		margin: 0;
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--ink-3, #666);
	}
	.body {
		margin: 0;
		font-size: 14px;
		line-height: 1.55;
		color: var(--ink, #1a1a1a);
	}
</style>

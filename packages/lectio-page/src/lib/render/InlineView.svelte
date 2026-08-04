<script lang="ts">
	import InlineView from './InlineView.svelte';
	import katex from 'katex';
	import type { InlineNode } from '$lib/contract/document';

	let { nodes }: { nodes: InlineNode[] } = $props();

	function mathHtml(latex: string): string {
		try {
			return katex.renderToString(latex, { throwOnError: false, output: 'html' });
		} catch {
			return latex;
		}
	}
</script>

{#each nodes as node}
	{#if node.type === 'text'}
		{node.value}
	{:else if node.type === 'strong'}
		<strong><InlineView nodes={node.children} /></strong>
	{:else if node.type === 'emphasis'}
		<em><InlineView nodes={node.children} /></em>
	{:else if node.type === 'small-caps'}
		<span style="font-variant: small-caps"><InlineView nodes={node.children} /></span>
	{:else if node.type === 'term'}
		<span title={node.definition}>{node.value}</span>
	{:else if node.type === 'math'}
		{@html mathHtml(node.latex)}
	{:else if node.type === 'reference'}
		<a href={`#${node.target_id}`}>{node.label}</a>
	{/if}
{/each}

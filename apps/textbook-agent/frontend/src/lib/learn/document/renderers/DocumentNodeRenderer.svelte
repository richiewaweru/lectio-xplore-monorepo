<script lang="ts">
	import type { DocumentNode } from '../types';
	import type { AssetRef } from '../resolve-asset';
	import ParagraphNodeView from './ParagraphNode.svelte';
	import HeadingNodeView from './HeadingNode.svelte';
	import ListNodeView from './ListNode.svelte';
	import FigureNodeView from './FigureNode.svelte';
	import TableNodeView from './TableNode.svelte';
	import CalloutNodeView from './CalloutNode.svelte';

	interface Props {
		node: DocumentNode;
		assets?: Record<string, AssetRef> | null;
	}

	let { node, assets = null }: Props = $props();
</script>

<div class="document-node-renderer" data-testid="document-node-renderer" data-kind={node.kind}>
	{#if node.kind === 'paragraph'}
		<ParagraphNodeView {node} />
	{:else if node.kind === 'heading'}
		<HeadingNodeView {node} />
	{:else if node.kind === 'list'}
		<ListNodeView {node} />
	{:else if node.kind === 'figure'}
		<FigureNodeView {node} {assets} />
	{:else if node.kind === 'table'}
		<TableNodeView {node} />
	{:else if node.kind === 'callout'}
		<CalloutNodeView {node} />
	{/if}
</div>

<style>
	.document-node-renderer {
		min-width: 0;
	}
</style>

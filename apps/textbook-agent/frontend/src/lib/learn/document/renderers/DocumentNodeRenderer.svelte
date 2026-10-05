<script module lang="ts">
	const warnedKinds = new Set<string>();
</script>

<script lang="ts">
	import type { DocumentNode } from '../types';
	import type { AssetRef } from '../resolve-asset';
	import ParagraphNodeView from './ParagraphNode.svelte';
	import HeadingNodeView from './HeadingNode.svelte';
	import ListNodeView from './ListNode.svelte';
	import FigureNodeView from './FigureNode.svelte';
	import TableNodeView from './TableNode.svelte';
	import CalloutNodeView from './CalloutNode.svelte';
	import EquationNodeView from './EquationNode.svelte';
	import QuoteNodeView from './QuoteNode.svelte';
	import CompareNodeView from './CompareNode.svelte';
	import UnknownNodeView from './UnknownNode.svelte';

	interface Props {
		node: DocumentNode;
		assets?: Record<string, AssetRef> | null;
		figureNumber?: number;
	}

	let { node, assets = null, figureNumber = undefined }: Props = $props();
	function fallbackNode(value: DocumentNode): Record<string, unknown> {
		const unknown = value as unknown as Record<string, unknown>;
		const kind = String(unknown.kind ?? 'unknown');
		if (!warnedKinds.has(kind)) {
			warnedKinds.add(kind);
			console.warn(`Learn renderer received unknown document kind: ${kind}`);
		}
		return unknown;
	}
</script>

<div class="document-node-renderer" data-testid="document-node-renderer" data-kind={node.kind}>
	{#if node.kind === 'paragraph'}
		<ParagraphNodeView {node} />
	{:else if node.kind === 'heading'}
		<HeadingNodeView {node} />
	{:else if node.kind === 'list'}
		<ListNodeView {node} />
	{:else if node.kind === 'figure'}
		<FigureNodeView {node} {assets} {figureNumber} />
	{:else if node.kind === 'table'}
		<TableNodeView {node} />
	{:else if node.kind === 'callout'}
		<CalloutNodeView {node} />
	{:else if node.kind === 'equation'}
		<EquationNodeView {node} />
	{:else if node.kind === 'quote'}
		<QuoteNodeView {node} />
	{:else if node.kind === 'compare'}
		<CompareNodeView {node} />
	{:else}
		<UnknownNodeView node={fallbackNode(node)} />
	{/if}
</div>

<style>
	.document-node-renderer {
		min-width: 0;
	}
</style>

<script lang="ts">
	import type { LearnDocument, LearnNode } from './types';
	import DocumentNodeRenderer from './renderers/DocumentNodeRenderer.svelte';
	import InteractionNodeRenderer from './renderers/InteractionNodeRenderer.svelte';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		editable?: boolean;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		editable = false
	}: Props = $props();

	const nodes = $derived(document.nodes ?? []);

	function select(node: LearnNode) {
		onSelectNode?.(node.id);
	}

	function onKeydown(event: KeyboardEvent, node: LearnNode) {
		if (!editable && !onSelectNode) return;
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			select(node);
		}
	}
</script>

<div
	class="document-canvas"
	data-testid="document-canvas"
	data-document-id={document.id}
	data-node-count={nodes.length}
	data-editable={editable ? 'true' : 'false'}
>
	{#each nodes as node (node.id)}
		{@const selected = selectedNodeId === node.id}
		<div
			class="canvas-node"
			class:selected
			data-testid="canvas-node"
			data-node-id={node.id}
			data-kind={node.kind}
			data-selected={selected ? 'true' : 'false'}
			role={onSelectNode ? 'button' : undefined}
			tabindex={onSelectNode ? 0 : undefined}
			onclick={() => onSelectNode && select(node)}
			onkeydown={(e) => onKeydown(e, node)}
		>
			{#if node.kind === 'interaction'}
				<InteractionNodeRenderer {node} />
			{:else}
				<DocumentNodeRenderer {node} />
			{/if}
		</div>
	{/each}
	{#if nodes.length === 0}
		<p class="empty" data-testid="document-canvas-empty">This document has no nodes yet.</p>
	{/if}
</div>

<style>
	.document-canvas {
		display: grid;
		gap: 16px;
	}
	.canvas-node {
		min-width: 0;
		border-radius: 10px;
		outline: 2px solid transparent;
		outline-offset: 2px;
		transition: outline-color 120ms ease;
	}
	.canvas-node.selected {
		outline-color: var(--ink-3, #888);
	}
	.canvas-node[role='button'] {
		cursor: pointer;
	}
	.empty {
		margin: 0;
		color: var(--ink-2, #444);
		font-size: 14px;
	}
</style>

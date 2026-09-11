<script lang="ts">
	import type { CalloutTone, LearnDocument, LearnNode } from './types';
	import type { AssetRef } from './resolve-asset';
	import type {
		InteractionSubmitHandler,
		ServerEvaluation
	} from '$lib/learn/interactions/types';
	import type { InteractionAttemptState } from './types';
	import DocumentNodeRenderer from './renderers/DocumentNodeRenderer.svelte';
	import InteractionNodeRenderer from './renderers/InteractionNodeRenderer.svelte';
	import ParagraphEditor from './editors/ParagraphEditor.svelte';
	import ListEditor from './editors/ListEditor.svelte';
	import HeadingEditor from './editors/HeadingEditor.svelte';
	import CalloutEditor from './editors/CalloutEditor.svelte';
	import FigureEditor from './editors/FigureEditor.svelte';
	import TableEditor from './editors/TableEditor.svelte';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		editable?: boolean;
		assets?: Record<string, AssetRef> | null;
		attemptsByInteraction?: Map<string, InteractionAttemptState>;
		onSubmitInteraction?: (args: {
			interactionId: string;
			response: Record<string, unknown>;
		}) => Promise<ServerEvaluation>;
		onUpdateNodeText?: (nodeId: string, text: string) => void;
		onUpdateListItems?: (nodeId: string, items: string[]) => void;
		onUpdateHeading?: (
			nodeId: string,
			patch: { text?: string; level?: 1 | 2 | 3 }
		) => void;
		onUpdateCallout?: (
			nodeId: string,
			patch: { body?: string; title?: string; tone?: CalloutTone }
		) => void;
		onUpdateFigure?: (
			nodeId: string,
			patch: { caption?: string; alt?: string; asset_id?: string | null }
		) => void;
		onUpdateTable?: (
			nodeId: string,
			patch: { headers?: string[]; rows?: string[][]; caption?: string }
		) => void;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		editable = false,
		assets = null,
		attemptsByInteraction = new Map(),
		onSubmitInteraction = undefined,
		onUpdateNodeText = undefined,
		onUpdateListItems = undefined,
		onUpdateHeading = undefined,
		onUpdateCallout = undefined,
		onUpdateFigure = undefined,
		onUpdateTable = undefined
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

	function initialEval(nodeId: string): ServerEvaluation | null {
		const attempt = attemptsByInteraction.get(nodeId);
		if (!attempt?.outcome) return null;
		return {
			outcome: attempt.outcome,
			feedback: attempt.feedback ?? attempt.outcome,
			score_earned: attempt.score_earned,
			score_possible: attempt.score_possible
		};
	}

	function submitFor(nodeId: string): InteractionSubmitHandler | undefined {
		if (!onSubmitInteraction) return undefined;
		return (response) => onSubmitInteraction({ interactionId: nodeId, response });
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
			{#if editable && selected && node.kind !== 'interaction'}
				<div class="editor-pane" data-testid="node-editor" data-kind={node.kind}>
					{#if node.kind === 'paragraph'}
						<ParagraphEditor
							value={node.text}
							onChange={(text) => onUpdateNodeText?.(node.id, text)}
						/>
					{:else if node.kind === 'heading'}
						<HeadingEditor
							value={node.text}
							level={node.level ?? 2}
							onChange={(text) => onUpdateHeading?.(node.id, { text })}
							onLevelChange={(level) => onUpdateHeading?.(node.id, { level })}
						/>
					{:else if node.kind === 'list'}
						<ListEditor
							items={node.items}
							ordered={node.ordered}
							onChange={(items) => onUpdateListItems?.(node.id, items)}
						/>
					{:else if node.kind === 'callout'}
						<CalloutEditor
							body={node.body}
							title={node.title ?? ''}
							tone={node.tone ?? 'note'}
							onChange={(patch) => onUpdateCallout?.(node.id, patch)}
						/>
					{:else if node.kind === 'figure'}
						<FigureEditor
							caption={node.caption ?? ''}
							alt={node.alt ?? ''}
							assetId={node.asset_id ?? null}
							onChange={(patch) => onUpdateFigure?.(node.id, patch)}
						/>
					{:else if node.kind === 'table'}
						<TableEditor
							headers={node.headers ?? []}
							rows={node.rows ?? []}
							caption={node.caption ?? ''}
							onChange={(patch) => onUpdateTable?.(node.id, patch)}
						/>
					{/if}
				</div>
			{:else if node.kind === 'interaction'}
				<InteractionNodeRenderer
					{node}
					onSubmit={submitFor(node.id)}
					initialEvaluation={initialEval(node.id)}
				/>
			{:else}
				<DocumentNodeRenderer {node} {assets} />
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
	.editor-pane {
		min-width: 0;
	}
	.empty {
		margin: 0;
		color: var(--ink-2, #444);
		font-size: 14px;
	}
</style>

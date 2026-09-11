<script lang="ts">
	/**
	 * Parallel to OrderedBlockList for LearnDocument v2 (flat ordered nodes).
	 * Attempt state stays outside node content — pass via attemptsByInteraction / onSubmitAttempt.
	 */
	import DocumentCanvas from '$lib/learn/document/DocumentCanvas.svelte';
	import type { InteractionAttemptState, LearnDocument } from '$lib/learn/document/types';
	import type {
		AttemptSubmitHandler,
		ServerEvaluation
	} from '$lib/learn/interactions/types';
	import type { StoredAttempt } from './api/attempts';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		/** Kept for API parity with OrderedBlockList; not embedded in nodes. */
		attemptsByInteraction?: Map<string, InteractionAttemptState | StoredAttempt>;
		preview?: boolean;
		onSubmitAttempt?: AttemptSubmitHandler;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		attemptsByInteraction = new Map(),
		preview = false,
		onSubmitAttempt = undefined
	}: Props = $props();

	const attemptStates = $derived.by(() => {
		const map = new Map<string, InteractionAttemptState>();
		for (const [id, attempt] of attemptsByInteraction.entries()) {
			if ('interactionId' in attempt) {
				map.set(id, attempt as InteractionAttemptState);
				continue;
			}
			const stored = attempt as StoredAttempt;
			map.set(id, {
				interactionId: stored.interaction_id,
				outcome: stored.outcome,
				feedback: stored.outcome,
				response: stored.response_json,
				score_earned: stored.score_earned,
				score_possible: stored.score_possible
			});
		}
		return map;
	});

	let activeSectionId = $state<string>('all');
	const sections = $derived(document.sections ?? []);
	const viewDocument = $derived.by(() => {
		if (activeSectionId === 'all' || sections.length === 0) return document;
		const section = sections.find((item) => item.id === activeSectionId);
		const allowed = new Set(section?.node_ids ?? []);
		return { ...document, nodes: document.nodes.filter((node) => allowed.has(node.id)) };
	});

	async function onSubmitInteraction(args: {
		interactionId: string;
		response: Record<string, unknown>;
	}): Promise<ServerEvaluation> {
		if (preview || !onSubmitAttempt) {
			throw new Error('Preview mode — attempts are not persisted');
		}
		return onSubmitAttempt({
			interactionId: args.interactionId,
			response: args.response
		});
	}
</script>

<div
	class="ordered-document-list"
	data-testid="ordered-document-list"
	data-document-version="2"
	data-preview={preview ? 'true' : 'false'}
	data-persist-attempts={preview ? 'false' : 'true'}
	data-node-count={viewDocument.nodes.length}
>
	{#if sections.length > 0}
		<nav class="section-tabs" data-testid="runtime-section-tabs" aria-label="Lesson sections">
			<button
				type="button"
				class:active={activeSectionId === 'all'}
				onclick={() => (activeSectionId = 'all')}
			>
				All
			</button>
			{#each sections as section}
				<button
					type="button"
					class:active={activeSectionId === section.id}
					title={section.title || section.id}
					onclick={() => (activeSectionId = section.id)}
				>
					{section.id}
				</button>
			{/each}
		</nav>
	{/if}
	<DocumentCanvas
		document={viewDocument}
		{selectedNodeId}
		{onSelectNode}
		attemptsByInteraction={attemptStates}
		onSubmitInteraction={preview || !onSubmitAttempt ? undefined : onSubmitInteraction}
	/>
	{#if preview}
		<p class="preview-note" data-testid="preview-attempt-isolation">
			Preview — attempts are not saved.
		</p>
	{/if}
</div>

<style>
	.ordered-document-list {
		display: grid;
		gap: 16px;
		min-width: 0;
	}
	.preview-note {
		margin: 0;
		color: var(--ink-3, #666);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.section-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.section-tabs button {
		border: 1px solid var(--rule, #ccc);
		border-radius: 8px;
		background: var(--paper, #fff);
		padding: 6px 10px;
		cursor: pointer;
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		text-transform: capitalize;
	}
	.section-tabs button.active {
		font-weight: 600;
		border-color: var(--ink, #1a1a1a);
	}
</style>

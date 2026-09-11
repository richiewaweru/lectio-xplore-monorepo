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
	data-node-count={document.nodes.length}
>
	<DocumentCanvas
		{document}
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
</style>

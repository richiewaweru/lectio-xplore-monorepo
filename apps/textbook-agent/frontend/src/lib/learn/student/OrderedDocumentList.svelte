<script lang="ts">
	/**
	 * Parallel to OrderedBlockList for LearnDocument v2 (flat ordered nodes).
	 * Attempt state stays outside node content — pass via attemptsByInteraction.
	 */
	import DocumentCanvas from '$lib/learn/document/DocumentCanvas.svelte';
	import type { InteractionAttemptState, LearnDocument } from '$lib/learn/document/types';

	interface Props {
		document: LearnDocument;
		selectedNodeId?: string | null;
		onSelectNode?: (nodeId: string) => void;
		/** Kept for API parity with OrderedBlockList; not embedded in nodes. */
		attemptsByInteraction?: Map<string, InteractionAttemptState>;
		preview?: boolean;
	}

	let {
		document,
		selectedNodeId = null,
		onSelectNode = undefined,
		attemptsByInteraction = new Map(),
		preview = false
	}: Props = $props();

	// Reserved for later interaction mount wiring — keep attempts out of document content.
	void attemptsByInteraction;
</script>

<div
	class="ordered-document-list"
	data-testid="ordered-document-list"
	data-document-version="2"
	data-preview={preview ? 'true' : 'false'}
	data-persist-attempts={preview ? 'false' : 'true'}
	data-node-count={document.nodes.length}
>
	<DocumentCanvas {document} {selectedNodeId} {onSelectNode} />
</div>

<style>
	.ordered-document-list {
		display: grid;
		gap: 16px;
		min-width: 0;
	}
</style>

<script lang="ts">
	/**
	 * Mount retained interaction UI for LearnDocument v2 nodes.
	 * Attempts stay outside ordinary document content (parent owns submit).
	 */
	import InteractionShell from '$lib/learn/interactions/InteractionShell.svelte';
	import type { InteractionSubmitHandler, ServerEvaluation } from '$lib/learn/interactions/types';
	import type { InteractionNode } from '../types';

	interface Props {
		node: InteractionNode;
		disabled?: boolean;
		onSubmit?: InteractionSubmitHandler;
		initialEvaluation?: ServerEvaluation | null;
		questionNumber?: number;
	}

	let {
		node,
		disabled = false,
		onSubmit = undefined,
		initialEvaluation = null,
		questionNumber = undefined
	}: Props = $props();
</script>

<section
	class="interaction-node"
	data-testid="interaction-node-renderer"
	data-interaction-type={node.interaction_type}
	data-node-id={node.id}
	data-question-number={questionNumber}
>
	<InteractionShell {node} {disabled} {onSubmit} {initialEvaluation} {questionNumber} />
</section>

<style>
	.interaction-node {
		margin: 0;
	}
</style>

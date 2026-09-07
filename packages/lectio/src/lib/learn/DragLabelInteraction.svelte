<script lang="ts">
	/** Drag-label uses match-pairs evaluation with keyboard-accessible assign. */
	import MatchPairsInteraction from './MatchPairsInteraction.svelte';
	import type { FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Props {
		prompt: string;
		labels: Array<{ id: string; label: string }>;
		targets: Array<{ id: string; label: string }>;
		correctPairs: Array<{ left: string; right: string }>;
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, labels, targets, correctPairs, feedback, ariaLabel = prompt }: Props = $props();
</script>

<div data-testid="drag-label-interaction">
	<MatchPairsInteraction
		{prompt}
		left={labels}
		right={targets}
		{correctPairs}
		{feedback}
		{ariaLabel}
	/>
</div>

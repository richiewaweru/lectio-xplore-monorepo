/**
 * ImageChoice is ChoiceInteraction with image options (same choice evaluator).
 */
<script lang="ts">
	import ChoiceInteraction from './ChoiceInteraction.svelte';
	import type { FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Option {
		id: string;
		text: string;
		imageUrl?: string;
	}

	interface Props {
		prompt: string;
		options: Option[];
		correctOptionId: string;
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, options, correctOptionId, feedback, ariaLabel = prompt }: Props = $props();
</script>

<div data-testid="image-choice-interaction">
	<ChoiceInteraction
		{prompt}
		{options}
		{correctOptionId}
		{feedback}
		{ariaLabel}
		variant="image"
	/>
</div>

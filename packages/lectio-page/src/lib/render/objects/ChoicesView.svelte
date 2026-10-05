<script lang="ts">
	import type { ChoicesContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, questionId = '', role = '' }: { content: ChoicesContent; questionId?: string; role?: string } = $props();
</script>

<div class="lectio-choices">
	{#if questionId}<p class="lectio-choice-question-number"><strong>{questionId}.</strong></p>{/if}
	<p>
		{#if content.marks != null}
			<span class="lectio-question-marks">[{content.marks}]</span>
		{/if}
		<InlineView nodes={asRichText(content.stem)} />
	</p>
	{#each content.options as option}
		<div class="lectio-choice">
			<span class="lectio-choice-mark" aria-hidden="true">○</span>
			<span class="lectio-choice-letter">{option.letter}.</span>
			<InlineView nodes={asRichText(option.text)} />
		</div>
	{/each}
	{#if role === 'predict'}
		<p class="lectio-prediction-reason"><strong>I think this because:</strong></p>
		<div class="lectio-answer-line"></div>
	{/if}
</div>

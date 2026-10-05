<script lang="ts">
	import type { ChoicesContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, questionId = '', role = '' }: { content: ChoicesContent; questionId?: string; role?: string } = $props();
	const taskNumber = $derived(/^Q(\d+)$/.exec(questionId)?.[1] ?? '');
	const modeLabels: Record<string, string> = { predict: 'Predict', check: 'Check', practice: 'Practice' };
	const mode = $derived(modeLabels[role] ?? '');
</script>

<div class={['lectio-choices', taskNumber && 'lectio-task']}>
	{#if taskNumber}
		<div class="lectio-task-header">Question {taskNumber}{#if mode}&nbsp;·&nbsp;{mode}{/if}</div>
	{:else if questionId}
		<p class="lectio-choice-question-number"><strong>{questionId}.</strong></p>
	{/if}
	<div class={taskNumber && 'lectio-task-body'}>
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
		<p class="lectio-prediction-reason">I think this because</p>
		<div class="lectio-answer-line"></div>
		<div class="lectio-answer-line"></div>
	{/if}
	</div>
</div>

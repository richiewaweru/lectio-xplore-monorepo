<script lang="ts">
	import type { QuestionsContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, role = '' }: { content: QuestionsContent; role?: string } = $props();

	const modeLabels: Record<string, string> = { predict: 'Predict', check: 'Check', practice: 'Practice' };
	const mode = $derived(modeLabels[role] ?? '');
	const taskNumber = (id: string) => /^Q(\d+)$/.exec(id)?.[1] ?? '';
</script>

{#if content.instructions}
	<p><InlineView nodes={asRichText(content.instructions)} /></p>
{/if}

{#each content.items as item, i}
	<div class={['lectio-question', taskNumber(item.id) && 'lectio-task']} id={item.id}>
		{#if taskNumber(item.id)}
			<div class="lectio-task-header">Question {taskNumber(item.id)}{#if mode}&nbsp;·&nbsp;{mode}{/if}</div>
		{:else}
			<span class="lectio-question-number">{item.id.startsWith('Q') ? item.id : i + 1}.</span>
		{/if}
		<div class={taskNumber(item.id) && 'lectio-task-body'}>
		{#if item.marks != null}
			<span class="lectio-question-marks">[{item.marks}]</span>
		{/if}
		<InlineView nodes={asRichText(item.prompt)} />
		<div class="lectio-answer-lines">
			{#each Array(item.answer_lines ?? 3) as _}
				<div class="lectio-answer-line"></div>
			{/each}
		</div>
		</div>
	</div>
{/each}

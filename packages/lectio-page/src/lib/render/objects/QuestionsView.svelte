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
		{#if item.match}
			<p class="lectio-match-instruction">Write the letter of the matching answer in each box.</p>
			<div class="lectio-match">
				<ol class="lectio-match-col lectio-match-left">
					{#each item.match.left as entry, n}
						<li class="lectio-match-row">
							<span class="lectio-match-key">{n + 1}</span>
							<span class="lectio-match-text"><InlineView nodes={asRichText(entry)} /></span>
							<span class="lectio-match-blank">Match</span>
						</li>
					{/each}
				</ol>
				<ol class="lectio-match-col lectio-match-right">
					{#each item.match.right as entry, n}
						<li class="lectio-match-row">
							<span class="lectio-match-key">{String.fromCharCode(65 + n)}</span>
							<span class="lectio-match-text"><InlineView nodes={asRichText(entry)} /></span>
						</li>
					{/each}
				</ol>
			</div>
		{/if}
		<div class="lectio-answer-lines">
			{#each Array(item.answer_lines ?? 3) as _}
				<div class="lectio-answer-line"></div>
			{/each}
		</div>
		</div>
	</div>
{/each}

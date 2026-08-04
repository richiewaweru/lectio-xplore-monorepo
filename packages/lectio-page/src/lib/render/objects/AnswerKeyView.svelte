<script lang="ts">
	import type { AnswerKeyContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: AnswerKeyContent } = $props();
</script>

<section class="lectio-answer-key">
	<h2>Answer key</h2>
	{#each content.groups as group}
		{#if group.title}
			<h3>{group.title}</h3>
		{/if}
		{#each group.entries as entry}
			<div class="lectio-answer-key-entry">
				<p>
					<strong>{entry.question_id}.</strong>
					<InlineView nodes={asRichText(entry.answer)} />
				</p>
				{#if entry.working}
					<p><InlineView nodes={asRichText(entry.working)} /></p>
				{/if}
				{#if entry.rubric}
					<p><InlineView nodes={asRichText(entry.rubric)} /></p>
				{/if}
			</div>
		{/each}
	{/each}
</section>

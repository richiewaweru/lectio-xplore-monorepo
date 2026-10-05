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
				{#if entry.feedback}
					<p><strong>Feedback:</strong> <InlineView nodes={asRichText(entry.feedback)} /></p>
				{/if}
				{#if entry.not_marked}
					<p><strong>Not marked:</strong> accept either response.</p>
				{/if}
				{#if entry.option_notes && Object.keys(entry.option_notes).length > 0}
					<table class="lectio-option-notes">
						<thead><tr><th>Option</th><th>Teacher note</th></tr></thead>
						<tbody>
							{#each Object.entries(entry.option_notes) as [option, note]}
								<tr><th>{option}</th><td><InlineView nodes={asRichText(note)} /></td></tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</div>
		{/each}
	{/each}
</section>

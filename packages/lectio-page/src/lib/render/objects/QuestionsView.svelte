<script lang="ts">
	import type { QuestionsContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: QuestionsContent } = $props();
</script>

{#if content.instructions}
	<p><InlineView nodes={asRichText(content.instructions)} /></p>
{/if}

{#each content.items as item, i}
	<div class="lectio-question" id={item.id}>
		<span class="lectio-question-number">{i + 1}.</span>
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
{/each}

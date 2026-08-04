<script lang="ts">
	import type { ChoicesContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: ChoicesContent } = $props();
</script>

<div class="lectio-choices">
	<p>
		{#if content.marks != null}
			<span class="lectio-question-marks">[{content.marks}]</span>
		{/if}
		<InlineView nodes={asRichText(content.stem)} />
	</p>
	{#each content.options as option}
		<div class="lectio-choice">
			<span class="lectio-choice-letter">{option.letter}.</span>
			<InlineView nodes={asRichText(option.text)} />
		</div>
	{/each}
</div>

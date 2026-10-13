<script lang="ts">
	import type { WorkedExampleContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: WorkedExampleContent } = $props();
</script>

<div class="lectio-worked-example">
	{#if content.title}
		<p><strong>{content.title}</strong></p>
	{/if}
	<p><InlineView nodes={asRichText(content.problem)} /></p>
	{#each content.steps as step, i}
		<div class="lectio-step">
			<span class="lectio-step-number">{i + 1}.</span>
			<span class="lectio-step-text"><InlineView nodes={asRichText(step.text)} /></span>
		</div>
	{/each}
	<div class="lectio-step">
		<span class="lectio-step-number">∴</span>
		<strong>Answer:</strong>
		<span class="lectio-step-text"><InlineView nodes={asRichText(content.answer)} /></span>
	</div>
	{#if content.check}
		<p><InlineView nodes={asRichText(content.check)} /></p>
	{/if}
</div>

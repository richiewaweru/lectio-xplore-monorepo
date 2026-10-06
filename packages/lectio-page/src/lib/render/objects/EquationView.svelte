<script lang="ts">
	import type { EquationContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: EquationContent } = $props();
</script>

<div class="lectio-equation">
	{#if content.label}<strong class="lectio-equation-label"><InlineView nodes={asRichText(content.label)} /></strong>{/if}
	<div class="lectio-equation-row">
		<div class="lectio-equation-terms">
			{#each content.inputs as input, i}
				{#if i > 0}<span aria-hidden="true">+</span>{/if}
				<span><InlineView nodes={asRichText(input)} /></span>
			{/each}
		</div>
		<div class="lectio-equation-arrow">
			{#if content.condition}<small><InlineView nodes={asRichText(content.condition)} /></small>{/if}
			<span aria-hidden="true">→</span>
		</div>
		<div class="lectio-equation-terms">
			{#each content.outputs as output, i}
				{#if i > 0}<span aria-hidden="true">+</span>{/if}
				<span><InlineView nodes={asRichText(output)} /></span>
			{/each}
		</div>
	</div>
</div>

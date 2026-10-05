<script lang="ts">
	import type { CompareContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: CompareContent } = $props();
</script>

<div class="lectio-compare">
	{#each content.items as item}
		<article class="lectio-compare-item">
			{#if item.label}<p class="lectio-compare-label"><InlineView nodes={asRichText(item.label)} /></p>{/if}
			<h3><InlineView nodes={asRichText(item.title)} /></h3>
			<p><InlineView nodes={asRichText(item.body)} /></p>
		</article>
	{/each}
</div>
